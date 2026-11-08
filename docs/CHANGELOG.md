# Implementation changelog

This describes local work, not deployment history. Nothing in this release resets existing login accounts, passwords or JWT secrets. Measurement and verification evidence is indexed in [benchmarks](benchmarks/README.md).

## Phase 0 — establish a baseline

Added a deterministic synthetic PostgreSQL seed, authenticated read benchmarks, SQL statement counts and actual query plans. The original one-run endpoint timings are retained as raw evidence, superseded for latency claims by the repeated noise check.

## Phase 1 — remove repeated database work

Removed per-row alert/shipment queries, added backward-compatible alert pagination, aggregated Reports and added one evidence-cursor index justified by measured plans. Alembic makes changes reproducible; the PostgreSQL index migration uses concurrent DDL. Query-count tests guard against N+1 regressions. Read-performance claims use the repeated noise ranges, including unchanged endpoints. Reports tuning remains local and unverified on hosted Supabase.

## Phase 2 — make caching optional

Added a small Reports cache interface, optional Redis adapter, revision-based invalidation and admin-only hit/miss metrics. Caching remains OFF. Polling avoided database calls in the measured mix; high churn added calls without hits. Alerts and live telemetry remain uncached. Cache timing experiments were separate diagnostics, not five-run confidence estimates.

## Phase 3 — improve ingestion and document the design

Added bounded batches, idempotent retries and per-device/IP admission limits with an authenticated critical-event lane. Documented offline custody, ordering and fleet/cost assumptions. Completed local software-signed ingestion and batching comparisons; these are historical results before the next phase's replay controls.

## Phase 4 — implement and verify security controls

Declared the cryptography version used in measurements, patched audited dependencies, and added a threat model/OWASP checklist. Implemented explicit strict-device replay protection, admin device registration/revocation/rotation, stored-chain verification, bounded input parsing and browser-role isolation SQL. Existing devices keep compatibility behavior until firmware/enrollment is ready. Hardware signing performance, hosted behavior and firmware epoch/ACK acceptance remain unverified.

## Final documentation and benchmark follow-up

Reconciled the README, architecture, security and rollout instructions. Preserved the existing overview/screenshot and contributor history; superseded one-run latency tables no longer serve as performance claims. The final-code ingestion experiment was stopped at the operator's request before all repeated runs completed. Its partial artifacts are preserved and explicitly do not establish final strict-device overhead or capacity. See [the partial experiment](benchmarks/final-ingestion.md) and [verification evidence](benchmarks/verification.json).
