# CI with GitHub Actions

The workflow runs on every push to `main` and on every pull request targeting
`main`. It installs the harness, validates scenario files, and checks
assertions against pre-recorded traces. If an assertion fails, the workflow
fails and the regression is caught before merging.

## Workflow file location
`.github/workflows/security-regression.yml`

## How pass and fail work

The harness CLI exits with a non-zero code when an assertion fails. GitHub
Actions treats any non-zero exit code as a step failure, which fails the job
and marks the workflow red.

Example: a scenario has `denied_tools: [send_email]` and the trace contains
a `send_email` tool call. The `no_denied_tool_call` assertion fires, the CLI
exits with code 1, the step fails. No extra scripting needed.

## Run mode

This workflow uses `--trace-file` mode. It checks assertions against a
pre-recorded JSON trace without starting a live agent.

Good fit for CI because:

- no server needs to start
- no API keys required
- same input always produces the same result

To test against a live agent instead, see `--live` mode in the README. That
requires an HTTP agent server running before the harness is invoked.

## What the workflow does

1. Check out the repository
2. Set up Python 3.11
3. Install the harness with `pip install -e .`
4. Create the `results/` directory
5. Validate each scenario file with `agent-harness validate`
6. Run each scenario against its trace file with `agent-harness run`
7. Upload result JSON files as artifacts

## Viewing results

Result JSON files are uploaded as a workflow artifact named
`regression-results` after every run, including failed ones.

To find them:

1. Go to the Actions tab in your repository
2. Click the workflow run
3. Scroll to Artifacts
4. Download `regression-results`

Each file shows the scenario ID, result status, which assertions ran, and
the evidence for any failure.

## Adapting this for your own project

1. Copy `.github/workflows/security-regression.yml` to your repository
2. Put your scenario files in a `scenarios/` directory
3. Put your trace files in `examples/traces/`
4. Update the `agent-harness validate` and `agent-harness run` commands to
   point to your files
5. Add one `agent-harness run` step per scenario

## Adding a new scenario

When you write a new scenario file, add two things to the workflow:

1. An `agent-harness validate` call for the new file
2. An `agent-harness run` step with the scenario and its trace file

```yaml
- name: Validate my new scenario
  run: agent-harness validate scenarios/my_category/my_scenario.yaml

- name: Run my new scenario
  run: |
    agent-harness run scenarios/my_category/my_scenario.yaml \
      --trace-file examples/traces/my_trace.json \
      --out results/my_scenario.json
```

## Related

- [Trace format](trace-format.md)
- [README](../README.md)