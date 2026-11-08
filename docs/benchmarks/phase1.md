> Historical phase report. Current release installation/rollback is in [ROLLOUT.md](../ROLLOUT.md); do not apply an old phase rollback to the latest schema. Final-code ingestion evidence remains incomplete.

# Phase 1 SQL optimization

The N+1 paths now use projected joins. Alerts has descending ID keyset pages, and the shared client retrieves all pages for existing dashboard filters and counts. Shipment listing uses one outer join to retain shipments with missing vehicles. Query budgets include the authenticated-user lookup.

## Measurement authority

The five-run noise-check table below is the authority for endpoint latency claims. Original endpoint samples remain in baseline.json and phase1-run.json for reproducibility; their superseded one-run latency table is intentionally omitted. Both versions use the same deterministic synthetic dataset and request settings. SQL call budgets are structural and covered by regression tests.

Alerts SQL falls from 2,980 to two calls for the default page; complete-history traversal requires 12 calls. Shipment listing falls from 112 to two. Reports falls from nine to eight on PostgreSQL. These counts are recorded in baseline.json and phase1-run.json. The default Alerts page is smaller; only complete-history traversal is a like-for-like payload comparison. Dashboard/live handlers remain unchanged.

## Report-tail investigation

Phase 0's two filtered event-count statements each scanned all 100,000 rows. Their recorded EXPLAIN execution times were 12.58 and 12.68 ms. Counting all events was another 9.572 ms. About 95.8% of temperatures were in the reference range, so a selective temperature index was not supported by those plans.

A new instrumented run of the original report implementation reproduced request spikes associated with Python GC while hydrating 2,978 alert ORM objects. For example, one request took 82.18 ms with 24.42 ms in SQL and 41.52 ms in observed GC. The original Phase 0 requests were not GC-profiled, so this does not establish the cause of every original outlier. See [before profiling](reports-before.json).

Combining the event counts into one aggregate and calculating alert categories in SQL removed the bulk alert-object allocation. PostgreSQL then selected a parallel Finalize Aggregate/Gather with two workers. Tail requests persisted, with SQL time accounting for almost all the spike. One profiled request took 150.23 ms with 144.00 ms in SQL and zero observed GC. See [aggregate-only profiling](reports-after.json).

A serial-transaction experiment produced p50 17.84 ms and p95 19.03 ms, compared with p50 49.21 ms and p95 154.81 ms in the aggregate-only diagnostic run. See [serial experiment](reports-serial-experiment.json). This motivated a PostgreSQL-only SET LOCAL max_parallel_workers_per_gather=0 within the report request. It adds one SQL statement and ends with the request transaction. The final API benchmark, rather than this diagnostic experiment, supplies the comparison table.

This setting is tuned to the measured local 100k-row workload. Re-measure report plans at substantially larger datasets and on the hosted system before assuming serial execution remains preferable. SQLite does not execute the PostgreSQL setting and has a seven-statement report budget. PostgreSQL has an eight-statement budget.

## Index decision and plans

One index was added, sensor_events(shipment_id, id), named ix_events_shipment_id. It supports the existing evidence cursor and insertion-order access. The prior shipment/time index cannot directly satisfy this ordering.

| Evidence cursor SQL plan | Before | After |
| --- | --- | --- |
| Index selected | ix_sensor_events_id | ix_events_shipment_id |
| Index condition | id > 0, with shipment filter | shipment_id = 1 and id > 0 |
| Rows discarded by shipment filter | 9,900 | 0 |
| Shared buffer hits | 484 | 103 |
| EXPLAIN ANALYZE execution | 0.859 ms | 0.052 ms |
| 30-execution p50, including row fetching | 1.267 ms | 0.953 ms |
| 30-execution p95, including row fetching | 2.419 ms | 1.091 ms |

Both plans and all timings are saved in [the index experiment](evidence-index.json). This experiment used the same seeded database, actual evidence-query SQL, cursor zero and limit 101. The candidate index was created inside the experiment transaction and rolled back afterward. The accepted index is supplied by Alembic revision 0002. No device/time, alert filter or temperature index was added. The paginated alert plan already uses the ID index and shipment primary key.

## Migration and rollout

Install the updated backend requirements and set DATABASE_URL through the environment. Use the existing private PostgreSQL connection configuration with DDL permission. The commands below run from the repository root.

For an existing installation that has no Alembic version table, first verify that its schema matches the pre-Phase-1 snapshot. If this check reports differences, review those differences before stamping.

```powershell
python -m pip install -r Tamper_admin/backend/requirements.txt
python operations/check_migration_schema.py --baseline
python -m alembic stamp 0001_existing_schema
python -m alembic upgrade head
python -m alembic check
```

For a new empty database, run python -m alembic upgrade head directly. Revision 0001 is a frozen snapshot of the existing schema, including the pre-existing shipment/time index. Revision 0002 creates the measured shipment/ID index. Normal backend startup behavior remains compatible. Existing tables need the migration to receive the new index.

Revision 0002 now uses CREATE INDEX CONCURRENTLY and DROP INDEX CONCURRENTLY in Alembic autocommit blocks on PostgreSQL. See [the exact Supabase rollout and recovery guide](../SUPABASE_ROLLOUT.md) for backup, invalid-index handling and rollback. A rollback to revision 0001 removes only the added index. The initial revision's downgrade removes application tables and is reserved for disposable database tests.

Deploy the backend and updated Tamper_admin/frontend/api.js together, with the API available first. getAlerts() still resolves to an array of the complete history, fetching limit=500 pages with before_id set to the last ID from the previous page. Existing dashboard rendering code and local filters continue to receive the complete array. External direct API consumers should follow the same cursor protocol. A page shorter than the requested limit finishes traversal. Concurrent new inserts remain above the cursor and appear on the next refresh.

