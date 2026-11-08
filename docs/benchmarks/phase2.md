> Historical phase report. Current release installation/rollback is in [ROLLOUT.md](../ROLLOUT.md); do not apply an old phase rollback to the latest schema. Final-code ingestion evidence remains incomplete.

# Phase 2 report caching

Current Phase 3 operating decision: keep REPORT_CACHE_BACKEND=off everywhere. The single-pair cache timings below are historical diagnostics, not five-run validated improvement claims. Do not enable caching as part of the current rollout.

Reports is the only cached endpoint. Dashboard summary, live telemetry, evidence, Alerts and shipment listing continue to query the database. Shipment listing already uses two SQL calls including authorization. An authoritative freshness check would use that same two-call floor, so no shipment-list SQL saving is established.

Caching is opt-in using REPORT_CACHE_BACKEND=memory. The default is off. The standard-library memory backend has a five-second TTL, a 32-entry bound and defensive copies. A small get/put interface also has an optional Redis adapter. Redis and hosted Supabase cache performance are unmeasured.

## Freshness contract

Each cache read first authenticates the current admin against the database, then reads the reports revision from cache_revisions on the authoritative primary database. Cached data is keyed by that revision. SQLAlchemy ORM flushes, bulk updates/deletes and Session.execute DML on events, alerts, shipments or vehicles advance the revision inside the same transaction as the write. An aborted transaction rolls back both data and revision.

After a successful ingestion or alert change, the next report request reads the new revision and cannot use the old cached response. A computation that finishes late can only populate its old revision key, which new requests will not use. Independent API workers can have separate memory caches and still observe the same database revision. Existing role checks run before a cache lookup.

The TTL limits memory residency and refreshes unchanged data. It is not the invalidation mechanism. Alerts and live endpoint responses are never cached. Failed cache access falls back to the database. A failed authoritative revision read fails the request instead of serving unverifiable cached data.

The application write listeners must be installed in every writer process. Raw SQL maintenance, direct engine writes and external database clients bypass SQLAlchemy session listeners. Disable caching across all workers before such maintenance, or advance the reports revision inside the same database transaction as the maintenance write.

```sql
INSERT INTO public.cache_revisions (namespace, generation)
VALUES ('reports', 1)
ON CONFLICT (namespace)
DO UPDATE SET generation = cache_revisions.generation + 1;
```

The revision upsert is one additional statement for each application data-writing commit, including workers with cache reads disabled. This supports a mixed rollout without silently losing invalidations. It also introduces a shared-row write lock. The later Phase 3 five-run comparison did not establish revision-row overhead outside observed noise; final strict-device ingestion is measured separately in [the final report](final-ingestion.md). No hosted contention result is claimed.

## Local polling experiment

Each mode started with a fresh 100k-event/100-device synthetic seed. Three report requests warmed the database before measurement without priming the cache. A 60-tick logical schedule issued two admin report reads per tick, one live read per tick, Alerts every two ticks and shipment listing every five ticks. One new event arrived before the first report in each tick. This models one active device at one event per logical second and two aggregate readers per logical second.

The schedule was executed without wall-clock sleeps. TTL used the explicit logical clock. Request latencies are actual elapsed local FastAPI/PostgreSQL times. This is a workload simulation, not a measurement of sustained requests per second or real 60-second concurrency. Every report response was checked for the correct post-ingestion event count.

| Report measurement | Cache off | Memory cache |
| --- | ---: | ---: |
| Report requests | 120 | 120 |
| Report SQL calls | 960 | 660 |
| Mean SQL calls per report | 8 | 5.5 |
| p50 | 16.629 ms | 3.969 ms |
| p95 | 17.824 ms | 18.198 ms |
| Hits / misses | 0 / 0, disabled | 60 / 60 |
| Hit rate | Disabled | 50% |
| Total SQL across the entire mixed workload | 1,848 | 1,548 |

This avoided 300 report SQL calls, a 31.25% reduction for reports and a 16.23% reduction across the entire mix. The total includes ingestion and revision-write overhead. Both control and cached modes use the same Phase 2 invalidation machinery, so the comparison does not measure that machinery's incremental cost against the old Phase 1 writer.

| Enabled-cache outcome | Requests | SQL/request | p50 | p95 |
| --- | ---: | ---: | ---: | ---: |
| Hit | 60 | 2 | 3.229 ms | 3.787 ms |
| Miss | 60 | 9 | 17.262 ms | 18.352 ms |

Hits retain the authorization and revision queries. Misses add the revision query to the original eight-statement PostgreSQL report path. With exactly half the requests hitting, nearest-rank p50 falls at the end of the hit group. It should not be interpreted as the mean latency. Report p95 did not improve in this experiment.

The 60 ingestion requests executed 60 revision upserts. Ingestion p50 was 8.843 ms in the off run and 9.858 ms in the cache-enabled run, with 624 SQL calls in either case. These are separate single runs and do not establish a statistically bounded ingestion latency difference.

