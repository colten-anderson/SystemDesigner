# Wiring Guide: Backstage / Service Catalog Usage

Treat each system portfolio as a companion to your service catalog entity.

## Catalog alignment
Map portfolio fields to catalog metadata:
- system identity ↔ system/service entity name and owner
- business context ↔ domain, tier, and lifecycle metadata
- operations ↔ on-call links, dashboards, and runbooks
- dependencies ↔ relation graph (consumes/provides)

## Practical integration
- Link each portfolio file from catalog annotations.
- In scorecards, check for freshness of `operations` and `known-issues`.
- During incident triage, open catalog entity + portfolio side-by-side.
