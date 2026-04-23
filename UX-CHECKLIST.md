# UX Checklist for System Portfolio Adoption

Use this checklist to improve contributor experience, operator usability, and documentation reliability.

## 1) Contributor onboarding UX
- [ ] New contributor can understand purpose in under 2 minutes from `README.md`.
- [ ] Getting-started flow can be completed in ~15 minutes for a first draft.
- [ ] Each template section has at least one concrete "good example" pattern.
- [ ] Unknowns are acceptable if they include owner + follow-up date.

## 2) Information architecture UX
- [ ] Critical information is findable in predictable locations across all portfolios.
- [ ] Headings and tables are optimized for scan speed during incidents.
- [ ] Dependencies include both technical function and failure impact.
- [ ] Decisions include alternatives considered and rationale.

## 3) Operational UX (incident-first)
- [ ] `operations.md` includes first checks for the first 10 minutes.
- [ ] Escalation thresholds are explicit and measurable.
- [ ] Rollback or containment steps are documented where applicable.
- [ ] Owner and on-call path are obvious without searching chat/history.

## 4) Validation UX
- [ ] Structural validation is part of normal author workflow.
- [ ] Strict validation is used before sign-off (or merge) to prevent placeholders.
- [ ] Validation errors are understandable and easy to fix.
- [ ] Teams know which quality bar is required: draft vs production-ready.

## 5) Continuous improvement UX
- [ ] Teams review one portfolio monthly for outdated content.
- [ ] Known issues and constraints include mitigation status and review date.
- [ ] Improvement requests are captured (e.g., "missing template prompt", "unclear field").
- [ ] At least one high-quality internal portfolio is used as a canonical example.

## Suggested rollout sequence
1. Pilot with one system that has active on-call responsibility.
2. Measure time-to-first-draft and strict-validation pass rate.
3. Fix top friction points (unclear prompts, missing examples, review ambiguity).
4. Roll out to adjacent systems with a lightweight review cadence.
