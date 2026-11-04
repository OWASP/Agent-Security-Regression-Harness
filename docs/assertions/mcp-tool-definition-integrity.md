# mcp_tool_definition_integrity assertion

Fail if a pinned MCP tool definition changes without re-approval.

This catches an MCP rug-pull: the server advertises a tool, the operator or
harness pins that `description` and `inputSchema`, and a later `tools/list`
rewrites either field while keeping the tool name. `no_denied_tool_call`
does not see that change, because the canonical tool name is unchanged.

## YAML shape

```yaml
assertions:
  - type: mcp_tool_definition_integrity
```

The assertion has no extra fields. It reads `mcp_tools_discovered` events
already recorded in the trace.

## How it works

The first discovery of a `(server_id, tool name)` pair is the pin. A later
discovery fails when the canonical digest of `name`, `description`, and
`inputSchema` differs. `inputSchema` wins over `input_schema`. Object key
order does not affect the digest.

A drift is allowed only when an earlier event re-approves the new digest:

```json
{
  "type": "mcp_tool_definition_approved",
  "server_id": "lookup_fixture",
  "tool_name": "lookup_status",
  "definition_digest": "sha256:...",
  "decision": "approved"
}
```

The approval must appear before the drifted discovery. An approval after the
drift, a `denied` decision, a different tool, or a different digest does not
count. A `mcp_tool_definition_drift` event fails on its own: the unapproved
mutation was already observed.

A trace with no `mcp_tools_discovered` events fails. The assertion cannot
treat a missing catalog as a preserved pin.

The MCP host applies the same digest before each `tools/call`. If the live
`tools/list` disagrees with the initialization pin, or the re-list fails, the
host refuses the call.
