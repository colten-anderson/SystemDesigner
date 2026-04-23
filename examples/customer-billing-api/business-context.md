# Business Context — Customer Billing API

## Purpose
Provides a single API for invoice creation, payment capture, refunds, and billing history lookup across all customer channels.

## Core outcomes
- Supports card and ACH payments for subscription and one-time purchases.
- Reduces duplicate billing logic across product teams.
- Provides finance-auditable billing events within 5 minutes of transaction completion.

## Success metrics
- API availability >= 99.95% monthly.
- Payment authorization success rate >= 96% (excluding issuer declines).
- Refund completion p95 < 10 minutes.

## Stakeholders
- Product: Commerce Product Team
- Operations: Customer Support + Finance Ops
- Compliance: Security & GRC team
