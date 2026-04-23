# Wiring Guide: MCP Resource Usage

Use the system portfolio as a first-class MCP resource set.

## Recommended resource model
Expose each file as an addressable resource:
- `system://<id>/system-identity`
- `system://<id>/business-context`
- `system://<id>/architecture`
- `system://<id>/tech-stack`
- `system://<id>/dependencies-and-integrations`
- `system://<id>/data`
- `system://<id>/security-and-access`
- `system://<id>/operations`
- `system://<id>/known-issues-and-constraints`
- `system://<id>/decisions-and-history`

## Consumption pattern
1. Resolve identity + criticality first.
2. Pull architecture + dependencies before change planning.
3. Pull security + operations before execution.
4. Pull known-issues + decisions before non-trivial migration work.

## Operational tip
Cache stable files (history, business context) longer than high-churn files (operations, known issues).
