"""Deterministic state models for the ``forbidden_state_not_reached`` assertion.

A scenario declares a state model under ``expected.state_model``:

- ``initial`` — starting values for named state fields.
- ``transitions`` — rules that map normalized effect events to state updates.
- ``forbidden`` — predicates over the state that must never become true.

Recorded trace events carry normalized effects (``type: "effect"``) and
optional provenance references. The assertion folds those effects in
order, evaluates every forbidden predicate after each transition, and
fails at the first transition that makes a predicate true. The fold is
pure and deterministic: the same model and the same event sequence
always produce the same result.
"""

from __future__ import annotations

import fnmatch
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

EFFECT_EVENT_TYPE = "effect"

STATE_MODEL_KEYS = {"initial", "transitions", "forbidden"}
TRANSITION_KEYS = {"when", "requires", "set", "add"}
WHEN_KEYS = {"effect", "resource", "destination"}
PREDICATE_KEYS = {"id", "all"}
CONDITION_OPERATORS = ("equals", "not_equals", "greater_than", "less_than", "matches")

SCALAR_TYPES = (bool, int, float, str)
NUMERIC_TYPES = (int, float)


class EffectSequenceError(ValueError):
    """Raised when effect events violate the monotonic sequence contract.

    Effect events may stamp an integer ``sequence`` at record time. When
    some events carry a stamp and others do not, when stamps are not
    integers, or when stamps repeat, the intended fold order is
    ambiguous and the trace's evidence is unreliable.
    """


@dataclass(frozen=True)
class ProvenanceEntry:
    """One recorded contribution of a transition to a state field."""

    transition_index: int
    effect: str
    provenance_refs: tuple[str, ...]


@dataclass(frozen=True)
class StateViolation:
    """The first forbidden predicate that became true during the fold."""

    predicate_id: str
    transition_index: int
    effect: str
    field_provenance: tuple[tuple[str, tuple[ProvenanceEntry, ...]], ...]


@dataclass(frozen=True)
class StateFoldResult:
    """Outcome of folding effect events through a state model."""

    final_state: dict[str, Any]
    field_provenance: dict[str, tuple[ProvenanceEntry, ...]]
    violation: StateViolation | None


def _is_scalar(value: Any) -> bool:
    return isinstance(value, SCALAR_TYPES)


def _is_number(value: Any) -> bool:
    return isinstance(value, NUMERIC_TYPES) and not isinstance(value, bool)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_state_model(model: Any) -> list[str]:
    """Validate a scenario ``expected.state_model`` mapping.

    Returns a list of human-readable error strings; an empty list means
    the model is valid.
    """
    errors: list[str] = []

    if not isinstance(model, dict):
        return ["expected.state_model must be an object"]

    unknown_model_keys = sorted(set(model) - STATE_MODEL_KEYS)
    if unknown_model_keys:
        errors.append(
            f"expected.state_model has unsupported keys: {', '.join(unknown_model_keys)}"
        )

    for required_key in ("initial", "transitions", "forbidden"):
        if required_key not in model:
            errors.append(f"expected.state_model.{required_key} is required")

    if errors:
        return errors

    initial = model["initial"]
    transitions = model["transitions"]
    forbidden = model["forbidden"]

    declared_fields: set[str] = set()
    add_fields: set[str] = set()
    guard_fields: set[str] = set()

    if not isinstance(initial, dict):
        errors.append("expected.state_model.initial must be an object")
    else:
        for name, value in initial.items():
            if not _is_non_empty_string(name):
                errors.append("expected.state_model.initial keys must be non-empty strings")
                continue
            declared_fields.add(name)
            if not _is_scalar(value):
                errors.append(
                    f"expected.state_model.initial.{name} must be a bool, number, or string"
                )

    if not isinstance(transitions, list) or not transitions:
        errors.append("expected.state_model.transitions must be a non-empty list")
    else:
        for index, rule in enumerate(transitions):
            errors.extend(
                _validate_transition_rule(index, rule, declared_fields, add_fields, guard_fields)
            )

    if not isinstance(forbidden, list) or not forbidden:
        errors.append("expected.state_model.forbidden must be a non-empty list")
    else:
        for index, predicate in enumerate(forbidden):
            errors.extend(_validate_predicate(index, predicate, declared_fields))

    for name in sorted(add_fields):
        if name in initial and not _is_number(initial[name]):
            errors.append(
                f"expected.state_model.initial.{name} must be a number because "
                "a transition rule adds to it"
            )

    for name in sorted(guard_fields):
        if name not in declared_fields:
            errors.append(
                f"expected.state_model.requires field '{name}' is not declared in "
                "expected.state_model.initial or any transition rule"
            )

    # The fold only evaluates predicates after transitions. A predicate that
    # already holds in the initial state would therefore never fire, so it is
    # rejected statically while the model structure is still being validated.
    if not errors and isinstance(initial, dict) and isinstance(forbidden, list):
        for index, predicate in enumerate(forbidden):
            if isinstance(predicate, dict) and _predicate_holds(predicate, initial):
                errors.append(
                    f"expected.state_model.forbidden[{index}] ('{predicate.get('id')}') "
                    "is already true in the initial state; the fold only evaluates "
                    "predicates after transitions"
                )

    for index, rule in enumerate(transitions) if isinstance(transitions, list) else []:
        if not isinstance(rule, dict) or not isinstance(rule.get("set"), dict):
            continue
        for name, value in rule["set"].items():
            if name in add_fields and not _is_number(value):
                errors.append(
                    f"expected.state_model.transitions[{index}].set.{name} must be a "
                    "number because another transition rule adds to it"
                )

    return errors


