# Dependencies and Integrations

## Summary
Map upstream/downstream dependencies and how integration failures show up operationally.

## Interview Prompts
- Which systems does this depend on (identity, messaging, storage, network, vendor APIs)?
- Which systems depend on this?
- What interfaces are used (API, events, files, ETL, webhooks)?
- What auth and rate-limit constraints exist?
- Which vendors are in the critical path?

## Output Structure
- **Upstream dependencies:**
- **Downstream consumers:**
- **Integration interface catalog:**
- **Data and control flows:**
- **Vendor touchpoints:**
- **Failure modes and fallback behavior:**

## For AI + Human Use
Describe how to triage whether an incident is local or dependency-driven.

## Open Questions / TBDs
- TBD:
