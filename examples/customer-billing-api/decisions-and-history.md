# Decisions & History — Customer Billing API

| Date | Decision | Context | Alternatives considered | Outcome |
|---|---|---|---|---|
| 2025-02-18 | Use provider tokenization only | Reduce PCI exposure | Self-hosted vault | Lower compliance burden; accepted vendor lock-in |
| 2025-06-10 | Adopt event-driven reconciliation | Need reliable downstream finance sync | Direct DB reads by analytics | Better decoupling and replayability |
| 2025-11-03 | Separate ACH adapter from card flows | Distinct failure modes and SLAs | Unified adapter interface only | Improved incident isolation |