def _validate_transition_rule(
    index: int,
    rule: Any,
    declared_fields: set[str],
    add_fields: set[str],
    guard_fields: set[str],
) -> list[str]:
    label = f"expected.state_model.transitions[{index}]"
    errors: list[str] = []

    if not isinstance(rule, dict):
        return [f"{label} must be an object"]

    unknown = sorted(set(rule) - TRANSITION_KEYS)
    if unknown:
        errors.append(f"{label} has unsupported keys: {', '.join(unknown)}")

    when = rule.get("when")
    if not isinstance(when, dict):
        return errors + [f"{label}.when must be an object"]

    unknown_when_keys = sorted(set(when) - WHEN_KEYS)
    if unknown_when_keys:
        errors.append(f"{label}.when has unsupported keys: {', '.join(unknown_when_keys)}")

    for key in sorted(WHEN_KEYS):
        if key in when and not _is_non_empty_string(when[key]):
            errors.append(f"{label}.when.{key} must be a non-empty string")
    if "effect" not in when:
        errors.append(f"{label}.when.effect is required")

    guard = rule.get("requires")
    if "requires" in rule:
        if not isinstance(guard, list) or not guard:
            errors.append(f"{label}.requires must be a non-empty list")
        else:
            for condition_index, condition in enumerate(guard):
                condition_label = f"{label}.requires[{condition_index}]"
                errors.extend(_validate_condition_shape(condition_label, condition))
                if isinstance(condition, dict) and _is_non_empty_string(condition.get("field")):
                    guard_fields.add(condition["field"])

    has_set = isinstance(rule.get("set"), dict) and bool(rule["set"])
    has_add = isinstance(rule.get("add"), dict) and bool(rule["add"])
    if "set" in rule and not has_set:
        errors.append(f"{label}.set must be a non-empty object")
    if "add" in rule and not has_add:
        errors.append(f"{label}.add must be a non-empty object")
    if not has_set and not has_add:
        errors.append(f"{label} must define at least one of set or add")

    if has_set:
        for name, value in rule["set"].items():
            if not _is_non_empty_string(name):
                errors.append(f"{label}.set keys must be non-empty strings")
                continue
            declared_fields.add(name)
            if not _is_scalar(value):
                errors.append(f"{label}.set.{name} must be a bool, number, or string")

    if has_add:
        for name, value in rule["add"].items():
            if not _is_non_empty_string(name):
                errors.append(f"{label}.add keys must be non-empty strings")
                continue
            declared_fields.add(name)
            add_fields.add(name)
            if not _is_number(value):
                errors.append(f"{label}.add.{name} must be a number")

    return errors


def _validate_predicate(index: int, predicate: Any, declared_fields: set[str]) -> list[str]:
    label = f"expected.state_model.forbidden[{index}]"
    errors: list[str] = []

    if not isinstance(predicate, dict):
        return [f"{label} must be an object"]

    unknown = sorted(set(predicate) - PREDICATE_KEYS)
    if unknown:
        errors.append(f"{label} has unsupported keys: {', '.join(unknown)}")

    if not _is_non_empty_string(predicate.get("id")):
        errors.append(f"{label}.id must be a non-empty string")

    conditions = predicate.get("all")
    if not isinstance(conditions, list) or not conditions:
        errors.append(f"{label}.all must be a non-empty list")
        return errors

    for condition_index, condition in enumerate(conditions):
        label_condition = f"{label}.all[{condition_index}]"
        errors.extend(_validate_condition(label_condition, condition, declared_fields))

    return errors


