# Dependencies & Integrations — Snowflake Analytics Platform

| Dependency | Type | Owner | Purpose | Failure impact | Fallback |
|---|---|---|---|---|---|
| Salesforce connector | External SaaS | RevOps Systems | Pipeline and revenue analytics | Revenue dashboards stale | Manual CSV export for critical reports |
| ERP export feed | Internal | Finance Systems | Monthly close and accounting metrics | Delayed close package | Controlled backfill on restored feed |
| Product event stream | Internal | Core Platform | Product usage and retention metrics | Feature analytics blind spot | Replay from Kafka retention window |
| Looker | Internal SaaS | BI Team | Dashboard access for stakeholders | Limited self-serve analytics | Query via Snowflake worksheets |
