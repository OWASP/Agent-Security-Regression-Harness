# Non-goals

This project will stay useful only if it stays focused.

The following are non-goals:

## Not a benchmark

This project does not rank models, vendors, frameworks, or agents.

## Not a scanner

This project does not automatically discover every vulnerability in an agentic system.

## Not a generic AI safety suite

This project focuses on security regression behavior in agentic systems, especially tool use, data access, approval flows, memory, and MCP trust boundaries.

## Not a replacement for threat modeling

The harness helps teams test known abuse cases. It does not replace architecture review, threat modeling, secure design, or manual security assessment.

## Not vendor-specific

The harness should remain model-neutral, vendor-neutral, and framework-neutral.

Vendor or framework integrations may exist, but they must not define the core architecture.

## Not dependent on subjective model judgment

Assertions should be deterministic where possible. LLM-as-judge patterns may be explored later, but they must not become the foundation of the project.