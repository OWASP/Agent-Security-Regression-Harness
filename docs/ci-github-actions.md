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
5. Validates every `.yaml` file under `scenarios/` with `agent-harness validate`
6. Runs trace-based harness checks against passing traces for representative scenarios
7. Dry-runs remaining scenarios that lack trace fixtures
8. Reads every file in `results/` and exits 1 if any has `"result": "fail"` or `"result": "error"`
9. Uploads result JSON files as artifacts (runs even on failure)

## How pass and fail actually work

`agent-harness run` writes machine-readable result JSON to the path you give
`--out`. The `result` field in that JSON will be `pass`, `fail`, `not_run`,
or `error`.

The workflow handles this by adding an explicit result-checking step after
all harness run steps. It reads every JSON file in `results/`,
looks for `"result": "fail"` or `"result": "error"`, and calls `sys.exit(1)`
if any are found. That is what actually fails the job.

A result of `"error"` means the harness did not complete the regression check
correctly, so the workflow treats it as a CI failure.

```
harness writes JSON → result-checking step reads JSON → step exits 1 → job fails
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
1. Point `agent-harness validate` commands at your scenario files
2. Point `agent-harness run --trace-file` commands at your trace files
3. Add one `agent-harness run` step per scenario

The result-checking step at the end works across however many scenarios you
add. It globs `results/*.json`, so you do not need to update it when you add
new scenarios.

## Adding a new scenario

When you add a scenario to this repository, add a matching trace file to
`examples/traces/` and a new run step to `.github/workflows/tests.yml`:

```yaml
- name: Run my new scenario
  run: |
    agent-harness run scenarios/my_category/my_scenario.yaml \
      --trace-file examples/traces/my_trace.json \
      --out results/my_scenario.json
```

The result-checking step picks up the new output file automatically.

## Related

- [Trace format](trace-format.md)
- [README](../README.md)
