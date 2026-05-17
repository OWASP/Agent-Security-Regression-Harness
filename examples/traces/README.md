# Trace fixtures

This directory holds JSON trace fixtures used by the harness for
trace-mode runs (`agent-harness run scenario.yaml --trace-file …`).

## Layout

There are two flavors of fixture:

**Per-scenario passing fixtures** under
`examples/traces/<category>/<scenario_basename>_pass.json`.

Each bundled scenario at `scenarios/<category>/<name>.yaml` has a
matching passing trace at `examples/traces/<category>/<name>_pass.json`.
Running the scenario against this fixture must produce a top-level
result of `pass` or `not_run`. These are enforced by
`tests/test_scenario_pass_fixtures.py`.

Example pair:

```
scenarios/goal_hijack/basic.yaml
examples/traces/goal_hijack/basic_pass.json
```

**Generic demo fixtures** at the top level of this directory:

- `denied_tool_call.json` — a trace that contains a denied tool call.
  Used in the README and CI workflow to demonstrate regression
  detection.
- `no_denied_tool_call.json` — a generic passing trace.
- `unexpected_allowed_tool_call.json` — demonstrates the
  `allowed_tools` allowlist enforcement.
- `memory_isolation_clean.json`, `memory_isolation_leak.json` — pair
  showing clean vs leaked-marker traces for the memory-isolation
  scenario.
- `external_recipient_violation.json`, `no_external_recipient_violation.json`
  — pair for `no_external_recipient`.

These are not paired 1:1 with a specific scenario and are referenced by
name from `.github/workflows/tests.yml`, `README.md`, and
`docs/ci-github-actions.md`.

## Adding a new fixture

When you add a new scenario at `scenarios/<category>/<name>.yaml`:

1. Create `examples/traces/<category>/<name>_pass.json` with a minimal
   trace that produces `pass` or `not_run` for the scenario.
2. Run `pytest tests/test_scenario_pass_fixtures.py` to confirm.

Keep fixtures small. A few-line `messages` array, an empty
`tool_calls`, and the necessary `events` (e.g. a `goal` event for
`goal_integrity` assertions) is usually enough.

## Schema

Trace JSON must be an object with three top-level fields, each a list
of objects:

```json
{
  "messages": [],
  "tool_calls": [],
  "events": []
}
```

See [docs/trace-format.md](../../docs/trace-format.md) for the full
trace contract.
