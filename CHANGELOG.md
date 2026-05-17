# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-17

First packaged release. Consolidates the v0.0.x development series into
a usable OWASP Incubator baseline.

### Added

- **CLI** (`agent-harness`) with `version`, `validate`, and `run` subcommands.
- **Run modes** for `run`: `--dry-run`, `--trace-file`, `--live --target-url`,
  `--python-target`, `--openai-agent`, `--mcp-target`, `--langchain-target`.
- **`--exit-on-fail` flag** on `agent-harness run` that exits with code 1 if
  the overall result is `fail` or `error`. Default behaviour (exit 0 on every
  successful run regardless of assertion outcomes) is unchanged.
- **Scenario format** (YAML) with JSON Schema at
  `schemas/scenario.schema.json` and validation in
  `src/agent_harness/scenario.py`.
- **Result JSON output** with schema at `schemas/result.schema.json`.
- **Trace model** covering `messages`, `tool_calls`, and `events`.
- **Four implemented assertions**:
  - `no_denied_tool_call` — denylist plus optional `allowed_tools` allowlist
  - `goal_integrity` — fail on drift from the expected goal event
  - `memory_isolation` — fail on configured `forbidden_markers` anywhere in the
    trace, with redacted failure evidence (count, marker index, SHA-256 prefix,
    character length) so the harness does not re-leak the secrets it catches
  - `no_external_recipient` — fail on outbound actions to recipients or domains
    outside the allowlist; scans `tool_calls` (top-level and `arguments`) and
    `tool_code` event `code` / `data.code` fields
- **Adapters**:
  - HTTP target adapter
  - Python callable target adapter (sync + async, including callable objects
    with `async __call__` and sync wrappers returning awaitables)
  - OpenAI Agents SDK adapter (MVP)
  - LangChain / LangGraph adapter (MVP)
  - MCP workflow adapter (deterministic, vendor-neutral)
  - MCP stdio host runtime with full session lifecycle, output bounding,
    server-identity preservation, and rejection of forged MCP evidence from
    targets
- **20 bundled scenarios** across 8 categories: `goal_hijack`,
  `prompt_injection`, `unsafe_tool_execution`, `sensitive_data_disclosure`,
  `privilege_escalation`, `memory_isolation`, `approval_bypass`,
  `mcp_trust_boundary`. Each scenario ships with a per-scenario passing
  trace fixture at `examples/traces/<category>/<name>_pass.json`.
- **Demo targets** under `examples/targets/`: HTTP, vulnerable HTTP,
  hardened HTTP, Python callable, LangChain Runnable, MCP workflow.
- **CI workflow** (`.github/workflows/tests.yml`) with three jobs:
  `test` (pytest), `lint` (ruff + mypy), and `security-regression`
  (trace-based harness runs with result-JSON gating and artifact upload).
  Concurrency block cancels superseded runs on the same ref.
- **Release workflow** (`.github/workflows/release.yml`). Pushing a tag
  matching `v<major>.<minor>.<patch>` (or `…rc<N>`) runs the quality
  gates on the tagged commit, builds sdist + wheel, publishes to PyPI
  via trusted publishing (no long-lived token), and attaches the
  artifacts to a GitHub release. Maintainer procedure is documented in
  `docs/releasing.md`.
- **Cookbook** at `docs/cookbook.md` with 7 runnable examples.
- **Documentation**: `scenario-spec.md` (including a written decision
  on the schema-vs-Python validation asymmetry), `trace-format.md`,
  `adapters.md`, `architecture.md`, `scope.md`, `non-goals.md`,
  `mcp-adapter-design.md`, `integrating-your-agent.md`,
  `ci-github-actions.md`, `releasing.md`, plus per-assertion docs
  under `docs/assertions/` and a fixture-layout README under
  `examples/traces/`.
- **Project hygiene**: `CONTRIBUTING.md` with an AI-assistance disclosure
  policy, `SECURITY.md`, `GOVERNANCE.md`, `AGENTS.md`, issue forms under
  `.github/ISSUE_TEMPLATE/`, `.github/CODEOWNERS`, and a PR template.
- **Test infrastructure**: ruff (line-length 100, ruleset `E,F,I,UP,B`)
  and mypy configured in `pyproject.toml` and gated in CI; schema
  validation tests for emitted result JSON
  (`tests/test_result_schema.py`); scenario/schema synchronization tests
  (`tests/test_scenario_schema_sync.py`); and per-scenario passing
  fixture tests (`tests/test_scenario_pass_fixtures.py`).

### Changed

- `no_denied_tool_call` semantics extended: `expected.allowed_tools`, when
  present, acts as an allowlist for all observed tool calls in addition to
  the existing `denied_tools` denylist behavior.

### Fixed

- Type errors in `mcp_adapter.py` (missing `server_id is not None`
  guard) and `mcp_host.py` (event-dict inference) surfaced by mypy.
  Both were latent invariants the runtime relied on.

### Security

- `memory_isolation` failure evidence no longer echoes the raw marker value
  it found. Evidence now reports `count=N` plus per-match
  `marker[index](sha256=<12-char>, chars=N)` so triage stays possible without
  re-exposing secrets in CI logs or result artifacts.
- MCP host rejects target-supplied MCP trace evidence (host-owned
  `mcp_servers` / `mcp_tool_calls` / `mcp_events`, canonical
  `mcp/<server>/<tool>` tool names, and any `tool_call` carrying top-level
  `mcp_*` metadata fields), so a target cannot forge MCP evidence.
- MCP fixture filesystem rejects absolute paths, `..` traversal, symlinks,
  Windows junctions and reparse points, marker-file access, directory
  deletions, oversized reads, and non-UTF-8 reads.

[Unreleased]: https://github.com/OWASP/Agent-Security-Regression-Harness/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWASP/Agent-Security-Regression-Harness/releases/tag/v0.1.0
