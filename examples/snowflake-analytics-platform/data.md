# Data — Snowflake Analytics Platform

## Data domains
- Revenue and subscription lifecycle
- Customer account and support interactions
- Product telemetry and feature usage
- Marketing funnel and attribution

## Governance model
- PII classified with column-level tags.
- Row-level policies applied for finance and HR-sensitive datasets.
- Access granted through role-based data products (reader, analyst, engineer).

## Data quality program
- dbt tests for uniqueness, not-null, relationships, and accepted values.
- Freshness checks for critical sources every 15 minutes.
- Severity-based alert routing to domain owners.
