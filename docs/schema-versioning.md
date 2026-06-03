# Schema Versioning and Breaking-Change Policy

This document defines the versioning contract for the two public JSON
Schemas shipped with the OWASP Agent Security Regression Harness:

- `schemas/scenario.schema.json` — the input format for scenario files.
- `schemas/result.schema.json` — the output format produced by
  `agent-harness run`.

It is the single source of truth for what counts as a breaking change,
how versions are bumped, how long deprecated fields are kept, and how
breaking changes are announced. It is intentionally a policy document,
not a generator: enforcement is provided by the schema-validation tests
referenced in [Cross-references](#cross-references).

## Scope

This policy covers:

- Versioning of the two schemas named above.
- The compatibility contract between the schemas and the published
  Python release of the `agent-harness` CLI.
- The deprecation and removal process for any field, enum value, or
  assertion type those schemas describe.

It does **not** cover:

- The Python source API of `agent_harness.*` (modules, functions,
  dataclasses). Those follow the package's normal SemVer release
  process in `CHANGELOG.md`.
- Trace JSON. Traces are a wire format produced by adapters and live
  targets; they are described in [`docs/trace-format.md`](trace-format.md)
  and evolve together with the result schema when needed. Any change
  to trace shape that affects the result schema is governed by this
  policy.

## Versioning model

Each schema carries a top-level integer `"version"` field:

- `schemas/scenario.schema.json` has a `"version"` field.
- `schemas/result.schema.json` has a `"version"` field.

These fields are the authoritative numeric state of each schema. Any
schema change is shipped together with an updated `"version"` value
and an entry in `CHANGELOG.md`. Adding the `"version"` field to a
schema that does not yet carry one is itself a PATCH change per
[SemVer mapping](#semver-mapping) (it adds a new optional field), and
the first introduction of a `"version"` field is documented in the
CHANGELOG so consumers can start reading it.

A schema's `version` is a single monotonically increasing integer
within its major line. The first released version is `1`. There is no
separate `major` / `minor` / `patch` field in the schema itself; the
magnitude of a change is decided by the rules in
[SemVer mapping](#semver-mapping) and is reflected in the package
release that ships the change, not in the on-the-wire schema.

The schemas do **not** embed the package version. The mapping between
schema major version and package version is fixed for the lifetime of
the major line and is recorded in
[Compatibility contract](#compatibility-contract).

## SemVer mapping

The package release that ships a schema change bumps the package
version using these rules. A change is evaluated against the *current
state* of the schema — additions and removals are both changes.

### MAJOR (breaking)

A change is MAJOR if any of the following is true:

- A required field is removed or renamed.
- A field that was previously optional becomes required and does not
  have a documented default.
- A field's type narrows in a way that rejects previously valid values
  (for example, `string` → `string` with a `pattern` that excludes
  existing values, or `array` of any item → `array` of objects with a
  strict `required` list).
- An enum value currently used by shipped scenarios is removed.
- The semantics of an existing field change such that previously valid
  inputs now produce a different result. This includes changes to
  conditional rules enforced by the Python validator in
  `src/agent_harness/scenario.py::validate_scenario_data` (for example,
  adding a new requirement that an assertion type must declare an
  additional non-empty field).
- The shape of the result JSON changes in a way consumers cannot
  paper over (for example, the top-level `result` enum gains a value
  the consumer has not been taught to handle, or `assertions` items
  gain a new required field).

A schema MAJOR bump is the signal that downstream tooling must
re-validate its stored data and may need code changes. It is paired
with a package MAJOR bump.

### MINOR (additive, backwards-compatible)

A change is MINOR if any of the following is true and **none** of the
MAJOR conditions above is true:

- A new optional field is added to any object.
- A new enum value is added to an existing enum, provided the value
  is purely additive and existing values are not renamed or removed.
- A new assertion `type` is added in `scenario.schema.json`. Adding an
  assertion type is part of the scenario schema's public surface and
  counts as MINOR.
- A new field is added to `assertions` items in `result.schema.json`,
  provided the field is optional and consumers that ignore unknown
  fields continue to work.
- A new `mode` value is added to the result JSON, on the same
  "consumers ignore unknown" basis.

A schema MINOR bump may be paired with a package MINOR bump when the
additions are user-visible. Internal-only additions (for example, a
new optional field that no code reads yet) still bump the schema
version but may be shipped in a PATCH package release if the maintainer
agrees; this is documented in the CHANGELOG entry.

### PATCH (clarifications and corrections)

A change is PATCH if any of the following is true and **none** of the
MAJOR or MINOR conditions above is true:

- A typo or wording fix in a schema `title`, `description`, or
  `$comment`.
- A non-substantive tightening that does not reject any previously
  valid value (for example, adding `minLength: 1` to a field whose
  values were already required to be non-empty by the Python
  validator).
- Adding or correcting `examples` blocks.
- Documentation-only changes to the prose in `docs/` that do not
  change the schema itself.

A schema PATCH bump does not require a package version bump. It is
expected to ride along with the next package release of any kind.

### Worked examples

| Change | Bump | Reason |
|---|---|---|
| Remove `result.trace` from `result.schema.json` | MAJOR | Required field removed. |
| Rename `expected.allowed_tools` to `expected.tool_allowlist` | MAJOR | Required field renamed. |
| Drop `enum` value `live` from `result.mode` | MAJOR | Enum value removed. |
| Add a new `result.schema.json` `mode` value `suite` | MINOR | Additive enum value. |
| Add a new optional `assertions[].tags` field | MINOR | New optional field. |
| Add a new assertion `type: approval_required` to the scenario schema | MINOR | New assertion type. |
| Fix typo in `result.schema.json` `title` | PATCH | Description-only. |
| Add `minLength: 1` to a field that is already required to be non-empty by the Python validator | PATCH | Already non-substantive. |

## Pre-1.0 rule: schemas track the package version

Until the first 1.0.0 release of the `agent-harness` CLI, schemas are
considered unstable. The following rules apply during the 0.x series:

- The schema `version` field tracks the package major version line. A
  package release at `0.x.y` ships schemas at major `1`. The first
  1.0.0 package release that introduces a stable contract will ship
  schemas at major `1`; an explicit `0.x → 1.0` transition plan is
  recorded in [Compatibility contract](#compatibility-contract) and
  the CHANGELOG when it happens.
- Schema MAJOR bumps within 0.x are permitted and are announced in
  the CHANGELOG, but they are not paired with a package MAJOR bump
  (because 0.x releases are allowed to break SemVer). The
  deprecation window below still applies.
- Schema MINOR and PATCH bumps follow the same rules as post-1.0.

In short: pre-1.0, the schema major is "1, but it may move" — and
when it moves, this policy is the only stable surface consumers can
rely on. The first 1.0.0 release of the package is the moment the
schema `version` is committed to a fixed line.

## Breaking-change definition

A *breaking change* is any change classified as MAJOR under
[SemVer mapping](#semver-mapping). The bar is set deliberately low
on purpose: a consumer that writes YAML to the current scenario
schema, or that reads the result JSON, must be able to rely on the
documented field set. Adding a new required field — even one that
"obviously" should be there — counts as breaking and goes through the
deprecation window.

Two non-breaking changes that compose to a breaking change are
treated as a single breaking change. For example, renaming a field
and then later removing the original name is a single breaking event
from the consumer's point of view: the deprecation clock starts when
the new name is added and the old name becomes deprecated, and the
old name is removed only after the deprecation window elapses.

## Deprecation window

A field, enum value, or assertion type that the maintainers intend to
remove must first be marked as deprecated. The deprecation window
is **at least one MINOR release** before removal, with the following
requirements:

- The PR that introduces the deprecation must:
  - Add a `deprecated: true` annotation in the schema (using
    `description` text where the schema dialect does not support a
    true annotation key) so editors warn contributors.
  - Add a `Deprecated` entry to `CHANGELOG.md` under `[Unreleased]`
    that names the deprecated item and the recommended replacement.
  - Include a PR-level note titled `Deprecation:` that surfaces the
    change in the GitHub PR conversation.
- The PR that performs the removal must:
  - Be a MAJOR release of the package (or, pre-1.0, a release that
    ships a schema MAJOR bump).
  - Add a `Removed` entry to `CHANGELOG.md` that names the removed
    item and the version in which it was deprecated.
  - Reference the deprecation PR in the description or commit
    message.

For MINOR changes (for example, a new optional field added now and
later made required), the same deprecation window applies in
reverse: the new field is added as optional, marked deprecated only
when the maintainers decide to require it, and the requirement takes
effect in a later MAJOR release.

A deprecation window may be extended, but not shortened, at the
maintainers' discretion. The extension is recorded in the CHANGELOG.

## Compatibility contract

The package release line guarantees a stable schema major version
across its lifetime. Concretely:

| Schema major | Package release line | Status |
|---|---|---|
| `1` | `0.1.x` and the first 1.0.0 release | Current pre-1.0 contract. May move under the [Pre-1.0 rule](#pre-10-rule-schemas-track-the-package-version). |
| `1` (frozen) | `1.x.y` and the first 2.0.0 release | Post-1.0 contract. Frozen: no MAJOR bumps within the 1.x line. |
| `2` (when cut) | `2.x.y` | Future contract. The transition is announced in the CHANGELOG with a written migration note and a 0.x → 1.0 → 2.0 trail of deprecations. |

A Python release of `agent-harness` is guaranteed to read and write
schemas at the major version listed for its release line. It is
permitted to also read older major versions for one additional
release line, to give downstream tooling a migration window. For
example, the `1.x` line may accept `result.schema.json` at major `1`
or `0` (the equivalent pre-1.0 line) so that tooling written against
`0.1.x` continues to work during the `0.1.x → 1.0.0` transition. The
exact backward-read window for each release is recorded in the
CHANGELOG entry that introduces the new major.

The schemas themselves are published as part of the wheel and the git
repository. Consumers that want to pin to a specific schema version
should pin both the `agent-harness` package version and the schema
file (for example, by vendoring a specific commit or by referencing
the schema via a permanent URL). The `version` field in the schema
is the only sanctioned way for a consumer to check which contract
they are holding.

## Announcing changes

Every schema change is announced twice: once at the proposal stage
and once at the release stage.

### At proposal stage (PR)

A pull request that changes a schema must include in its description:

- A one-line summary of the change, with the
  [SemVer mapping](#semver-mapping) classification (MAJOR / MINOR /
  PATCH).
- A "Breaking:" or "Deprecation:" or "Removal:" label line, as
  applicable.
- For MAJOR and MINOR changes: a brief migration note (one or two
  sentences) for downstream consumers.

The PR must also update `CHANGELOG.md` under `[Unreleased]` with the
appropriate subsection (`Added`, `Changed`, `Deprecated`, `Removed`,
`Fixed`, `Security`), per the contribution rules in
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

### At release stage (tag)

When a tagged release ships one or more schema changes, the release
notes (auto-generated by GitHub from the CHANGELOG) carry the same
information forward. The release workflow re-runs the schema
validation tests on the tagged commit, so a tag cannot ship if the
schemas drift from the Python validator. See
[`docs/releasing.md`](releasing.md) for the maintainer's release
procedure and `tests/test_scenario_schema_sync.py` for the
synchronization test.

## How to propose a change

The expected workflow is:

1. Open an issue describing the proposed change, the SemVer
   classification, and the consumer impact.
2. Maintainers triage and assign a milestone.
3. A pull request updates the schema, the Python validator (if the
   change touches conditional rules), the `tests/` synchronization
   tests, and the CHANGELOG.
4. The PR is merged into the next appropriate release.

Pure documentation changes to this file (`docs/schema-versioning.md`)
do not require a CHANGELOG entry. Changes to the **policy** itself —
that is, changes to the rules in this document — are reviewed by a
maintainer and announced in the CHANGELOG under `Changed`, because
they redefine what counts as a breaking change.

## Cross-references

- [`docs/scenario-spec.md`](scenario-spec.md) — the scenario format,
  which is the user-facing surface governed by `scenario.schema.json`.
- [`docs/trace-format.md`](trace-format.md) — the trace wire format
  that flows into the result JSON. Trace shape changes that affect
  the result schema are also covered by this policy.
- [`docs/releasing.md`](releasing.md) — the maintainer's release
  procedure, including the schema-validation gate in CI.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — the contributor workflow
  and the CHANGELOG conventions this policy builds on.
- [`CHANGELOG.md`](../CHANGELOG.md) — the running list of announced
  schema changes, deprecations, and removals.
- `schemas/scenario.schema.json` and `schemas/result.schema.json` —
  the schemas themselves; their `version` field is the authoritative
  numeric state.
- `tests/test_scenario_schema_sync.py` — the test that pins the
  Python validator to the scenario schema.
- `tests/test_result_schema.py` — the test that validates emitted
  result JSON against the result schema.
