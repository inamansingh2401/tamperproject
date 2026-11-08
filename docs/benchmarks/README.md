# Benchmark and verification evidence

Authoritative read-performance claims use [Phase 1 five-run noise results](phase1.md), not the archived one-run endpoint samples. [Phase 2](phase2.md) records cache query-count trade-offs; its timings are single-pair diagnostics. [Phase 3](phase3.md) contains completed historical ingestion comparisons before strict replay. [Final-code ingestion](final-ingestion.md) is incomplete and establishes no final overhead claim. [Current verification](verification.json) records actual test/build/audit results. Configuration constants and protocol/version identifiers are implementation facts, not measured performance.

## Original baseline reproduction

# Reproducing the Phase 0 baseline

The original Phase 0 artifacts correspond to commit 6d108ca. Use that revision in a separate checkout to reproduce the original implementation. For the current Phase 1 implementation, run with --output docs/benchmarks/phase1-run.md and follow [the Phase 1 report](phase1.md). Supplying a separate output path preserves the original baseline.

Run from the repository root using Python and PostgreSQL 18 installed locally.

```powershell
python -m pip install -r Tamper_admin/backend/requirements.txt httpx
python operations/run_benchmark.py --events 100000 --devices 100 --samples 30
```

The runner creates its own password-protected loopback PostgreSQL cluster, inserts synthetic data, runs authenticated API requests and saves Markdown plus raw JSON. It stops the cluster and removes its private files afterward. It supplies generated credentials through process environment variables. Existing DATABASE_URL values are replaced inside this process.

Use `--pg-bin "C:/Program Files/PostgreSQL/18/bin"` for a different installation location and `--port 25435` for an unused port. Keep every comparison's arguments identical. The runner accepts 100,000–500,000 events. Each device has a separate shipment and vehicle, so raising the device count also stresses list endpoints.

For a pre-created empty loopback database named `safetrack_benchmark`, set `BENCHMARK_DATABASE_URL` through your environment and run the tools separately.

```powershell
python operations/seed_benchmark.py --events 100000 --devices 100
python operations/benchmark_api.py --samples 30 --output docs/benchmarks/baseline.md
```

The seed tool rejects non-empty databases. Both tools reject remote hosts and database names other than safetrack_benchmark. The API's existing startup creates demo entities and applies its existing schema checks inside this isolated database.

## Dataset and measurement scope

The deterministic fixture uses seed 20261108 and one-second readings per device, distributed across 100 devices by default. It includes roughly 2% light exposure, 1% shock and 3% temperature-excursion opportunities. The exact alert count is in the report. These are synthetic distributions rather than empirical fleet frequencies. The rows use valid legacy hash chains without device signatures. Read benchmarks therefore exclude the signature-verification cost of version-2 evidence.

The harness measures eight authenticated GET routes through FastAPI TestClient against real PostgreSQL. It performs three warmups and 30 serial measurements per route, reporting nearest-rank p50 and p95, SQL statement count, response size and all individual timings. SQLAlchemy instrumentation adds some overhead. The five slowest distinct SQL statements by mean cursor execution time receive EXPLAIN ANALYZE BUFFERS plans with their actual parameters.

This measures local application and database latency, excluding network, TLS, browser rendering, cold starts and ingestion throughput. The existing admin dashboard loads vehicles, shipments and alerts. The harness measures those actual requests individually. API responses are checked for HTTP success. Existing regression tests separately validate response semantics.

## Validation

```powershell
python -m unittest discover -s tests -p "test_*.py"
python operations/run_postgres_tests.py
node tests/test_evidence.cjs
node tests/test_ui_state.cjs
node tests/test_reports.cjs
```

The benchmark safety tests check database target restrictions and percentile calculation. PostgreSQL execution of the full seed and every measured endpoint is the integration check for the tooling.

## Next phases

Save later runs to separate output paths so the original baseline stays reviewable. Before/after improvement claims need comparable measurements. Phase 0 establishes the starting point and supplies no improvement percentage or hosted cost estimate.
