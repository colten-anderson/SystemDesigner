# Security & Access — Customer Billing API

## Authentication and authorization
- Service-to-service auth via mTLS and workload identity.
- End-user requests authorized through checkout service JWT scopes.
- Admin refund endpoints require elevated support role + approval workflow.

## Security controls
- Secrets managed in AWS Secrets Manager with 90-day rotation.
- WAF and rate limiting applied at ingress.
- Quarterly dependency vulnerability scanning and patch SLAs.

## Compliance notes
- PCI DSS scope limited to integration points (tokenized flow).
- Audit logging enabled for all financial state transitions.
