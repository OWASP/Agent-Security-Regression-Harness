# Trace fixtures

This directory holds JSON trace fixtures used by the harness for
trace-mode runs (`agent-harness run scenario.yaml --trace-file …`).

## Layout

There are three flavors of fixture:

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

**Known-evasion fixtures** at the top level of this directory:

- `email_exfiltration_emailaddress_key_violation.json`,
  `email_exfiltration_mail_key_violation.json`,
  `email_exfiltration_msgraph_torecipients_violation.json`,
  `email_exfiltration_sendgrid_personalizations_violation.json`,
  `email_exfiltration_custom_sendto_list_violation.json` — five recipient
  shapes that evade `no_external_recipient` today (#167).

Unlike the demo fixtures above, these are referenced only from
`tests/test_no_external_recipient_shape_evasion.py`, not from any workflow
or doc. See "Adding a known-evasion trace fixture" below for why.

## Adding a new fixture

When you add a new scenario at `scenarios/<category>/<name>.yaml`:

1. Create `examples/traces/<category>/<name>_pass.json` with a minimal
   trace that produces `pass` or `not_run` for the scenario.
2. Run `pytest tests/test_scenario_pass_fixtures.py` to confirm.

Keep fixtures small. A few-line `messages` array, an empty
`tool_calls`, and the necessary `events` (e.g. a `goal` event for
`goal_integrity` assertions) is usually enough.

## Adding a failing trace fixture

When you add a scenario that has a failing trace:

1. Create `examples/traces/<name>.json` with a trace that demonstrates
   the failure — the agent took an action the scenario is designed to catch.
2. Add a run step to `.github/workflows/tests.yml` writing the result
   to `regression_demo/`.
3. Add the output filename from your run step to `.github/workflows/tests.yml` 
   to the expected_files list in "Fail if any expected regression-demo file is 
   missing" step.
4. Run `agent-harness run scenarios/your_scenario.yaml --trace-file examples/traces/your_fixture.json`
   to confirm.
5. The `regression_demo/` gate will fail CI if the step does not emit a file or if the result is 
   anything other than `fail`.


## Adding a known-evasion trace fixture

Different from the section above, and easy to confuse with it. A *failing* trace
demonstrates an action the harness **does** catch. A *known-evasion* trace
demonstrates an action it **should** catch and currently does not, because the
assertion has a gap worth recording against an open issue.

Do not wire a known-evasion trace into `regression_demo/`. That gate requires
`result == "fail"` for every file it finds, and exists to prove the harness
caught the action. An evasion trace scores `pass` by definition, so adding one
turns the gate red on merge, and because `tests.yml` runs `security-regression`
on every pull request against `main`, every later pull request shows that job
red too, which masks a real regression arriving in the same step.

Instead:

1. Create `examples/traces/<name>_violation.json` with the evading trace.
2. Add a focused test that asserts the **correct** outcome (`fail`) and mark it
   `@pytest.mark.xfail(strict=True, reason="#<issue>: ...")`.
3. Run `pytest` to confirm it reports `xfailed`, not `failed`.

`strict=True` is what makes this hold its signal. While the gap is open the test
xfails and CI stays green. When the gap is fixed the assertion starts returning
`fail`, the xfail becomes an `XPASS`, and strict mode turns that into a hard
failure, so whoever lands the fix must retire the marker, which promotes the
trace to an ordinary regression test in the same commit. Attach the marker per
parameter rather than to the function, or a one-shape fix reds every shape that
is still evading.

One trap, worth stating because it is invisible: **do not put the fixture
integrity checks inside the xfail-marked test.** `xfail` reports *any* exception
as an expected failure, so an `AssertionError` from a guard is indistinguishable
from the assertion under test failing. A guard there is inert, and fixture rot
(a renamed trace, an emptied `expected` block, an exfiltration edited out of
`tool_calls`) reads as "gap still open" forever. Put those checks in a separate,
unmarked test.

The CI docs call a `regression_demo/` trace an *expected-fail* trace
(`docs/ci-github-actions.md`); a known-evasion trace is not one.

See `tests/test_no_external_recipient_shape_evasion.py` for a worked example of
both halves.


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
