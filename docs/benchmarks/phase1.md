# Phase 1 SQL optimization

The N+1 paths now use projected joins. Alerts has descending ID keyset pages, and the shared client retrieves all pages for existing dashboard filters and counts. Shipment listing uses one outer join to retain shipments with missing vehicles. Query budgets include the authenticated-user lookup.

## Measurements

The table compares the original Phase 0 report with the final Phase 1 run. Both used 100,000 events, 100 synthetic devices, seed 20261108, PostgreSQL 18, concurrency one, three warmups and 30 timed requests per route. Existing startup adds ten demo shipments/devices, giving 110 total. There are 2,978 alerts. Instrumentation includes authentication, SQL, ORM work and serialization through FastAPI TestClient.

Raw timings and exact plans are in [Phase 0 JSON](baseline.json), [Phase 1 JSON](phase1-run.json) and [the final query-plan report](phase1-run.md). These are separate local runs with visible timing variability, including endpoints whose handlers were untouched. Network latency, browser rendering, hardware signatures and ingestion throughput are outside the measurement.

| Route | p50 before → after (ms) | p95 before → after (ms) | SQL before → after |
| --- | ---: | ---: | ---: |
| /api/admin/dashboard | 7.417 → 8.801 | 9.461 → 10.691 | 5 → 5 |
| /api/vehicles | 5.820 → 7.920 | 7.325 → 12.189 | 2 → 2 |
| /api/shipments | 47.159 → 13.730 | 63.726 → 18.896 | 112 → 2 |
| /api/alerts | 1294.784 → 9.596 | 1633.002 → 12.079 | 2980 → 2 |
| /api/shipments/BENCH-SHIP-00000 | 11.053 → 19.099 | 13.790 → 22.876 | 6 → 6 |
| /api/shipments/BENCH-SHIP-00000/live | 6.834 → 8.392 | 8.653 → 10.035 | 3 → 3 |
| /api/shipments/BENCH-SHIP-00000/evidence?limit=100 | 15.193 → 23.058 | 18.116 → 29.162 | 4 → 4 |
| /api/reports/summary | 58.421 → 40.261 | 151.858 → 46.958 | 9 → 8 |
| Alerts complete history | 1294.784 → 148.064 | 1633.002 → 168.404 | 2980 → 12 |

The default Alerts endpoint now returns 100 records instead of the previous unbounded 2,978 records. The complete-history row includes all 2,978 records across six requests at limit=500, matching the updated JavaScript client. Its SQL count includes six authentication lookups.

The shipment and report improvements retain the same logical response content. Dashboard summary and live telemetry handlers were untouched. The final run was slower for vehicles, shipment detail, live telemetry, dashboard summary and the evidence endpoint. The evidence index improved its isolated SQL plan, but the endpoint's final measured latency increased. No endpoint-level speedup is claimed for those routes.

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

The index migration uses ordinary CREATE INDEX. Schedule a short maintenance window because index construction can block writes. A rollback to revision 0001 removes only the added index. The initial revision's downgrade removes application tables and is reserved for disposable database tests.

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
