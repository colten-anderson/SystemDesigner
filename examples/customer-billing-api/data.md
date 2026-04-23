# Data — Customer Billing API

## Data domains
- Customer billing profile (non-PCI identifiers only)
- Invoice metadata and status history
- Payment transaction records and provider response codes
- Refund requests and outcomes

## Sensitive data handling
- Card PAN is never stored; tokenization handled by payment provider.
- PII fields: name, email, billing address; encrypted at rest and in transit.
- Data retention: transactional records retained 7 years for finance compliance.

## Data quality controls
- Idempotency keys on all write endpoints.
- Nightly reconciliation against provider settlement files.
- Alert on mismatch ratio > 0.5%.
