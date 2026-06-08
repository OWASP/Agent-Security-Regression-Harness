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

## Validate a scenario suite

The `validate` command accepts one scenario file, a directory, or a glob. Directory
validation is recursive, prints one result per scenario, and exits non-zero if any
scenario is invalid:

```bash
agent-harness validate scenarios/
```

Globs are useful when a workflow only needs to validate part of a suite:

```bash
agent-harness validate "scenarios/mcp_trust_boundary/**/*.yaml"
```

Both forms finish with a summary count of valid and invalid scenarios.

## How pass and fail actually work

`agent-harness run` writes machine-readable result JSON to the path you give
`--out`. The `result` field in that JSON will be `pass`, `fail`, `not_run`,
or `error`.

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

The result-checking steps pick up new output files automatically.

## Related

- [Trace format](trace-format.md)
- [README](../README.md)
