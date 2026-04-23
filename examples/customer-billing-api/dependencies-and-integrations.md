# Dependencies & Integrations — Customer Billing API

| Dependency | Type | Owner | Purpose | Failure impact | Fallback |
|---|---|---|---|---|---|
| Stripe API | External | Payments Platform | Card auth/capture/refund | Card charges fail | Queue retries; temporary checkout warning |
| ACH Processor | External | Treasury Engineering | Bank debit/credit flows | ACH settlement delay | Retry with backoff; manual finance queue |
| Email service | Internal | Messaging Team | Sends receipts | Receipts delayed | Reprocess queued email events |
| Finance data lake export | Internal | Data Platform | Reconciliation reporting | Delayed close reports | Backfill export job |
