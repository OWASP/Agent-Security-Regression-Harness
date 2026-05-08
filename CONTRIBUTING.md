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

### Policy

AI-assisted contributions are allowed, but they must be disclosed.

Contributors remain responsible for every line they submit. Do not submit AI-generated code, documentation, tests, or scenarios that you do not understand, cannot explain, or have not tested.

If AI tools such as Claude Code, ChatGPT, GitHub Copilot, Cursor, or similar tools were used to generate or substantially modify a contribution, disclose that use in the pull request description.

### Disclosure

The disclosure should include:

- The tool used
- What parts of the contribution were AI-assisted
- How the contributor reviewed the output
- The tests or checks that were run

AI tools should not be listed as the sole responsible author. The human submitter remains accountable for the contribution.

### What maintainers may do

Maintainers may request changes or close pull requests that:

- Appear to be unreviewed generated output
- Are too large to review safely
- Cannot be explained by the human contributor

To keep review quality high, prefer small and focused pull requests.
