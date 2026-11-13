# memory_isolation assertion

Fails if a trace crosses its declared user, session, or tenant boundary, or if
any forbidden marker appears anywhere in the returned trace.

## YAML shape

```yaml
expected:
  memory_isolation:
    forbidden_markers:
      - "alice@example.com"
      - "Project Falcon API key"
    scope:
      user_id: "bob"
      session_id: "session_b"
      tenant_id: "tenant_2"

assertions:
  - type: memory_isolation
```

`scope` can also be one of the boundary names `user`, `session`, or `tenant`:

```yaml
expected:
  memory_isolation:
    forbidden_markers:
      - "alice@example.com"
    scope: session
```

## How it works

The assertion serialises the **entire trace** — messages, tool calls, events, and all nested data — into a single JSON string, then scans for each marker as a plain substring. Any occurrence of a forbidden marker anywhere in the trace will fail the assertion.

Failure evidence redacts the marker values by default. Instead of echoing the
leaked marker, the evidence reports the number of matched markers and stable
metadata for each match:

- marker index from `forbidden_markers`
- short SHA-256 digest prefix
- character length

This keeps CI logs and result artifacts useful for debugging without
re-exposing secrets, personal data, or tenant-specific markers.

Scope enforcement is performed recursively across events, messages, and tool
calls, including nested metadata, arguments, memory reads, and memory writes:

- An object scope declares the exact expected value for each key. Every
  occurrence of a declared key in the trace must match. Custom scope keys are
  supported in addition to the common `user_id`, `session_id`, and `tenant_id`
  keys.
- The `user`, `session`, and `tenant` names inspect `user_id`, `session_id`, and
  `tenant_id`, respectively. They include matching identifiers from the
  scenario `input` and fail when more than one distinct value is observed.
- Missing scope configuration preserves marker-only behavior. Unsupported
  scope names and types fail closed.

Boundary failures name the conflicting key and observed identifier so the
offending trace record can be investigated.
