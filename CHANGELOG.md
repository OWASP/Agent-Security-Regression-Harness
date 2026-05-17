# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `agent-harness run --exit-on-fail` exits with code 1 if the overall
  result is `fail` or `error`. Default behaviour (exit 0 on every
  successful run regardless of assertion outcomes) is unchanged.
- Ruff (line-length 100, ruleset `E,F,I,UP,B`) and mypy added to dev
  dependencies and configured in `pyproject.toml`. CI now has a `lint`
  job that runs both, gating PRs on lint and type errors.
- `concurrency:` block on `tests.yml` so superseded runs on the same
  ref cancel automatically.

### Changed

- Whitespace and import-order cleanup driven by ruff across `src/` and
  `tests/`. Behaviour unchanged.

### Fixed

- Type errors surfaced by mypy in `mcp_adapter.py` (missing
  `server_id is not None` guard) and `mcp_host.py` (event-dict
  inference); both were latent invariants the runtime relied on.

## [0.1.0] — Unreleased

First packaged release. Consolidates the v0.0.x development series into
a usable OWASP Incubator baseline.

### Added

- **CLI** (`agent-harness`) with `version`, `validate`, and `run` subcommands.
- **Run modes** for `run`: `--dry-run`, `--trace-file`, `--live --target-url`,
  `--python-target`, `--openai-agent`, `--mcp-target`, `--langchain-target`.
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
- **23 bundled scenarios** across 8 categories: `goal_hijack`,
  `prompt_injection`, `unsafe_tool_execution`, `sensitive_data_disclosure`,
  `privilege_escalation`, `memory_isolation`, `approval_bypass`,
  `mcp_trust_boundary`.
- **Demo targets** under `examples/targets/`: HTTP, vulnerable HTTP,
  hardened HTTP, Python callable, LangChain Runnable, MCP workflow.
- **CI workflow** (`.github/workflows/tests.yml`) with a `test` job
  (pytest) and a `security-regression` job (trace-based harness runs with
  result-JSON gating and artifact upload).
- **Cookbook** at `docs/cookbook.md` with 7 runnable examples.
- **Documentation**: `scenario-spec.md`, `trace-format.md`, `adapters.md`,
  `architecture.md`, `scope.md`, `non-goals.md`, `mcp-adapter-design.md`,
  `integrating-your-agent.md`, `ci-github-actions.md`, plus per-assertion
  docs under `docs/assertions/`.
- **Project hygiene**: `CONTRIBUTING.md` with an AI-assistance disclosure
  policy, `SECURITY.md`, `GOVERNANCE.md`, `AGENTS.md`, issue forms under
  `.github/ISSUE_TEMPLATE/`, `.github/CODEOWNERS`, and a PR template.

### Changed

- `no_denied_tool_call` semantics extended: `expected.allowed_tools`, when
  present, acts as an allowlist for all observed tool calls in addition to
  the existing `denied_tools` denylist behavior.

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
