# OWASP Agent Security Regression Harness

The OWASP Agent Security Regression Harness is an open source, vendor-neutral test harness for running executable security regression scenarios against agentic applications and MCP-integrated systems.

The project helps builders and defenders verify that changes to prompts, models, tools, retrieval sources, memory, approval flows, or MCP integrations do not reintroduce known security failures.

## What this project does

This project provides a code-first harness for:

- Running reproducible agent security abuse-case scenarios
- Validating expected security outcomes with policy assertions
- Producing machine-readable results for local development and CI
- Capturing execution traces for debugging and auditability
- Building a reusable scenario library for agent and MCP security risks

## What this project is not

This project is not:

- A benchmark
- A scanner
- A leaderboard
- A replacement for threat modeling
- A generic AI safety evaluation suite
- A guarantee that an agentic system is secure

It is a regression harness. Its job is to help teams catch known classes of agent security failures before they ship.

## Current status

This project is in early Incubator development.

The first milestone is a minimal CLI that can:

1. Load a scenario file
2. Execute it against a target agent endpoint
3. Evaluate policy assertions
4. Emit pass/fail JSON output

## Usage

Validate a scenario and emit a result without executing a target.

```bash
agent-harness run path/to/scenario.yaml --dry-run
```

Evaluate assertions against a pre-recorded execution trace.

```bash
agent-harness run path/to/scenario.yaml --trace-file path/to/trace.json
```

Add `--out path/to/result.json` to either command to write the result JSON to a file instead of stdout.
