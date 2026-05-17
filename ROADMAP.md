# Roadmap

Tracking issues live under GitHub milestones. This file is the narrative; the
milestones are the source of truth for scope.

## v0.0.1: Minimal runnable harness — **shipped**

Goal: prove the project can execute one security scenario and produce
machine-readable pass/fail output.

Shipped:

- Repository structure
- Scenario specification draft
- Scenario and result JSON schemas
- CLI skeleton (`agent-harness`)
- YAML scenario loading
- JSON result output
- Foundational scenarios
- Basic tests

## v0.0.2: Assertions and traces — **mostly shipped**

Goal: make results explainable.

Shipped:

- Execution trace model
- `no_denied_tool_call` assertion (with `expected.allowed_tools` allowlist
  enforcement)
- `goal_integrity` assertion
- `memory_isolation` assertion (with redacted marker evidence)
- `no_external_recipient` assertion
- Additional foundational scenarios (23 across 8 categories)

Carried forward:

- `no_secret_disclosure` — deferred. The known-secret regression case is
  covered today by `memory_isolation` with configured `forbidden_markers`.
  A generic unknown-secret detector remains an open question; see #24.
- `approval_required` — moved to v0.2.0 milestone (#80).

## v0.0.3: Generic HTTP adapter — **shipped**

Goal: test simple API-driven agents.

Shipped:

- Generic HTTP target adapter
- Documented request and response formats
- Toy vulnerable agent (`examples/targets/vulnerable_http_agent.py`)
- Toy hardened agent (`examples/targets/hardened_http_agent.py`)
- Local demo instructions in `README.md`

Bonus, not originally in scope:

- Python callable adapter
- OpenAI Agents SDK adapter (MVP)
- LangChain/LangGraph adapter (MVP)
- MCP workflow adapter and stdio host runtime (deterministic)
- CI workflow with trace-based regression gating
- Cookbook with runnable examples
- `AGENTS.md` and `docs/integrating-your-agent.md`

## v0.1.0: Incubator baseline release — **in progress**

Goal: a packaged alpha that ships consistently. Lock the release pipeline
(tag → PyPI), stabilize public artifacts (CLI exit codes, scenario/result
schemas, README accuracy), and make the project pip-installable on tag push.

Milestone: [v0.1.0 — Incubator baseline release](https://github.com/OWASP/Agent-Security-Regression-Harness/milestone/2)

Planned work:

- CLI `--exit-on-fail` flag (#83)
- Validate emitted result JSON against `result.schema.json` in tests (#87)
- Keep Python scenario validation and `scenario.schema.json` in sync (#88)
- Trace fixtures and assertion checks for every bundled scenario (#98)
- PyPI publish workflow on tag (#114)
- `CHANGELOG.md` following Keep a Changelog (#115)
- Version bump to 0.1.0 + Alpha classifier (#116)
- Issue templates and CODEOWNERS (#117)
- `ruff` + `mypy` in CI (#118)
- Realign README `no_secret_disclosure` claim (#119)

## v0.2.0: Hardening + CI ergonomics — planned

Goal: comfortable to run in real CI pipelines.

Milestone: [v0.2.0 — Hardening + CI ergonomics](https://github.com/OWASP/Agent-Security-Regression-Harness/milestone/3)

Planned work:

- `approval_required` assertion (#80)
- JUnit XML output (#81)
- Recursive scenario validation (#84)
- Suite-level runner for scenario/trace directories (#85)
- HTTP adapter timeout configurable (#92)
- Optional HTTP target headers without storing secrets (#93)
- Coverage gate in CI (#120)
- Schema versioning + breaking-change policy (#121)

## v0.3.0: Adapter parity + scanner integrations — planned

Goal: adapter family on par across vendors, plus security-tooling output
formats.

Milestone: [v0.3.0 — Adapter parity + scanner integrations](https://github.com/OWASP/Agent-Security-Regression-Harness/milestone/4)

Planned work:

- MCP trust-boundary scenario (#15)
- SARIF output for code-scanning integrations (#82)
- OpenAI Agents goal event support (#94)
- LangChain/LangGraph streaming/callback traces (#95)
- Full MCP host: HTTP transport, OAuth, full lifecycle beyond stdio MVP (#96)

## Backlog (unscheduled)

- `no_secret_disclosure` generic assertion (#24) — pending design decision
  on regex curation vs. entropy heuristics vs. dictionary patterns
