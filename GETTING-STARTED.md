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
Copy all files from `templates/` into your system folder and fill them through interview + validation.

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

Then verify content quality:
- a new engineer can identify owner, criticality, and architecture quickly;
- on-call can execute first-response steps from docs;
- key dependencies and risk constraints are explicit;
- open questions are tracked with owner + next step.

## 5) Integrate into workflows
Use guides in `wiring/` to consume the portfolio in MCP resources, service catalogs, AI system prompts, context packs, and operations workflows.
