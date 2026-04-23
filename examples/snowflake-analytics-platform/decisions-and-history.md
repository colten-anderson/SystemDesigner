# Decisions & History — Snowflake Analytics Platform

| Date | Decision | Context | Alternatives considered | Outcome |
|---|---|---|---|---|
| 2024-09-12 | Standardize transformations on dbt | Needed consistent testing and lineage | Mixed SQL scripts + notebooks | Improved testability and ownership clarity |
| 2025-01-21 | Introduce domain-oriented marts | KPI definitions diverged by team | Single monolithic warehouse schema | Clear contracts and faster analytics delivery |
| 2025-08-07 | Add cost anomaly alerting | Spend spikes during ad-hoc heavy queries | Manual monthly cost review | Faster response to runaway workloads |
