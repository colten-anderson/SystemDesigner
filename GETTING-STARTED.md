# Getting Started

There are two ways to fill a portfolio:

- **Voice interview (recommended for teams):** drop the agent into a live
  Teams call and let it run the whole interview — see step 2a.
- **Manual / chat interview:** use the interviewer prompt in a text chat and
  fill the files yourself — see step 2b.

## 1) Choose one IT system
Create a folder for a single system portfolio (example: `portfolios/exchange-online/`).

## 2a) Run the live voice interview
One command joins a Microsoft Teams meeting via its dial-in number, leads the
full mode-aware interview, and writes the validated 10-file portfolio:

```bash
pip install -e ".[voice]"
cp .env.example .env       # fill in ANTHROPIC, DEEPGRAM, CARTESIA, DAILY keys

# Paste the Teams invite's "Dial in by phone" block, or use a dial string:
python scripts/run_interview.py --join "+15551234567,,123456789#" \
    --out portfolios/<system-name>
```

Accounts you need (details in [docs/voice-interview.md](docs/voice-interview.md)):
Anthropic (LLM), Deepgram (STT), Cartesia (TTS), and Daily with PSTN dial-out
enabled (paid feature). The Teams meeting needs a dial-in number, which exists
when the organizer's tenant has Audio Conferencing.

Platform support: **Teams ✅ (dial-in)** · **Slack Huddles ❌** (no audio API
exists — documented, not faked) · **local mic / text console ✅** for
development (`--local-audio` / `--text`). Progress is saved continuously;
resume a dropped call with
`python scripts/run_interview.py --resume portfolios/<system-name>/.interview-state.json`.

## 2b) Or run the interview manually in a chat
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

You can also enforce a documentation quality gate score (0-100):

```bash
python scripts/validate_portfolio.py portfolios --all --quality-gate 80
```

And generate a markdown review artifact for audits or PRs:

```bash
python scripts/validate_portfolio.py portfolios --all --report reports/portfolio-validation.md
```

If your CI policy treats warnings as failures, use:

```bash
python scripts/validate_portfolio.py portfolios --all --max-fact-age-days 90 --fail-on-warnings
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
