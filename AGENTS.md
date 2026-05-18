# AI Agent Guide: OWASP Agent Security Regression Harness

This file helps AI coding agents (Claude, Copilot, Cursor, etc.) understand this project and contribute effectively.

## Project overview

A Python CLI tool (`agent-harness`) that runs executable security regression scenarios against AI agents and MCP-integrated systems. It checks that security policies hold after code/prompt changes.

``` python
pip install -e . && agent-harness run scenarios/goal_hijack/basic.yaml --dry-run
```

## Architecture

```python
src/agent_harness/
  cli.py          # Entry point. argparse-based. Subcommands: version, validate, run
  scenario.py     # Loads & validates YAML scenarios (Scenario dataclass)
  trace.py        # Trace dataclass (messages, tool_calls, events)
  assertions.py   # Evaluates assertions against traces. Each assertion = one function
  result.py       # HarnessResult + AssertionResult dataclasses, status aggregation
  recorder.py     # TraceRecorder helper for incremental trace building
  runner.py       # Orchestrates: load scenario -> run target/adapter -> eval assertions
  adapters.py     # HTTP target + Python callable target runners
  openai_agents_adapter.py  # Runs OpenAI Agents SDK Agent, converts result -> Trace
  langchain_adapter.py      # Runs LangChain/LangGraph invoke(), converts result -> Trace
  mcp_adapter.py            # Runs MCP workflow callable, converts result -> Trace
  mcp_runtime.py            # MCP server config validation (future full host)

tests/
  test_*.py       # pytest. Mirrors src structure.
```

## Contribution workflow

1. Pick an open issue with `help wanted` or `good first issue` label
2. Fork, create a focused branch (`feature/`, `fix/`, `scenario/`, `docs/`)
3. Make small, reviewable changes
4. Run `python -m pytest` before pushing
5. Open PR and disclose AI assistance per CONTRIBUTING.md

## What needs doing

| Area | How to help |
|------|-------------|
| **Scenarios** | Add YAML files under `scenarios/<category>/`. See `docs/scenario-spec.md` |
| **Assertions** | Add function in `assertions.py`, register in `evaluate_assertions()` |
| **Adapters** | Add new target type in `adapters.py` or a new dedicated `*_adapter.py` |
| **CLI** | Add flags in `cli.py::build_parser()` + wiring in `main()` |
| **Tests** | Add `test_*.py` in `tests/` using pytest |
| **Docs** | Improve `docs/`, README, examples |
| **CI** | Add GitHub Actions workflows (`.github/workflows/`) |

## Key patterns

- **Scenario format**: YAML with `id`, `title`, `category`, `severity`, `target`, `input`, `expected`, `assertions`. Validated via `validate_scenario_data()`.
- **Adding an assertion type**: (1) Add eval function in `assertions.py`, (2) Register in `evaluate_assertions()`, (3) Optionally add validation in `validate_scenario_data()`, (4) Add tests in `tests/test_assertions.py`.
- **Adding an adapter**: (1) Create `*_adapter.py` with run function returning `Trace`, (2) Wire in `runner.py`, (3) Add CLI flags in `cli.py`, (4) Add tests.
- **Trace shape**: `{"messages": [...], "tool_calls": [...], "events": [...]}`. See `docs/trace-format.md`.
- **All assertions get**: scenario + trace as inputs, return `AssertionResult(id, result, evidence)`.

## Running tests

```bash
python -m pytest           # all tests
python -m pytest -v        # verbose
python -m pytest tests/test_assertions.py  # single file
```

## Style

- `from __future__ import annotations` in every file
- Type hints on everything (stdlib types preferred)
- Dataclasses for models, frozen=True when immutable
- Use the existing domain-specific exceptions for errors (e.g., `ScenarioValidationError`, `TraceValidationError`, and `AdapterError`) rather than introducing undocumented base types
- No external CLI dependencies (argparse only)
- Obvious names, minimal comments, no dead code