def _validate_condition(label: str, condition: Any, declared_fields: set[str]) -> list[str]:
    if not isinstance(condition, dict):
        return [f"{label} must be an object"]

    errors = _validate_condition_shape(label, condition)
    if errors:
        return errors

    if condition["field"] not in declared_fields:
        errors.append(
            f"{label}.field '{condition['field']}' is not declared in "
            "expected.state_model.initial or any transition rule"
        )

    return errors


def _validate_condition_shape(label: str, condition: Any) -> list[str]:
    """Validate one condition's structure without checking field declaration.

    Guard conditions may reference fields that a later transition rule
    declares, so their declared-field check runs after all rules are
    scanned instead of here.
    """
    if not isinstance(condition, dict):
        return [f"{label} must be an object"]

    errors: list[str] = []
    present_operators = sorted(set(condition) & set(CONDITION_OPERATORS))
    unknown = sorted(set(condition) - {"field"} - set(CONDITION_OPERATORS))
    if unknown:
        errors.append(f"{label} has unsupported keys: {', '.join(unknown)}")

    if not _is_non_empty_string(condition.get("field")):
        errors.append(f"{label}.field must be a non-empty string")

    if len(present_operators) != 1:
        errors.append(
            f"{label} must define exactly one operator: "
            + ", ".join(CONDITION_OPERATORS)
        )
        return errors

    operator = present_operators[0]
    value = condition[operator]
    if operator in {"greater_than", "less_than"} and not _is_number(value):
        errors.append(f"{label}.{operator} must be a number")
    if operator == "matches" and not isinstance(value, str):
        errors.append(f"{label}.matches must be a string glob pattern")

    return errors


def extract_effect_events(events: list[Any]) -> list[dict[str, Any]]:
    """Return well-formed effect events from a trace's event list, in order.

    An effect event is an event with ``type == "effect"`` and a non-empty
    string ``effect`` field. Other events are ignored so traces can record
    additional event kinds without confusing the fold.
    """
    effect_events: list[dict[str, Any]] = []

    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != EFFECT_EVENT_TYPE:
            continue
        effect = event.get("effect")
        if isinstance(effect, str) and effect.strip():
            effect_events.append(event)

    return effect_events


