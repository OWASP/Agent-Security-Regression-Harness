# Roadmap

## v0.0.1: Minimal runnable harness

Goal: prove the project can execute one security scenario and produce machine-readable pass/fail output.

Planned work:

- Define initial repository structure
- Draft scenario specification
- Add scenario JSON schema
- Add result JSON schema
- Implement CLI skeleton
- Load YAML scenario files
- Emit JSON result files
- Add one foundational scenario
- Add basic tests

## v0.0.2: Assertions and traces

Goal: make results explainable.

Planned work:

- Add execution trace model
- Add `no_denied_tool_call` assertion
- Add `no_secret_disclosure` assertion
- Add `approval_required` assertion
- Add additional foundational scenarios

## v0.0.3: Generic HTTP adapter

Goal: test simple API-driven agents.

Planned work:

- Add generic HTTP target adapter
- Document expected request and response formats
- Add toy vulnerable agent
- Add toy hardened agent
- Add local demo instructions

## v0.1.0: Incubator baseline release

Goal: publish a usable OWASP Incubator baseline.

Planned work:

- Stabilize scenario format draft
- Stabilize JSON result output
- Add CI example
- Add at least 5 security scenarios
- Add contributor guide for scenarios
- Add initial project documentation