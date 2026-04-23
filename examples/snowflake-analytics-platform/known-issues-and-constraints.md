# Known Issues & Constraints — Snowflake Analytics Platform

- **Constraint:** Third-party SaaS APIs impose extraction rate limits.
  - **Impact:** Incremental sync lag during business peaks.
  - **Mitigation:** Prioritized sync windows for executive metrics.
- **Issue:** Inconsistent source naming conventions across business units.
  - **Impact:** Higher modeling complexity and slower onboarding.
  - **Mitigation:** Enforced canonical naming contract in staging models.
- **Constraint:** Some finance data available only once daily.
  - **Impact:** Intraday financial dashboards cannot be fully real-time.
  - **Mitigation:** Dashboard labels include freshness disclosure.
