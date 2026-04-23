# Operations — Snowflake Analytics Platform

## SLOs and operations KPIs
- Critical mart freshness: <30 minutes (98% target)
- Pipeline success rate: >= 99%
- Cost variance threshold: page when daily spend exceeds forecast by 20%

## Standard incident responses
1. **Freshness breach**
   - Identify failing source or job in Dagster.
   - Rerun impacted asset group with constrained warehouse.
   - Notify downstream dashboard owners and ETA.
2. **Data quality regression**
   - Quarantine failing model from production publish.
   - Triage failing tests by upstream source changes.
   - Approve controlled backfill after validation.

## Maintenance routines
- Weekly warehouse right-sizing review.
- Monthly lineage and ownership audit for critical marts.
