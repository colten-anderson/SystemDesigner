# IT System Context Portfolio

A markdown-first framework for documenting **one IT system** so both **AI agents** and **human engineers** can work effectively across onboarding, operations, incident response, audits, migrations, and architecture review.

## What this is
This repository provides:
- a mode-aware interview prompt for capturing system context,
- a fixed portfolio file set for consistent output,
- examples for real enterprise SaaS systems,
- wiring guides for feeding the portfolio into AI and engineering workflows.

## Core principles
- **One system per portfolio**.
- **Humans and AI are equal audience**.
- **Practical operations detail over generic narrative**.
- **Explicit unknowns with follow-up owners**.
- **Consistent file set across system modes**.

## Supported system modes
The interview starts with a required mode picker:
- A. Configured enterprise SaaS
- B. In-house application
- C. Shared platform / infrastructure service
- D. Data system
- Other / mixed

Mode changes emphasis, not file names.

## Portfolio file set
1. `system-identity.md`
2. `business-context.md`
3. `architecture.md`
4. `tech-stack.md`
5. `dependencies-and-integrations.md`
6. `data.md`
7. `security-and-access.md`
8. `operations.md`
9. `known-issues-and-constraints.md`
10. `decisions-and-history.md`

## Repository layout
- `interview-protocol/` — central interviewer system prompt
- `templates/` — baseline markdown templates for each portfolio file
- `examples/` — sample portfolios (Exchange Online, OneDrive, NinjaOne RMM)
- `wiring/` — implementation patterns for consuming context in tools and workflows

## Quick start
See [GETTING-STARTED.md](GETTING-STARTED.md).

## Validation helper
Run the validator script against any portfolio folder to quickly confirm required files and optionally flag placeholders:

```bash
python scripts/validate_portfolio.py examples/exchange-online
python scripts/validate_portfolio.py examples/exchange-online --strict
```

