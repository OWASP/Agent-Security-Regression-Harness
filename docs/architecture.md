# Architecture

The harness has five core concepts:

## Scenario

A scenario defines a security regression test.

It includes:

- Scenario metadata
- Target configuration
- Input messages or context
- Expected constraints
- Assertions

## Runner

The runner loads a scenario, sends it to a target adapter, collects execution data, and passes that data to the assertion engine.

## Adapter

An adapter connects the harness to a target agent system.

Initial adapters should be simple and generic. The first planned adapter is a generic HTTP adapter.

## Trace

A trace records what happened during execution.

A trace may include:

- Messages
- Tool calls
- Tool outputs
- Approval events
- Retrieved context
- Memory operations
- MCP interactions

## Assertion engine

The assertion engine evaluates whether security expectations held.

Initial assertions should include:

- No denied tool call occurred
- No sensitive data was disclosed
- Required approval was enforced
- Expected goal was preserved