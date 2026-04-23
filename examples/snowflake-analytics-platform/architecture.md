# Architecture — Snowflake Analytics Platform

## High-level design
- Ingestion from SaaS and operational databases via Fivetran/Airbyte.
- Raw landing zone in Snowflake; transformation layer built with dbt.
- Curated marts exposed to BI tools and reverse ETL jobs.
- Metadata and lineage tracked in data catalog.

## Processing tiers
1. Raw (append-only, source-aligned)
2. Staging (standardized types + keys)
3. Core (conformed entities)
4. Marts (domain-specific analytics outputs)

## Reliability approach
- Per-domain warehouse sizing and workload isolation.
- Automatic retries for transient ingestion failures.
- Incident runbooks for freshness, quality, and cost anomalies.
