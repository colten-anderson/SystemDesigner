# Known Issues & Constraints — Customer Billing API

- **Constraint:** ACH settlement windows vary by bank holidays.
  - **Impact:** Cash reporting can lag by 1-2 business days.
  - **Mitigation:** Finance dashboard labels provisional balances.
- **Issue:** Legacy mobile clients retry with short timeouts.
  - **Impact:** Bursty duplicate request attempts during provider latency.
  - **Mitigation:** Server-side idempotency and client SDK upgrade campaign.
- **Constraint:** Single AWS region for now.
  - **Impact:** Regional outage causes full downtime.
  - **Mitigation:** Active DR plan; multi-region target in Q3 roadmap.
