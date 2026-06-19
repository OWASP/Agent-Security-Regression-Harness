# CI with GitHub Actions

This repository uses one CI workflow committed under `.github/workflows/`, with two jobs:

| Workflow file | Job | Purpose |
|--------------|-----|---------|
| `tests.yml` | `test` | Run `pytest` on every push/PR to `main` |
| `tests.yml` | `security-regression` | Validate scenarios and run trace-based harness checks |

## What the committed workflow does

The `security-regression` job in `.github/workflows/tests.yml`:

1. Checks out the repository
2. Sets up Python 3.11
3. Installs the harness with `python -m pip install -e .`
4. Creates the `results/` directory
5. Runs trace-based harness checks against passing traces for representative scenarios (scenario validation is already covered by pytest)
6. Dry-runs remaining scenarios that lack trace fixtures
7. Reads every file in `results/` and exits 1 if any has `"result": "fail"` or `"result": "error"`
8. Reads every file in `regression_demo/` and exits 1 if any does not have `"result": "fail"`
9. Uploads result JSON files as artifacts (runs even on failure)

## Validating scenarios

`agent-harness validate` accepts scenario files, directories, and glob patterns.
Directories are searched recursively for `.yaml` and `.yml` files. The command
prints one line per scenario, prints a summary, and exits 1 if any scenario is
invalid.

Validate one file:

```bash
agent-harness validate scenarios/goal_hijack/basic.yaml
```

Validate every scenario in a directory:

```bash
agent-harness validate scenarios/
```

Validate a glob, including nested folders:

```bash
agent-harness validate "scenarios/**/*.yaml"
```

Example CI step:

```yaml
- name: Validate security scenarios
  run: agent-harness validate "scenarios/**/*.yaml"
```

## How pass and fail actually work

`agent-harness run` writes machine-readable result JSON to the path you give
`--out`. The `result` field in that JSON will be `pass`, `fail`, `not_run`,
or `error`.

For CI systems that ingest JUnit XML, also pass `--junit-out <path>`. This
writes one testcase per assertion while preserving the result JSON output:

```bash
agent-harness run scenarios/goal_hijack/basic.yaml \
  --trace-file examples/traces/no_denied_tool_call.json \
  --out results/basic.json \
  --junit-out results/basic.xml
```

By default `agent-harness run` exits 0 on every successful run regardless of
assertion outcomes — the result JSON is the source of truth. There are two
ways to turn that into a job failure:

**Per-step gating with `--exit-on-fail`** (simplest for a small number of
scenarios). Pass the flag and the process exits 1 when the overall result is
`fail` or `error`:

```bash
agent-harness run scenarios/goal_hijack/basic.yaml \
  --trace-file examples/traces/no_denied_tool_call.json \
  --exit-on-fail
```

