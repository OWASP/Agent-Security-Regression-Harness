# Scope

The OWASP Agent Security Regression Harness provides a repeatable way to test whether agentic systems preserve expected security properties after changes.

The project focuses on:

- Executable abuse-case scenarios
- Regression testing
- Agent tool-use security
- MCP trust boundary testing
- Policy assertions
- Execution traces
- Machine-readable output
- Local and CI workflows

The project is intended for:

- Application security engineers
- AI platform teams
- Red teams
- Developers building agentic applications
- Teams adopting MCP-connected systems

## Primary use case

A team changes something in an agentic system, such as:

- Prompt instructions
- Model configuration
- Tool permissions
- Retrieval sources
- Memory behavior
- Approval flow logic
- MCP server integration

The team then runs this harness to check whether known security controls still hold.