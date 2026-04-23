# Security & Access — Snowflake Analytics Platform

## Access model
- SSO with SCIM-provisioned roles.
- Least-privilege roles by domain and environment.
- Break-glass admin role requires ticket + approval.

## Controls
- All data encrypted at rest and in transit.
- Network policies restrict access to corporate egress and approved jobs.
- Quarterly access recertification with automated deprovisioning.

## Auditability
- Query history retained and exported to SIEM.
- Data access policy changes tracked in change-management logs.
