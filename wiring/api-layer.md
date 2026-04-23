# Wiring Guide: API-Layer Consumption

Use the portfolio as structured context for operational APIs and agent orchestration.

## Endpoint pattern
- `GET /systems/{id}/context` → full context pack
- `GET /systems/{id}/context/{section}` → section-level retrieval
- `GET /systems/{id}/runbook-hints` → operation snippets derived from `operations.md`

## Suggested request flow
1. Read `system-identity` for routing + ownership.
2. Read `architecture` and `dependencies-and-integrations` for blast radius.
3. Read `security-and-access` for policy checks.
4. Read `operations` for runbook-driven execution.

## Contract guidance
Return section metadata with:
- `last_updated`
- `owner`
- `confidence` (high/medium/low)
- `open_questions_count`
