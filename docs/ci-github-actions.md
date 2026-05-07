# CI with GitHub Actions

When copied into `.github/workflows/security-regression.yml`, this workflow runs 
on every push to `main` and on every pull request targeting
`main`. It installs the harness, validates scenario files, runs assertions
against pre-recorded traces, and explicitly checks the result JSON to fail
the job if any regression was detected.

## Where the example workflow lives

The example workflow is at:

```
docs/examples/github-actions/security-regression.yml
```

## How pass and fail actually work

`agent-harness run` writes machine-readable result JSON to the path you give
`--out`. The `result` field in that JSON will be `pass`, `fail`, `not_run`,
or `error`.

The workflow handles this by adding an explicit result-checking step after
all the `agent-harness run` steps. It reads every JSON file in `results/`,
looks for `"result": "fail"` or `"result": "error"`, and calls `sys.exit(1)`
if any are found. That is what actually fails the job.

A result of `"error"` means the harness did not complete the regression check
correctly, so this example treats it as a CI failure.

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
The README documents which assertions are currently implemented.

## Run mode

This workflow uses `--trace-file` mode. It evaluates assertions against a
pre-recorded JSON trace without starting a live agent.

That makes it a good fit for CI: no server to start, no API keys required,
and the same input always produces the same result.

To test against a live agent instead, see `--live` mode in the README. You
would need an HTTP agent server running before the harness step fires.

## What the workflow does

1. Check out the repository
2. Set up Python 3.11
3. Install the harness with `python -m pip install -e .`
4. Create the `results/` directory
5. Validate each scenario file with `agent-harness validate`
6. Run each scenario with `agent-harness run --trace-file ... --out results/....json`
7. Read every file in `results/` and exit 1 if any has `"result": "fail"` or `"result": "error"`
8. Upload result JSON files as artifacts (runs even when step 7 fails, because of `if: always()`)

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

1. Copy `docs/examples/github-actions/security-regression.yml` into
   `.github/workflows/security-regression.yml` in your repository
2. Put your scenario files in a `scenarios/` directory
3. Put your trace files in `examples/traces/`
4. Update the `agent-harness validate` and `agent-harness run` commands to
   point to your files
5. Add one `agent-harness run` step per scenario

The result-checking step at the end works across however many scenarios you
add. It globs `results/*.json`, so you do not need to update it when you add
new scenarios.

## Adding a new scenario

When you write a new scenario, add two things to the workflow:

```yaml
- name: Validate my new scenario
  run: agent-harness validate scenarios/my_category/my_scenario.yaml

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
