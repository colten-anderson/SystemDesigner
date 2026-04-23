# Operations — Customer Billing API

## SLOs and alerts
- Availability SLO: 99.95%
- Latency SLO: p95 < 250 ms for `CreatePayment`
- Page when 5xx > 2% for 5 minutes or provider timeout > 8%

## Common incidents
1. **Provider timeout spike**
   - Verify provider status page and outbound latency dashboards.
   - Enable degraded mode (queue capture requests).
   - Escalate if degraded mode exceeds 30 minutes.
2. **Duplicate charge suspicion**
   - Check idempotency key collisions and replay logs.
   - Freeze automated retries for affected tenant.
   - Coordinate with Finance Ops for customer remediation.

## Operational routines
- Weekly review of failed payment buckets.
- Monthly failover game day for database and queue backlog recovery.
