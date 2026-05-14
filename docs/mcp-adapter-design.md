# MCP Adapter Design

Status: design basis for MCP adapter work. An MVP workflow adapter now exists
in `src/agent_harness/mcp_adapter.py`; fuller MCP host/runtime support remains
future work.

This document defines the design constraints for a native Model Context
Protocol (MCP) adapter before adding code. MCP is not just another
tool-calling framework: it introduces a protocol boundary between an agent
host, MCP clients, MCP servers, tools, prompts, resources, roots, sampling,
authorization, and transports. The harness must preserve those boundaries in
its trace model.

## Goals

- Add a design for a future `mcp` adapter without implementing it yet.
- Preserve MCP server identity in traces and assertions.
- Treat MCP servers, resources, prompts, tool descriptions, tool results, and
  server-initiated requests as data crossing a trust boundary.
- Keep scenarios framework-neutral and keep runtime secrets, local commands,
  and credentials out of scenario YAML.
- Keep the harness assertion engine independent of MCP SDK objects.
- Keep MCP dependencies optional through the existing `mcp` extra.

## MVP Non-goals

- Do not make the harness a general-purpose MCP host yet.
- Do not add a new assertion language in the MVP adapter implementation.
- Do not require external MCP servers or network access in tests.
- Do not treat MCP tool annotations or server-provided metadata as proof of
  safety.

## MCP Model To Preserve

MCP uses a host/client/server architecture:

- The host is the AI application or agent runtime.
- The host creates one MCP client per MCP server connection.
- Each MCP server exposes capabilities such as tools, resources, and prompts.
- Clients may expose capabilities such as roots, sampling, and elicitation.
- The protocol uses JSON-RPC 2.0 messages and a lifecycle with initialization,
  capability negotiation, operation, and shutdown.
- Current standard transports include `stdio` and Streamable HTTP.

The harness adapter must not flatten this model into anonymous tool calls. Two
different MCP servers can expose a tool with the same name, and a server can
provide resources or prompts that affect agent behavior without being a tool
call. Server identity is therefore part of the security evidence.

## Adapter Role

The future MCP adapter should still follow the existing harness rule:

```text
Scenario -> Adapter -> Trace -> Assertions -> HarnessResult
```

The adapter is responsible for running a scenario against an MCP-connected
target and translating observed MCP behavior into a harness `Trace`.

The adapter should be an observation and execution bridge. It should not decide
whether the run passed or failed, rewrite scenario policy, or mark a server as
safe because it supplied a friendly name, description, icon, annotation, or
prompt.

## Runtime Configuration

Scenario files should describe expected security behavior. Runtime details
should be supplied explicitly by CLI flags, a local runtime config file, or a
Python API.

Scenario YAML may reference stable MCP server IDs when a scenario's security
policy depends on server identity:

```yaml
target:
  adapter: mcp
  required_servers:
    - filesystem_fixture

expected:
  denied_tools:
    - mcp/filesystem_fixture/delete_file
```

Runtime configuration should provide launch and connection details:

```yaml
mcp_servers:
  - id: filesystem_fixture
    transport: stdio
    command: python
    args:
      - -m
      - examples.mcp_servers.filesystem_fixture
    trust: untrusted
    roots:
      - file:///workspace/fixtures/mcp-filesystem
```

Runtime configuration may contain credentials, process commands, environment
names, and network endpoints. These values should not be required in portable
scenario files.

## Server Identity

Every MCP server connection must have a stable harness-assigned `server_id`.

The `server_id`:

- Is required in runtime configuration.
- Must be unique within a scenario run.
- Should use a small stable identifier such as `github_prod`,
  `filesystem_fixture`, or `sentry_readonly`.
- Must not be derived solely from `serverInfo.name`, tool names, display
  titles, descriptions, icons, or any other server-supplied field.

The adapter should also record server-reported identity from the MCP
`initialize` response as evidence:

- `server_name`
- `server_title`
- `server_version`
- `protocol_version`
- negotiated server capabilities

Server-reported identity is useful for debugging but is not an authorization
boundary. The configured `server_id` is the identity used by harness traces and
scenario policy.

## Trust Model

Each configured MCP server should have an explicit trust label. Initial labels
can be intentionally small:

- `trusted`
- `untrusted`
- `third_party`
- `internal`

The adapter should record this label in connection events and propagate it to
tool, resource, prompt, and sampling events.

