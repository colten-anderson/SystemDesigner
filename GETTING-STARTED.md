# Getting Started

## 1) Choose one IT system
Create a folder for a single system portfolio (example: `portfolios/exchange-online/`).

## 2) Start with the interviewer prompt
Use `interview-protocol/agent-system-prompt.md` as your agent system prompt.

The interviewer must begin with the mode picker:
- A. Configured enterprise SaaS
- B. In-house application
- C. Shared platform / infrastructure service
- D. Data system
- Other / mixed

## 3) Populate the 10 baseline files
Scaffold template files into your system folder, then fill them through interview + validation.

```bash
python scripts/create_portfolio.py portfolios/<system-name>
```

If you rerun this command, existing files are preserved by default. Use `--force` to overwrite files.

Required files:
- `system-identity.md`
- `business-context.md`
- `architecture.md`
- `tech-stack.md`
- `dependencies-and-integrations.md`
- `data.md`
- `security-and-access.md`
- `operations.md`
- `known-issues-and-constraints.md`
- `decisions-and-history.md`

## 4) Validate portfolio quality
Before calling the portfolio complete, run a structural check:

```bash
python scripts/validate_portfolio.py portfolios/<system-name>
```

Use strict mode to fail if placeholder text remains:

```bash
python scripts/validate_portfolio.py portfolios/<system-name> --strict
```

Validate multiple portfolios at once by pointing to a parent folder and adding `--all`:

```bash
python scripts/validate_portfolio.py portfolios --all
```

If you need to integrate validation into CI pipelines, add `--json` for machine-readable output:

```bash
python scripts/validate_portfolio.py portfolios --all --json
```

Then verify content quality:
- a new engineer can identify owner, criticality, and architecture quickly;
- on-call can execute first-response steps from docs;
- key dependencies and risk constraints are explicit;
- open questions are tracked with owner + next step.

## 5) Integrate into workflows
Use guides in `wiring/` to consume the portfolio in MCP resources, service catalogs, AI system prompts, context packs, and operations workflows.

## 6) Improve user experience as you scale
Use [UX-CHECKLIST.md](UX-CHECKLIST.md) to reduce onboarding friction and improve incident usability as more teams adopt the portfolio pattern.

## Quick quality examples (what "good" looks like)
Use the patterns below to increase signal quality while filling templates:

- **Owner fields:** Prefer a named team plus a routable alias (for example, `Identity Platform Team` + `identity-platform@company.com`) instead of a single person.
- **Runbooks:** Include trigger, first checks, rollback, and escalation threshold (for example, "rollback if no recovery in 15 minutes").
- **Dependencies:** Document both technical dependency and business impact (for example, "if SSO fails, external customers cannot access billing portal").
- **Known issues:** Track mitigation status and next review date, not just the problem statement.
- **Decisions:** Record alternatives considered and why they were rejected.

If unsure, start from the closest portfolio in `examples/` and rewrite each section with your system's real owners, tooling, and constraints.
