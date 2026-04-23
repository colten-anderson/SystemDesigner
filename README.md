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
- `examples/` — sample portfolios (Exchange Online, OneDrive, NinjaOne RMM, Customer Billing API, Snowflake Analytics Platform).
- `wiring/` — implementation patterns for consuming context in tools and workflows.
- `scripts/` — helper utilities such as portfolio scaffolding and structure validation.

## Quick start (5 minutes)
1. Pick a system and create a folder for it.
2. Scaffold all template files into that folder.
3. Run the interview in `interview-protocol/agent-system-prompt.md` and fill each file.
4. Validate your folder structure and placeholders.
5. Use the wiring docs to connect the portfolio into your AI/dev workflows.

For full onboarding, see [GETTING-STARTED.md](GETTING-STARTED.md).

## Example workflow
```bash
# 1) Scaffold a new portfolio from templates
python scripts/create_portfolio.py ./my-system

# 2) Start from a reference example (optional)
cp -R examples/exchange-online ./my-system

# 3) Adapt content to your real system
$EDITOR my-system/*.md

# 4) Validate required files
python scripts/validate_portfolio.py my-system

# 5) Optional strict mode (flags placeholders)
python scripts/validate_portfolio.py my-system --strict

# 6) Validate every portfolio in a parent directory
python scripts/validate_portfolio.py examples --all

# 7) Export machine-readable results
python scripts/validate_portfolio.py examples --all --json
```

## Better example patterns (copy/paste starters)
Use these when replacing template placeholders so your portfolio becomes immediately actionable.

### `system-identity.md` (good level of specificity)
- **System:** Exchange Online (US tenant)
- **Primary owner:** Messaging Platform Team (`messaging-platform@company.com`)
- **Escalation path:** Service Desk → Messaging On-Call → M365 Architect
- **SLA / criticality:** Tier 0, 99.9% availability target

### `operations.md` (incident-first runbook examples)
- **P1 symptom:** Users cannot send external mail.
- **First 10 minutes:** Check Microsoft 365 Service Health, verify recent transport rule changes, compare impact by region.
- **Rollback action:** Disable last modified transport rule and re-test with synthetic mailbox.
- **Escalate when:** >20% impacted users or no mitigation within 30 minutes.

### `dependencies-and-integrations.md` (dependency mapping example)
| Dependency | Type | Why it matters | Owner | Failure impact |
|---|---|---|---|---|
| Entra ID Connect | Identity sync | User/mailbox identity consistency | IAM Team | New accounts fail to provision |
| SMTP relay appliance | Mail flow | Legacy app email delivery | Network Team | Application alerts are dropped |
| SIEM connector | Security monitoring | Audit/event ingestion | SecOps | Delayed detection and compliance gaps |

### `known-issues-and-constraints.md` (risk statement example)
- **Constraint:** Shared tenant throttling cannot be disabled.
- **Operational effect:** Bulk migration windows are capped and must be staged.
- **Current mitigation:** Batch size limits + off-peak scheduling.
- **Follow-up owner/date:** Messaging Platform Team — review quarterly.

## Validation helper
Run the validator script against any portfolio folder to confirm required files and optionally flag placeholders:

```bash
python scripts/create_portfolio.py ./my-system
python scripts/validate_portfolio.py examples/exchange-online
python scripts/validate_portfolio.py examples/exchange-online --strict
python scripts/validate_portfolio.py examples --all --json
```

## Core principles
- **One system per portfolio**.
- **Humans and AI are equal audience**.
- **Practical operations detail over generic narrative**.
- **Explicit unknowns with follow-up owners**.
- **Consistent file set across system modes**.

## User experience improvements (practical defaults)
If you want a smoother experience for both first-time contributors and daily operators, start here:

1. **Reduce blank-page anxiety**
   - Pre-fill templates with one realistic sample row or bullet per section.
   - Add "minimum acceptable content" guidance directly below each heading.

2. **Optimize for time-to-first-value (15 minutes)**
   - Prioritize identity, ownership, escalation, and incident-first operations content before deep architecture details.
   - Use strict validation only after the first complete pass to avoid early friction.

3. **Design for incident usage, not documentation beauty**
   - Keep "first 10 minutes" checks visible and scannable.
   - Prefer concise tables for dependencies and impact over long prose.

4. **Create visible progress and confidence**
   - Track completion state per file (draft / reviewed / production-ready).
   - Record unknowns with owner and follow-up date so users know what is intentionally incomplete.

5. **Shorten onboarding loops**
   - Start each new system from the closest example in `examples/`.
   - Add a quick peer review checklist (owner clarity, runbook usability, dependency impact, risk explicitness).

For a ready-to-run checklist, see [UX-CHECKLIST.md](UX-CHECKLIST.md).