Trust is attached to the server connection, not to an individual tool
description. A trusted server can still return untrusted user-controlled data,
and an untrusted server can expose a benign-looking tool. The adapter should
preserve both:

- The configured trust label for the server.
- The source and content type of data crossing from the server into the agent.

## Tool Naming

MCP tool names are unique only within a server. The harness trace should use a
canonical tool name that includes the server ID:

```text
mcp/<server_id>/<tool_name>
```

Example trace entry:

```json
{
  "name": "mcp/filesystem_fixture/delete_file",
  "arguments": {
    "path": "/workspace/fixtures/notes.txt"
  },
  "mcp_server_id": "filesystem_fixture",
  "mcp_tool_name": "delete_file",
  "mcp_method": "tools/call",
  "trust": "untrusted"
}
```

The `name` field remains compatible with the existing
`no_denied_tool_call` assertion because scenarios can deny the exact canonical
tool name. The MCP-specific fields keep the original protocol identity
available for future assertions.

The adapter should not record only the raw MCP tool name, because `delete_file`
from one server is not equivalent to `delete_file` from another server.

## Trace Events

The adapter should use the existing `Trace` shape:

```json
{
  "messages": [],
  "tool_calls": [],
  "events": []
}
```

MCP-specific facts should be recorded as structured `events`. Recommended
initial event types:

| Event type | Purpose |
|---|---|
| `mcp_connection_initialized` | A server connection completed lifecycle initialization. |
| `mcp_capabilities_negotiated` | Client and server capabilities selected for the session. |
| `mcp_tools_discovered` | The adapter observed tools from `tools/list`. |
| `mcp_resource_read` | The agent or host read a server resource. |
| `mcp_prompt_get` | The agent or host retrieved a server prompt. |
| `mcp_tool_result` | A server returned a tool result or tool execution error. |
| `mcp_client_request` | A server requested a client-side feature such as roots, sampling, or elicitation. |
| `mcp_policy_decision` | The adapter allowed or denied an MCP action because of harness configuration. |
| `mcp_connection_closed` | The connection shut down or failed. |

Example connection event:

```json
{
  "type": "mcp_connection_initialized",
  "id": "filesystem_fixture",
  "server_id": "filesystem_fixture",
  "transport": "stdio",
  "trust": "untrusted",
  "protocol_version": "2025-11-25",
  "server_name": "fixture-filesystem",
  "server_version": "0.1.0",
  "capabilities": {
    "tools": {
      "listChanged": true
    },
    "resources": {}
  }
}
```

Example resource event:

```json
{
  "type": "mcp_resource_read",
  "server_id": "filesystem_fixture",
  "trust": "untrusted",
  "uri": "file:///workspace/fixtures/injected.md",
  "mime_type": "text/markdown",
  "content_truncated": true
}
```

MVP workflow results may supply these observations through a top-level
`mcp_events` list. The adapter normalizes the first reviewable event set:

- `mcp_resource_read`: requires `server_id` and `uri`, and defaults
  `mcp_method` to `resources/read`.
- `mcp_prompt_get`: requires `server_id` and a prompt name from
  `mcp_prompt_name`, `prompt_name`, `params.name`, or `name`, and defaults
  `mcp_method` to `prompts/get`.
- `mcp_tool_result`: requires `server_id` plus a tool name, or a canonical
  `name` such as `mcp/filesystem_fixture/read_file`; the normalized event
  includes `mcp_tool_name`, canonical `name`, and `mcp_method: tools/call`.
- `mcp_policy_decision`: requires `server_id` and `decision`.

For every server-scoped MCP event, the adapter adds known `trust`, `transport`,
server identity, and protocol-version metadata from the matching `mcp_servers`
entry when the event does not already provide it.

The adapter should avoid dumping large binary payloads into traces by default.
It may record content type, URI, byte length, hashes, short text excerpts, and a
`content_truncated` flag. Redaction rules should be configurable before
capturing full resource or tool-result contents.

## Client Capabilities

The first implementation should expose the minimum client capabilities needed
for the tested scenario. It should default to conservative behavior:

- `roots`: expose no roots unless configured.
- `sampling`: deny server-initiated sampling unless explicitly enabled for the
  server.
- `elicitation`: deny server-initiated user input unless explicitly enabled.
- `tasks` and experimental capabilities: disabled unless an implementation
  phase explicitly adds them.

