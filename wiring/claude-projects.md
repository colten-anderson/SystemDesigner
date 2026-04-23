# Wiring Guide: Claude Projects

Attach a complete system portfolio to a Claude Project for system-specific reasoning.

## Project setup
- Project name: `<System Name> Context Portfolio`
- Upload all 10 files from the target system folder.
- Add usage instruction: "Prefer this portfolio over generic assumptions; flag stale or conflicting entries."

## Recommended project instructions
- Start answers by identifying system mode + criticality tier.
- Cite relevant sections when proposing changes.
- For incidents, prioritize `operations`, `dependencies-and-integrations`, and `known-issues-and-constraints`.
- For audits, prioritize `business-context`, `data`, and `security-and-access`.
