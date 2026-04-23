# Architecture — Customer Billing API

## High-level design
- Public API served by Kubernetes ingress (EKS).
- Stateless billing service pods perform request validation and orchestration.
- Payment provider adapter layer routes to Stripe and ACH processor.
- PostgreSQL stores billing entities; Redis used for idempotency keys.
- Event bus publishes `invoice.created`, `payment.captured`, and `refund.completed`.

## Runtime boundaries
- Synchronous path: client request → API → provider auth/capture.
- Asynchronous path: webhook processing + reconciliation workers.

## Availability strategy
- Multi-AZ database deployment.
- Horizontal pod autoscaling on request latency + CPU.
- Circuit breaker on provider adapter calls.