def order_effect_events(effect_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order effect events for the fold according to the sequence contract.

    Effect events may stamp an integer ``sequence`` at record time. When
    every effect event stamps one, the stamped monotonic per-trace order
    is authoritative and the events are sorted by it, so a trace folds
    identically regardless of the order its JSON array was serialized in.
    When no event stamps one, arrival order is used. A mixture of stamped
    and unstamped events, non-integer stamps, or duplicate stamps leave
    the intended order ambiguous and raise :class:`EffectSequenceError`.
    """
    stamped = ["sequence" in event for event in effect_events]

    if any(stamped) and not all(stamped):
        raise EffectSequenceError(
            "some effect events carry a sequence stamp and others do not; "
            "the intended fold order is ambiguous"
        )

    if not any(stamped):
        return list(effect_events)

    for index, event in enumerate(effect_events):
        stamp = event["sequence"]
        if not isinstance(stamp, int) or isinstance(stamp, bool):
            raise EffectSequenceError(
                f"effect event at arrival index {index} has a non-integer sequence stamp"
            )

    ordered = [
        effect_events[index]
        for index in sorted(
            range(len(effect_events)),
            key=lambda position: (effect_events[position]["sequence"], position),
        )
    ]

    stamps = [event["sequence"] for event in ordered]
    seen: set[int] = set()
    duplicates: set[int] = set()
    for stamp in stamps:
        if stamp in seen:
            duplicates.add(stamp)
        seen.add(stamp)
    if duplicates:
        raise EffectSequenceError(f"duplicate sequence stamps: {sorted(duplicates)}")

    return ordered


def _extract_provenance_refs(event: dict[str, Any]) -> tuple[str, ...]:
    """Return the declared provenance references of an effect event."""
    provenance = event.get("provenance")

    if not isinstance(provenance, list):
        return ()

    return tuple(ref for ref in provenance if isinstance(ref, str) and ref.strip())


def _pattern_matches(pattern: Any, value: Any) -> bool:
    """Match a ``when`` pattern against an event field with glob semantics."""
    if not isinstance(pattern, str):
        return False
    if not isinstance(value, str) or not value.strip():
        return False
    return fnmatch.fnmatchcase(value.strip(), pattern)


def _rule_matches(when: dict[str, Any], event: dict[str, Any], effect: str) -> bool:
    """Return whether an effect event satisfies a transition rule's ``when``."""
    if not fnmatch.fnmatchcase(effect, str(when["effect"])):
        return False

    if "resource" in when and not _pattern_matches(when["resource"], event.get("resource")):
        return False

    if "destination" in when and not _pattern_matches(
        when["destination"], event.get("destination")
    ):
        return False

    return True


def _condition_holds(condition: dict[str, Any], state: dict[str, Any]) -> bool:
    """Evaluate one predicate condition against the current state.

    A condition on a field that is not present in the state never holds.
    """
    field = condition["field"]

    if field not in state:
        return False

    value = state[field]

    if "equals" in condition:
        return value == condition["equals"]
    if "not_equals" in condition:
        return value != condition["not_equals"]
    if "greater_than" in condition:
        return _is_number(value) and value > condition["greater_than"]
    if "less_than" in condition:
        return _is_number(value) and value < condition["less_than"]
    if "matches" in condition:
        return isinstance(value, str) and fnmatch.fnmatchcase(value, condition["matches"])

    return False


def _predicate_holds(predicate: dict[str, Any], state: dict[str, Any]) -> bool:
    return all(_condition_holds(condition, state) for condition in predicate["all"])


def _predicate_fields(predicate: dict[str, Any]) -> list[str]:
    """Return the fields referenced by a predicate, in order, deduplicated."""
    fields: list[str] = []

    for condition in predicate["all"]:
        field = condition["field"]
        if field not in fields:
            fields.append(field)

    return fields


def _guard_holds(guard: Any, state: dict[str, Any]) -> bool:
    """Return whether a transition rule's ``requires`` conditions hold.

    Guards make fold order observable: a guarded rule applies only when
    the current state satisfies its conditions, so effects that arrive
    before their precondition is established do not contribute. A
    condition on a field that is not present in the state never holds.
    """
    return all(_condition_holds(condition, state) for condition in guard)


def fold_state_model(
    model: dict[str, Any],
    effect_events: list[dict[str, Any]],
) -> StateFoldResult:
    """Fold effect events through a state model and evaluate its predicates.

    State starts at ``initial``. Effect events are ordered by the sequence
    contract (see :func:`order_effect_events`); each is one transition:
    every matching transition rule whose ``requires`` guard holds is
    applied in declared order, then every forbidden predicate is
    evaluated. The fold returns at the first predicate that becomes true
    and reports which transitions contributed to each referenced state
    field.
    """
    state = deepcopy(model["initial"])
    field_provenance: dict[str, tuple[ProvenanceEntry, ...]] = {}

    for transition_index, event in enumerate(order_effect_events(effect_events), start=1):
        effect = str(event["effect"]).strip()
        provenance_refs = _extract_provenance_refs(event)

        for rule in model["transitions"]:
            if not _rule_matches(rule["when"], event, effect):
                continue
            if "requires" in rule and not _guard_holds(rule["requires"], state):
                continue

            written_fields = list(rule.get("set", {})) + list(rule.get("add", {}))

            for name, value in rule.get("set", {}).items():
                state[name] = deepcopy(value)

            for name, delta in rule.get("add", {}).items():
                state[name] = state.get(name, 0) + delta

            for name in written_fields:
                entry = ProvenanceEntry(transition_index, effect, provenance_refs)
                field_provenance[name] = field_provenance.get(name, ()) + (entry,)

        for predicate in model["forbidden"]:
            if _predicate_holds(predicate, state):
                violation = StateViolation(
                    predicate_id=predicate["id"],
                    transition_index=transition_index,
                    effect=effect,
                    field_provenance=tuple(
                        (name, field_provenance.get(name, ()))
                        for name in _predicate_fields(predicate)
                    ),
                )
                return StateFoldResult(state, field_provenance, violation)

    return StateFoldResult(state, field_provenance, None)
