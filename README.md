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

## Complete functionality overview
This repository includes end-to-end capabilities for **creating**, **filling**, **validating**, **reviewing**, and **operationalizing** system portfolios:

1. **Standardized portfolio model**
   - Fixed 10-file schema with shared naming for every system mode.
   - Mode-aware interviewing so depth and emphasis adapt by system type.

2. **Template-driven authoring**
   - Ready-to-copy markdown templates with expected output fields.
   - Placeholder patterns intentionally detectable by the validator.

3. **Guided elicitation workflow**
   - A dedicated interviewer prompt (`interview-protocol/agent-system-prompt.md`) to run structured discovery sessions.

4. **Portfolio scaffolding CLI** (`scripts/create_portfolio.py`)
   - Creates a new portfolio directory from templates.
   - Supports dry-run previews and force-overwrite behavior.
   - Supports custom template directories.

5. **Portfolio validation CLI** (`scripts/validate_portfolio.py`)
   - Checks required file presence.
   - Detects placeholder text.
   - Scores content quality (0-100) using section coverage, field completion, and content length.
   - Supports strict placeholder enforcement.
   - Supports parent-folder batch validation.
   - Supports filtering to only likely portfolios during batch mode.
   - Supports JSON output for machine-readable CI automation.
   - Supports minimum quality gates.
   - Supports markdown report generation.
   - Supports freshness checks from ISO dates and stale-fact thresholds.
   - Supports warning-to-failure mode for stricter CI policies.

6. **Integration/wiring patterns**
   - Patterns for OpenClaw agents, API-layer usage, MCP resources, Claude Projects, and system prompt composition.

7. **Reference implementations**
   - Complete sample portfolios for Exchange Online, OneDrive, NinjaOne RMM, Customer Billing API, and Snowflake Analytics Platform.

8. **Quality and UX aids**
   - `GETTING-STARTED.md` for first-pass onboarding.
   - `UX-CHECKLIST.md` for practical documentation quality and operator usability.
   - Automated tests for scaffold and validation scripts (`tests/`).

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
- `tests/` — script-level tests for scaffold and validation behavior.

## Quick start (5 minutes)
1. Pick a system and create a folder for it.
2. Scaffold all template files into that folder.
3. Run the interview in `interview-protocol/agent-system-prompt.md` and fill each file.
4. Validate your folder structure and placeholders.
5. Use the wiring docs to connect the portfolio into your AI/dev workflows.

For full onboarding, see [GETTING-STARTED.md](GETTING-STARTED.md).

## CLI usage

### 1) Create portfolio scaffold
```bash
# Create a new portfolio from repository templates
python scripts/create_portfolio.py ./my-system

# Preview scaffold operations without writing files
python scripts/create_portfolio.py ./my-system --dry-run

# Overwrite existing files in destination
python scripts/create_portfolio.py ./my-system --force

# Use a custom template source
python scripts/create_portfolio.py ./my-system --templates-dir ./templates
```

### 2) Validate portfolio quality and completeness
```bash
# Basic validation for one portfolio
python scripts/validate_portfolio.py my-system

# Fail if placeholder content is present
python scripts/validate_portfolio.py my-system --strict

# Validate all immediate subfolders under a parent directory
python scripts/validate_portfolio.py examples --all

# In mixed parent directories, only evaluate folders that look like portfolios
python scripts/validate_portfolio.py . --all --only-portfolios

# Emit JSON for CI and machine processing
python scripts/validate_portfolio.py examples --all --json

# Enforce minimum quality score
python scripts/validate_portfolio.py examples --all --quality-gate 80

# Write markdown review report
python scripts/validate_portfolio.py examples --all --report reports/portfolio-validation.md

# Flag stale documentation based on most recent ISO dates in each file
python scripts/validate_portfolio.py examples --all --max-fact-age-days 90

# Fail build when freshness checks fail
python scripts/validate_portfolio.py examples --all --max-fact-age-days 90 --enforce-freshness

# Fail build on any warning (placeholder and/or freshness)
python scripts/validate_portfolio.py examples --all --max-fact-age-days 90 --fail-on-warnings
```

## Exit code behavior (for CI)
`validate_portfolio.py` returns:
- `0` = pass (or pass with warnings when warnings are not configured to fail)
- `1` = policy failure (missing files, strict placeholders, freshness enforcement, warning enforcement, or quality gate failure)
- `2` = invocation/validation error (invalid args or unreadable target directory)

## Example workflow
```bash
# 1) Scaffold a new portfolio from templates
python scripts/create_portfolio.py ./my-system

# 2) Start from a reference example (optional)
cp -R examples/exchange-online ./my-system

# 3) Adapt content to your real system
$EDITOR my-system/*.md

# 4) Validate required files and quality
python scripts/validate_portfolio.py my-system --quality-gate 80

# 5) Optional strict CI-like checks
python scripts/validate_portfolio.py my-system --strict --max-fact-age-days 90 --fail-on-warnings
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
