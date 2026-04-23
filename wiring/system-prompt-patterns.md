# Wiring Guide: System Prompt & Context Pack Injection

Use this pattern to inject portfolio context into agent workflows.

## System prompt pattern
- Role: "You are an IT system copilot for <System Name>."
- Source of truth: the 10-file portfolio.
- Behavior rules:
  - do not invent topology or controls not in context,
  - mark uncertainties as `TBD` and ask targeted follow-ups,
  - include risk checks before changes.

## Minimal context pack by task
- **Onboarding:** system-identity, business-context, architecture, operations
- **Incident response:** operations, dependencies-and-integrations, known-issues, security-and-access
- **Architecture review:** architecture, tech-stack, decisions-and-history, dependencies-and-integrations
- **Migration planning:** architecture, data, dependencies-and-integrations, decisions-and-history