**Whole-suite gating** (used by this repository's committed workflow). Run
every scenario without `--exit-on-fail`, write each result to `results/` for 
clean traces and to `regression_demo/` for expected-fail traces.
Add a step that scans every JSON in `results/` for a result that is
`"result": "fail"` or `"result": "error"` and exits 1 if any is found. 
Add a step that scans every JSON in `regression_demo/` for a result that is 
not `"result": "fail"` (where a fail is expected) and exits 1 if any is found.

A result of `"error"` means the harness did not complete the regression check
correctly, so both gate steps treat it as a CI failure.

```
harness writes JSON → gate (flag or post-scan) decides exit code → job pass/fail
```

## Running a whole suite at once

`agent-harness suite` runs many scenarios against a directory of trace files in
one invocation and emits a single aggregate summary. It keeps single-scenario
`run` unchanged — use `suite` when you have a folder of scenarios to gate on.

```bash
agent-harness suite scenarios/ \
  --trace-dir traces/ \
  --out-dir results/ \
  --exit-on-fail
```

### Directory conventions

- **Scenarios**: the positional arguments accept scenario files, directories
  (searched recursively for `.yaml`/`.yml`), and glob patterns — the same
  discovery rules as `agent-harness validate`.
- **Traces**: each scenario is mapped to a trace file by its **scenario id**:
  `<trace-dir>/<scenario_id>.json`. For a scenario whose id is
  `goal_hijack.basic_001`, the suite looks for
  `<trace-dir>/goal_hijack.basic_001.json`. Mapping by id (rather than by file
  path) keeps the mapping stable when scenario files move, and scenario ids are
  constrained to a filename-safe charset (`[A-Za-z0-9._-]`) so a trace lookup
  can never escape `--trace-dir`.

> Note: this id-based convention is specific to `suite`. The example traces
> under `examples/traces/` use descriptive names and are not laid out this way;
> to use them with `suite`, copy or rename each to `<scenario_id>.json`.

### Output

- `--out-dir` writes one `<scenario_id>.json` per scenario that ran (the same
  shape as `agent-harness run`), plus an aggregate `summary.json`.
- The aggregate summary is always printed to stdout. It contains the overall
  `result`, per-status `counts` (`total`, `pass`, `fail`, `error`, `not_run`),
  and one `scenarios` entry per scenario with its id, category, severity, the
  trace path used, and the full `detail` result. This makes the summary a
  self-contained audit record. It validates against
  `schemas/suite_result.schema.json`.

### Resilience and gating

The suite never lets one broken input hide the rest. A scenario that cannot run
is recorded as a per-scenario `error` (with an `error_reason`) and the suite
continues:

| `error_reason` | Cause |
|----------------|-------|
| `missing_trace` | No `<scenario_id>.json` under `--trace-dir` |
| `invalid_trace` | The trace file exists but is malformed JSON |
| `invalid_scenario` | The scenario YAML failed validation |
| `duplicate_scenario_id` | Two discovered scenarios share an id |

Exit behavior composes with CI the same way as `run`:

- Without `--exit-on-fail`, `suite` always exits 0 and the summary JSON is the
  source of truth.
- With `--exit-on-fail`, `suite` exits 1 if **any** scenario is `fail` or
  `error` — so a missing trace mapping or an unparseable scenario fails the
  build rather than silently reducing coverage.
- If the scenario arguments match nothing, or `--trace-dir` does not exist,
  `suite` exits 1 immediately. An empty match is treated as an error, not a
  vacuous pass.

A suite where every scenario comes back `not_run` (for example, only
recognized-but-unimplemented assertions) aggregates to `not_run` and does **not**
fail under `--exit-on-fail`. Watch the `not_run` count in the summary so a
green suite does not hide a suite that tested nothing.

## A note on `not_run`

Some assertions are recognized by the harness but not fully implemented yet.
`no_secret_disclosure` is one example. When an assertion has no implementation,
it comes back as `not_run` rather than `pass` or `fail`.

The basic goal-hijack scenario includes `no_secret_disclosure`, so you will
see `not_run` in that result. This is expected. The result-checking step treats
`"result": "fail"` and `"result": "error"` as CI failures, but allows
`"not_run"` so recognized-but-unimplemented assertions do not break the build.

## Run mode

The committed workflow uses `--trace-file` mode. It evaluates assertions against
pre-recorded JSON traces without starting a live agent.

That makes it a good fit for CI: no server to start, no API keys required,
and the same input always produces the same result.

To test against a live agent instead, see `--live` mode in the README. You
would need an HTTP agent server running before the harness step fires.

## Viewing results

Result JSON files are uploaded as a workflow artifact named
`regression-results` after every run. The artifact upload step has
`if: always()`, so you get the files whether the job passed or failed.
If you write JUnit XML with `--junit-out`, include the XML files in the same
artifact or pass them to your CI system's test-report publisher.

To find them:

1. Go to the Actions tab in your repository
2. Click the workflow run
3. Scroll to Artifacts
4. Download `regression-results`

Each file contains the scenario ID, result status, which assertions ran, and
the evidence for any failure.

## Adapting this for your own project

The file at `docs/examples/github-actions/security-regression.yml` is a
simpler reference workflow designed for copying into your own repository.

Copy it and customize:

```bash
cp docs/examples/github-actions/security-regression.yml .github/workflows/
```

Then edit the file to:

1. Point `agent-harness run --trace-file` commands at your trace files
2. Add one `agent-harness run` step per scenario

The result-checking step at the end works across however many scenarios you
add. It globs `results/*.json`, so you do not need to update it when you add
new scenarios.

## Adding a new scenario

When you add a scenario to this repository, add a matching trace file to
`examples/traces/` and a new run step to `.github/workflows/tests.yml`:

### Clean traces
```yaml
- name: Run my new scenario
  run: |
    agent-harness run scenarios/my_category/my_scenario.yaml \
      --trace-file examples/traces/my_trace.json \
      --out results/my_scenario.json
```

### Failing traces
```yaml
- name: Run my new scenario
  run: |
    agent-harness run scenarios/my_category/my_scenario.yaml \
      --trace-file examples/traces/my_trace.json \
      --out regression_demo/my_scenario.json
```

Add the scenario path to the exclusion list in the dry-run step to avoid running it twice.

The result-checking steps pick up new output files automatically. For `regression_demo/` 
entries, also add the expected filename to `.github/workflows/tests.yml` to the expected_files 
list in the "Fail if any expected regression-demo file is missing" step to prevent the gate 
from passing vacuously if the demo step stops emitting.

## Related

- [Trace format](trace-format.md)
- [README](../README.md)
