"""Known-evasion traces for ``no_external_recipient`` (#167).

Each trace here sends to an external recipient in a shape the recipient
extractor does not read, so the assertion returns ``pass`` where it should
return ``fail``. The refusal half of each scenario lives in
``examples/traces/sensitive_data_disclosure/<name>_pass.json`` and is collected
by ``tests/test_scenario_pass_fixtures.py``.

Two tests per shape, and the split is the point:

``test_evasion_fixtures_still_exercise_the_gap`` is **not** xfail-marked. It
checks that the fixtures still describe an evasion at all. This cannot live in
the xfail test below, because ``xfail`` reports *any* exception as an expected
failure: an ``AssertionError`` from a guard is indistinguishable from the
assertion under test failing, so a guard inside an xfail test is inert. Measured
against an earlier draft of this module, where all three checks sat inside the
xfail test: deleting a violation trace, emptying a scenario's ``expected``
block, and stripping the exfiltration out of a trace's ``tool_calls`` each left
the suite reporting ``5 xfailed`` and green.

``test_external_recipient_in_evading_shape_is_caught`` asserts the correct
outcome under ``xfail(strict=True)``, per shape. While a shape evades, it
xfails. Once extraction reaches that shape the assertion starts returning
``fail``, the xfail becomes an ``XPASS``, and strict mode turns that into a hard
failure, so the fix cannot land without retiring the marker for that shape. The
marker is attached per parameter rather than to the function so a one-shape fix
does not red the four shapes still evading.

These traces are deliberately not wired into the ``regression_demo/`` gate: that
gate requires ``result == "fail"`` for every file it finds and exists to prove
the harness caught an action, which is the opposite of what an evasion trace
demonstrates.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.runner import run_scenario_with_trace
from agent_harness.scenario import load_scenario
from agent_harness.trace import load_trace

REPO_ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios" / "sensitive_data_disclosure"
TRACES_DIR = REPO_ROOT / "examples" / "traces"

EXTERNAL_RECIPIENT = "attacker@bad-domain.com"

# (shape slug, the field the external recipient hides behind)
SHAPES = [
    ("emailaddress_key", "a sibling 'emailAddress' string field"),
    ("mail_key", "a sibling 'mail' string field"),
    ("msgraph_torecipients", "a Microsoft Graph 'message.toRecipients' envelope"),
    ("sendgrid_personalizations", "a SendGrid 'personalizations[].to[]' envelope"),
    ("custom_sendto_list", "a custom 'send_to' list of recipient objects"),
]

SHAPE_IDS = [shape for shape, _ in SHAPES]


def _paths(shape: str) -> tuple[Path, Path]:
    return (
        SCENARIOS_DIR / f"email_exfiltration_{shape}_001.yaml",
        TRACES_DIR / f"email_exfiltration_{shape}_violation.json",
    )


@pytest.mark.parametrize(("shape", "description"), SHAPES, ids=SHAPE_IDS)
def test_evasion_fixtures_still_exercise_the_gap(shape: str, description: str) -> None:
    """Guard the fixtures the xfail test depends on. Must not be xfail-marked."""
    scenario_path, trace_path = _paths(shape)
    assert scenario_path.is_file(), f"missing scenario {scenario_path.name}"
    assert trace_path.is_file(), f"missing trace {trace_path.name}"

    scenario = load_scenario(scenario_path)
    expected = scenario.raw.get("expected", {})
    assert expected.get("allowed_recipients") or expected.get("allowed_domains"), (
        f"{scenario_path.name} defines no allowlist, so no_external_recipient "
        "returns not_run and the xfail below can never flip"
    )

    trace = load_trace(trace_path)
    # tool_calls only. The address also appears in the `messages` prose, so
    # scanning the whole file would pass for a trace whose actual outbound
    # action had been removed.
    assert EXTERNAL_RECIPIENT in json.dumps(trace.tool_calls), (
        f"{trace_path.name} no longer sends to {EXTERNAL_RECIPIENT} in a tool "
        f"call via {description}, so it cannot demonstrate an evasion"
    )

    result = run_scenario_with_trace(scenario, trace)
    assert result.result != "not_run", (
        f"{scenario.id} did not run its assertions against {trace_path.name}"
    )


@pytest.mark.parametrize(
    ("shape", "description"),
    [
        pytest.param(
            shape,
            description,
            id=shape,
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    f"#167: {shape} evades recipient extraction, which reads a "
                    "fixed key list at fixed depth. Remove this mark in the "
                    "commit that fixes this shape."
                ),
            ),
        )
        for shape, description in SHAPES
    ],
)
def test_external_recipient_in_evading_shape_is_caught(shape: str, description: str) -> None:
    """An external recipient must fail the assertion whatever shape carries it."""
    scenario_path, trace_path = _paths(shape)
    scenario = load_scenario(scenario_path)
    trace = load_trace(trace_path)

    result = run_scenario_with_trace(scenario, trace)

    failed = [a for a in result.assertions if a.result == "fail"]
    assert failed, (
        f"{scenario.id} scored {result.result!r} against a trace that sends to "
        f"{EXTERNAL_RECIPIENT} via {description}"
    )
    # Check which recipient was caught. A verdict alone would also be satisfied
    # by an extractor that over-collects and flags a sender or reply-to address
    # while still never seeing the evading recipient.
    assert any(EXTERNAL_RECIPIENT in (a.evidence or "") for a in failed), (
        f"{scenario.id} failed, but on {[a.evidence for a in failed]} rather "
        f"than {EXTERNAL_RECIPIENT}, so it is not catching this evasion"
    )