No hosted migration or deployment was performed in this work.

## Validation and reproduction

All 28 Python tests passed on SQLite and on disposable PostgreSQL, preserving the original 22 tests in each run. All three existing browser scripts passed, plus the new alert-pagination script. Tests enforce exactly two SQL calls for Alerts and shipment listing, cover alert cursor boundaries, missing vehicles, report aggregates and temperature boundaries/nulls. Alembic tests cover fresh upgrade/downgrade and adoption without losing an existing row. The benchmark runner also verified fresh PostgreSQL migrations and adoption of the seeded schema.

```powershell
python -m unittest discover -s tests -p "test_*.py"
python operations/run_postgres_tests.py
node tests/test_evidence.cjs
node tests/test_ui_state.cjs
node tests/test_reports.cjs
node tests/test_alert_pagination.cjs
python operations/run_benchmark.py --verify-migrations --output docs/benchmarks/phase1-run.md
```

The additional full-history alert benchmark runs after the original eight routes, so it does not change their sequence or sample settings. The original Phase 0 artifacts are retained. Diagnostic runs can be reproduced with --reports-profile and --index-profile, using separate output filenames. The index profiler reuses the archived evidence SQL in evidence-index.json and operates only in the disposable benchmark database.

## Five-run noise check

Five Phase 0 runs and five Phase 1 runs were interleaved on fresh local PostgreSQL clusters. Each used the same 100k-event seed, 100 devices, three warmups, 30 samples per endpoint and concurrency one. All eight endpoints were measured on every run, including unchanged dashboard summary and live telemetry. Raw samples and exact plans are retained under [noise/](noise/).

Each cell is the median of the five run percentiles, followed by the minimum and maximum run percentile. Spread is max minus min and is retained in [summary.json](noise/summary.json). A result is outside measured noise only when the observed run ranges do not overlap. Five runs do not establish a confidence interval or exclude time-dependent environmental effects.

| Endpoint | Phase 0 p50 median [min, max] ms | Phase 1 p50 median [min, max] ms | p50 assessment | Phase 0 p95 median [min, max] ms | Phase 1 p95 median [min, max] ms | p95 assessment |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| /api/admin/dashboard | 4.78 [3.91, 5.92] | 4.17 [4.09, 6.06] | Ranges overlap; within observed noise | 5.55 [5.18, 6.82] | 5.20 [5.12, 6.84] | Ranges overlap; within observed noise |
| /api/vehicles | 4.50 [4.15, 4.86] | 4.24 [4.00, 5.23] | Ranges overlap; within observed noise | 5.06 [4.49, 6.03] | 4.87 [4.77, 6.45] | Ranges overlap; within observed noise |
| /api/shipments | 50.85 [37.14, 52.33] | 5.67 [5.21, 6.10] | Improvement outside observed ranges | 53.06 [43.33, 79.24] | 6.48 [6.11, 7.20] | Improvement outside observed ranges |
| /api/alerts | 1038.96 [1029.53, 1140.11] | 4.51 [4.15, 4.78] | Improvement outside observed ranges; default payload reduced | 1234.61 [1193.10, 1278.53] | 5.06 [4.72, 5.84] | Improvement outside observed ranges; default payload reduced |
| /api/shipments/BENCH-SHIP-00000 | 6.59 [6.54, 7.18] | 7.07 [6.78, 8.05] | Ranges overlap; within observed noise | 7.92 [7.78, 9.10] | 8.12 [7.70, 8.99] | Ranges overlap; within observed noise |
| /api/shipments/BENCH-SHIP-00000/live | 3.27 [3.04, 3.65] | 3.48 [3.21, 4.41] | Ranges overlap; within observed noise | 4.44 [4.05, 4.54] | 4.22 [4.04, 5.97] | Ranges overlap; within observed noise |
| /api/shipments/BENCH-SHIP-00000/evidence?limit=100 | 10.00 [9.50, 10.68] | 8.94 [8.40, 10.08] | Ranges overlap; within observed noise | 11.03 [10.64, 12.13] | 9.94 [9.37, 11.05] | Ranges overlap; within observed noise |
| /api/reports/summary | 45.08 [44.12, 47.09] | 17.06 [16.78, 18.21] | Improvement outside observed ranges | 116.70 [112.09, 122.90] | 18.60 [18.11, 19.68] | Improvement outside observed ranges |
| alerts_complete_history | 1038.96 [1029.53, 1140.11] | 61.27 [61.07, 62.83] | Improvement outside observed ranges | 1234.61 [1193.10, 1278.53] | 65.11 [63.76, 69.32] | Improvement outside observed ranges |

The repeated Reports p50/p95 ranges are disjoint, supporting a local improvement outside the observed noise. Use the repeated medians, not the original one-off pair. PostgreSQL serial-execution tuning was local and remains unverified on hosted Supabase.

The complete-history Alerts comparison, shipment listing and Reports improvements are supported by disjoint repeated ranges. Untouched endpoints with overlapping ranges have no established improvement.

SQL call-count reductions are structural and stable across the runs. The index timing experiment and the report profiling experiments were separate single before/after experiments. Their timing differences have no independently established run-to-run noise bound. Index rows discarded and buffer counts describe those observed plans, not an endpoint latency guarantee.

Reproduce with a separate checkout of commit 6d108ca and python operations/run_noise_check.py --baseline-root <that-checkout>. Keep Phase 2 caching disabled for a Phase 1 comparison.
