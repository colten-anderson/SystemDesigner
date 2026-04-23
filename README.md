# IT System Context Portfolio

A markdown-first framework for documenting **one IT system** so both **AI agents** and **human engineers** can work effectively across onboarding, operations, incident response, audits, migrations, and architecture reviews.

## Why this repository is useful
Most system documentation is either too high-level for operations or too fragmented for AI tools.
This repo gives you a **single, repeatable portfolio shape** that works for both.

Use it to:
- onboard new engineers faster,
- reduce repeated Q&A during incidents,
- hand high-quality context to AI agents,
- capture architecture decisions and known risks in one place.

## What you get
- A **mode-aware interview protocol** to extract context consistently.
- A **fixed 10-file portfolio structure** so every system is documented the same way.
- **Practical templates** with prompts that drive specific, actionable content.
- **Reference examples** for enterprise SaaS systems.
- **Wiring guides** for feeding the resulting docs into prompts, MCP resources, and integration layers.

## Supported system modes
The interview starts with a required mode picker:
- A. Configured enterprise SaaS
- B. In-house application
- C. Shared platform / infrastructure service
- D. Data system
- Other / mixed

Mode changes emphasis, not file names.

## Portfolio file set (required)
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
- `interview-protocol/` — central interviewer system prompt.
- `templates/` — baseline markdown templates for each portfolio file.
- `examples/` — sample portfolios (Exchange Online, OneDrive, NinjaOne RMM).
- `wiring/` — implementation patterns for consuming context in tools and workflows.
- `scripts/` — helper utilities such as structure validation.

## Quick start (5 minutes)
1. Pick a system and create a folder for it.
2. Copy all files from `templates/` into that folder.
3. Run the interview in `interview-protocol/agent-system-prompt.md` and fill each file.
4. Validate your folder structure and placeholders.
5. Use the wiring docs to connect the portfolio into your AI/dev workflows.

For full onboarding, see [GETTING-STARTED.md](GETTING-STARTED.md).

## Example workflow
```bash
# 1) Start from a reference example
cp -R examples/exchange-online ./my-system

# 2) Adapt content to your real system
$EDITOR my-system/*.md

# 3) Validate required files
python scripts/validate_portfolio.py my-system

# 4) Optional strict mode (flags placeholders)
python scripts/validate_portfolio.py my-system --strict
```

## Validation helper
Run the validator script against any portfolio folder to confirm required files and optionally flag placeholders:

```bash
python scripts/validate_portfolio.py examples/exchange-online
python scripts/validate_portfolio.py examples/exchange-online --strict
```

## Core principles
- **One system per portfolio**.
- **Humans and AI are equal audience**.
- **Practical operations detail over generic narrative**.
- **Explicit unknowns with follow-up owners**.
- **Consistent file set across system modes**.