Raw measurements are in [polling cache off](cache-polling-off.json) and [polling cache enabled](cache-polling-memory.json).

## High-churn counterexample

A second experiment inserted a new event before every report read. This produced no cache hits.

| Report measurement | Cache off | Memory cache |
| --- | ---: | ---: |
| Requests | 120 | 120 |
| Hit rate | Disabled | 0% |
| SQL calls | 960 | 1,080 |
| SQL/request | 8 | 9 |
| p50 | 17.085 ms | 17.203 ms |
| p95 | 18.411 ms | 18.579 ms |

Caching did not help this workload and added 120 report SQL calls. Keep it disabled when writes change the report revision between essentially every read. With the measured query budgets, the report SQL break-even hit rate is above 12.5%, before considering backend latency. This is a statement-count calculation, not a measured hosted latency threshold.

Raw measurements are in [high churn off](cache-churn-off.json) and [high churn enabled](cache-churn-memory.json). These Phase 2 timing experiments were single control/enabled pairs. The five-run Phase 1 noise bounds do not establish Phase 2 confidence intervals.

## Metrics and configuration

GET /api/admin/cache-metrics is admin-only and exposes enabled state, backend name, TTL, hits, misses, errors, hit rate and process ID. Counters are local to one worker, even with Redis. Aggregate them across workers before deriving deployment-wide hit rates. Metrics contain no connection strings or keys.

For in-memory caching, set REPORT_CACHE_BACKEND=memory and optionally REPORT_CACHE_TTL_SECONDS=5. The supported TTL is greater than zero and at most 30 seconds. No frontend changes are needed for Phase 2.

For the optional Redis backend, run python -m pip install -r Tamper_admin/backend/requirements-cache.txt, set REPORT_CACHE_BACKEND=redis, REDIS_URL through the secret environment, and a database-specific REPORT_CACHE_NAMESPACE. Remote Redis requires rediss TLS. Redis connection/read timeouts are bounded. The adapter's JSON/TTL contract is unit-tested with a fake client. No Redis server latency, outage timing or hosted hit rate is claimed. [Redis Python client documentation](https://redis.io/docs/latest/develop/clients/redis-py/).

## Rollout and rollback

Follow the [Supabase backup and concurrent-index rollout](../SUPABASE_ROLLOUT.md) through revision 0002 first. Then use the current release's migration tools to run python -m alembic upgrade head before deploying the Phase 2 API. Revision 0003 creates the internal cache revision table, enables RLS on PostgreSQL, and revokes browser-role privileges when those roles exist.

The application backend must own that table or have explicitly reviewed SELECT/INSERT/UPDATE grants and RLS policies for it. Browser anon/authenticated roles must not receive access. The normal database-owner backend connection can use the table without a new policy.

Deploy all API writer processes with cache reads off. Verify ordinary ingestion, alert changes, report reads and the metrics endpoint. Keep caching off for Phase 3. Direct maintenance writers must follow the freshness contract above. Keep Reports serial-execution tuning marked as local and unverified on hosted Supabase.

If an earlier deployment already auto-created cache_revisions, do not blindly run CREATE TABLE again or stamp past unexplained differences. Run python operations/check_migration_schema.py, confirm the table's RLS and browser-role revocations, and review the existing schema before stamping 0003_report_cache_revision.

To disable caching, set REPORT_CACHE_BACKEND=off and redeploy/restart every worker. To remove the revision table, first disable cache reads everywhere, then deploy the Phase 1 API to every writer so no process still upserts that table. Using this release's migration tools, run python -m alembic downgrade 0002_evidence_cursor_index. This preserves the evidence index and application records. Roll back the index separately only if needed.

After a database restore, keep caching off and restart memory-cache workers. Rotate the Redis cache namespace before enabling Redis against restored data so revision values from the restored database cannot reuse prior cached keys.

No hosted database operation or deployment was performed.

## Reproduction and validation

```powershell
python operations/run_benchmark.py --cache-mix off --output docs/benchmarks/cache-polling-off.json
python operations/run_benchmark.py --cache-mix memory --output docs/benchmarks/cache-polling-memory.json
python operations/run_benchmark.py --cache-mix off --high-churn --output docs/benchmarks/cache-churn-off.json
python operations/run_benchmark.py --cache-mix memory --high-churn --output docs/benchmarks/cache-churn-memory.json
python -m unittest discover -s tests -p "test_*.py"
python operations/run_postgres_tests.py
```

Tests cover event-to-next-read freshness, alert resolution, independent worker caches, late fills under an old revision, bulk writes, rollback, TTL expiry, memory bounds, cache failure fallback, Redis JSON/TTL contract and metrics authorization. Migration tests cover SQLite behavior and PostgreSQL concurrent SQL emission. The disposable PostgreSQL migration drill also checked live insert progress during the concurrent index build.

All 35 Python tests passed on SQLite and on disposable PostgreSQL, including the original tests. All four browser scripts passed. Full PostgreSQL migration upgrade/check/downgrade and existing-schema adoption also passed locally.