Denied server-initiated requests should be recorded as `mcp_policy_decision`
events. This is useful evidence for MCP trust-boundary scenarios.

Example denied sampling event:

```json
{
  "type": "mcp_policy_decision",
  "id": "sampling_denied",
  "server_id": "untrusted_retrieval",
  "method": "sampling/createMessage",
  "decision": "deny",
  "reason": "sampling is disabled for this server"
}
```

## Authorization And Transport Boundaries

For `stdio` servers:

- Treat the child process as part of the test environment but not necessarily
  trusted.
- Record the configured `server_id`, transport, command basename, and redacted
  environment names.
- Do not place secrets or full environment values in traces.
- Terminate child processes during adapter cleanup.

For Streamable HTTP servers:

- Require explicit server URLs from runtime configuration.
- Record the URL origin, not credentials.
- Send the negotiated MCP protocol version header after initialization.
- Do not follow redirects to a different origin unless explicitly configured.
- Keep authentication tokens scoped to the intended MCP server.
- Do not pass through tokens issued for some other service as if they were MCP
  server tokens.

HTTP metadata discovery and OAuth flows can create SSRF and confused-deputy
risks. The adapter should support allowlists for hosts, schemes, and redirect
behavior before enabling remote MCP servers in tests.

## Policy Mapping

The first adapter can rely on existing assertions by emitting canonical tool
names in `tool_calls`.

Later MCP-specific assertions can add more precise policy:

- Deny a tool only when called through a specific `server_id`.
- Deny all tools from servers with `trust: untrusted`.
- Fail when an untrusted server supplies a prompt that becomes an assistant or
  system instruction.
- Fail when a server requests sampling, roots, or elicitation outside its
  configured permission set.
- Fail when a resource from an untrusted server is treated as instruction.

These future assertions should read structured trace fields. They should not
parse display strings or depend on MCP SDK objects.

## Error Handling

Adapter failures should raise `AdapterError`, consistent with existing
adapters.

Failures include:

- Missing optional MCP dependency.
- Invalid runtime MCP configuration.
- Duplicate `server_id` values.
- Unsupported transport.
- Failed lifecycle initialization.
- Protocol version mismatch.
- Required capability negotiation failure.
- Request timeout.
- Malformed JSON-RPC message.
- MCP SDK exception.
- Trace conversion failure.

The CLI should display clear installation guidance for missing dependencies,
for example:

```text
MCP adapter dependencies are not installed.
Install them with: python -m pip install "owasp-agent-security-regression-harness[mcp]"
```

## Test Strategy

MCP adapter tests should not require API keys, real model calls, third-party
servers, or network access to external services.

Recommended tests:

- In-process fake MCP servers for tool listing, tool calls, resource reads, and
  prompt retrieval.
- Local stdio fixture servers for lifecycle and cleanup behavior.
- Local HTTP fixture servers only when testing Streamable HTTP behavior.
- Fake target agents that deterministically call MCP tools.
- Assertions that server identity is preserved when two servers expose the same
  tool name.
- Tests that untrusted resource and prompt events include `server_id` and
  `trust`.
- Tests that sampling, roots, and elicitation are denied by default and traced.
- Tests that optional dependency errors include the install hint.

The first implementation should prefer stdio fixture coverage before remote
HTTP coverage because stdio is easier to run deterministically in CI.

## Implementation Phases

1. Add MCP trace conventions and tests around canonical tool names.
2. Add runtime configuration parsing for MCP server definitions.
3. Add a minimal stdio MCP client adapter that can initialize servers, list
   tools, call tools through a deterministic fake target, and emit traces.
4. Add resource and prompt tracing.
5. Add default-deny handling for roots, sampling, and elicitation.
6. Add Streamable HTTP support with origin allowlists and redacted auth
   handling.
7. Add MCP-specific assertions after trace conventions are stable.

## References

- MCP architecture overview:
  https://modelcontextprotocol.io/docs/learn/architecture
- MCP specification overview, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/basic
- MCP lifecycle specification, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle
- MCP transports specification, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- MCP tools specification, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- MCP resources specification, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/server/resources
- MCP prompts specification, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/server/prompts
- MCP roots specification, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/client/roots
- MCP sampling specification, version 2025-11-25:
  https://modelcontextprotocol.io/specification/2025-11-25/client/sampling
- MCP security best practices:
  https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
  
