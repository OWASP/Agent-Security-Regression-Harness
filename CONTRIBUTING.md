# Contributing to OWASP Agent Security Regression Harness

Thank you for your interest in contributing.

This project is building a practical regression harness for executable agent security abuse cases. Contributions should make the harness more usable, more reproducible, or more useful to defenders and builders.

## Good first contributions

Good first contributions include:

- Adding a new scenario under `scenarios/`
- Improving documentation under `docs/`
- Adding examples for CI usage
- Adding tests for the scenario parser
- Proposing assertion types
- Improving error messages
- Building a toy vulnerable agent for demos

## Project scope

Before opening a large pull request, read:

- `docs/scope.md`
- `docs/non-goals.md`
- `docs/scenario-spec.md`

Large, unfocused additions will be rejected. This project is intentionally narrow.

## Development workflow

1. Fork the repository
2. Create a feature branch
3. Make a small, reviewable change
4. Add or update tests where applicable
5. Open a pull request

Use clear branch names:

```text
scenario/goal-hijack-basic
docs/scenario-spec
feature/http-agent-adapter
fix/result-json-output
```

## AI-assisted contributions

AI-assisted contributions are allowed, but they must be disclosed.

This is a security-focused OWASP project. Human contributors remain
responsible for every line they submit, including code, documentation,
tests, and scenarios.

Do not submit AI-generated output that you do not understand, cannot
explain, or have not tested.

If you used AI tooling such as Claude Code, ChatGPT, GitHub Copilot,
Cursor, or similar tools to generate or substantially modify your
contribution, disclose it in your pull request description.

Your disclosure should include:

- The tool(s) used
- What parts were AI-assisted
- How you reviewed the output
- What tests/checks you ran

AI tools must not be listed as the sole responsible author. The human
submitter remains accountable.

Maintainers may request changes or close pull requests that appear to
be unreviewed generated output, are too large to review safely, or
cannot be explained by the human submitter.

To keep review quality high, prefer small and focused pull requests.

### Suggested PR disclosure format

If AI assistance was used, include a section like this in your PR body:

```markdown
## AI assistance disclosure

- Tools used: <tool names>
- AI-assisted areas: <files/sections>
- Human review performed: <how you reviewed and validated>
- Tests/checks run: <commands or CI checks>
```