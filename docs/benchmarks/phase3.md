> Historical phase report. Current release installation/rollback is in [ROLLOUT.md](../ROLLOUT.md); do not apply an old phase rollback to the latest schema. Final-code ingestion evidence remains incomplete.

# Phase 3 ingestion measurements

All results are local. Application caching was off for every capacity and policy run. No hosted database operation, deployment, ESP32 flash or physical-network measurement was performed.

The measured lab stack was Windows 11, Python 3.13.7, PostgreSQL 18.6, FastAPI 0.141.1, Uvicorn 0.52.4, SQLAlchemy 2.0.52, psycopg 3.3.4, HTTPX 0.28.1 and cryptography 50.0.1. Version capture found that cryptography was outside the repository's declared >=43,<47 range. Both variants in every measured pair used the same 50.0.1 installation. Phase 4 subsequently verified this version and updated both declarations to >=50.0.1,<51. These remain historical Phase 3 measurements; see [the incomplete final-code experiment](final-ingestion.md); current strict-device capacity is not established.

## A. Revision-row comparison

Five interleaved runs of each mode were completed at concurrency 1, 5, 10 and 20. Each of the 40 cases created a fresh PostgreSQL cluster with the deterministic 100,000-event, 100-device seed. Twenty signed warmup events preceded 400 measured single-event requests. The measured starting count was therefore 100,020, and every completed case stored exactly 400 new events.

Requests used actual loopback HTTP to one Uvicorn process with the existing SQLAlchemy pool of five connections plus five overflow connections. Forty independent device/shipment streams submitted software-signed P-256 temperature/humidity/LDR frames. Public keys were enrolled before the run. Backend signature verification, validation, SQL, hash chaining, commit and HTTP acknowledgment are included. Client signing and server startup are excluded. Optional motion-vector payload costs, gateway transport, device signing, TLS, WAN latency, sustained-duration load and hosted capacity remain unmeasured.

The control monkeypatches advance_revision only inside the benchmark process, after validating the target is the local safetrack_benchmark database. There is no production configuration, header or endpoint that disables revision writes.

| Concurrency | Revision write | Events/sec median [min, max] | p50 ms median [min, max] | p95 ms median [min, max] | SQL/request | Timed error rate |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | revision | 69.28 [31.77, 76.25] | 14.31 [12.88, 30.95] | 16.35 [15.03, 38.98] | 10.0525 | 0% |
| 1 | bypass | 72.90 [35.55, 79.42] | 13.43 [12.23, 27.35] | 15.86 [14.45, 34.66] | 9.0525 | 0% |
| 5 | revision | 89.76 [54.12, 99.84] | 52.18 [47.35, 89.78] | 71.13 [61.00, 148.66] | 10.0525 | 0% |
| 5 | bypass | 98.96 [51.54, 113.80] | 47.77 [40.60, 91.73] | 66.90 [57.02, 133.37] | 9.0525 | 0% |
| 10 | revision | 82.80 [41.19, 93.68] | 115.68 [100.89, 237.35] | 171.95 [150.91, 324.13] | 10.0525 | 0% |
| 10 | bypass | 83.50 [55.27, 101.74] | 112.21 [92.79, 168.98] | 183.16 [146.90, 275.51] | 9.0525 | 0% |
| 20 | revision | 80.17 [33.67, 89.14] | 220.93 [198.76, 547.11] | 428.39 [378.21, 940.00] | 10.0525 | 0% |
| 20 | bypass | 90.96 [38.23, 100.87] | 196.21 [177.65, 499.33] | 356.53 [307.39, 705.08] | 9.0525 | 0% |

Cells report the median of five run percentiles/rates and their observed minimum/maximum. Raw samples and spreads are in [revision-summary.json](ingestion/revision-summary.json) and the adjacent per-run JSON files. SQL calls are SQLAlchemy cursor statements, excluding driver-level COMMIT/ROLLBACK. Throughput is successful new events divided by the timed closed-loop request interval.

All throughput, p50 and p95 ranges overlap between revision-enabled and bypass modes at every tested concurrency. The extra one SQL statement per event is established, but this experiment does not establish a revision-row throughput bottleneck outside observed noise. The comparison combines an extra SQL round trip, its write work and possible lock contention. PostgreSQL lock-wait time was not separately profiled.

The ten-connection pool also bounds concurrent database work. The data do not isolate pool waits, CPU, signing-verification cost and shared-row serialization. They do not justify removing the production revision fence or claiming a particular component is the dominant bottleneck.

## B. Batch comparison

After implementing batching, five additional interleaved single/batch pairs were run at concurrency 10. The same 400 signed events from forty device/shipment pairs were sent as either 400 individual requests or forty requests containing ten events each. Both variants used production revision writes, the default limiter policy and caching off. None of these timed requests was rate-limited.

| Mode at concurrency 10 | Events/sec median [min, max] | Request p50 ms median | Request p95 ms median | SQL/request | SQL/event | Revision upserts per 400 events | Error rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| single | 75.95 [59.06, 93.51] | 126.17 | 184.04 | 10.0525 | 10.0525 | 400 | 0% |
| batch10 | 141.45 [131.68, 160.19] | 686.78 | 806.26 | 81.5250 | 8.1525 | 40 | 0% |

Batch throughput ranges do not overlap the single-request ranges, so the measured local throughput improvement is outside the observed run spread. Per-request latency is longer for a ten-event request. It must not be described as lower single-event acknowledgment latency.

Raw samples are in [batch-summary.json](ingestion/batch-summary.json) and single-c10/batch10-c10 files. The first attempt stopped during API startup before a timed batch case began. Its completed preliminary outputs and failure record are retained in [preliminary-batch-attempt](ingestion/preliminary-batch-attempt/). The startup wait was raised from 15 to 60 seconds and the entire five-pair batch comparison was restarted. No timed result from that preliminary attempt is in the final comparison. Its root cause was not established; a startup log reported a closed PostgreSQL connection.

## C. Retry and admission diagnostics

A real HTTP transport discarded a successful response after the API committed, raising a client ReadTimeout. One hundred identical retries then received duplicate acknowledgments with one consistent event hash. The database contained exactly one additional row. [Lost-acknowledgment diagnostic](ingestion/retry-proof.json).

With an intentionally small test policy of 0.01 events/sec and burst two, 200 ordinary requests produced two successes and 198 HTTP 429 responses. Ten invalid-credential attempts produced two HTTP 401 and eight HTTP 429 responses. All ten subsequent authenticated, signed critical requests succeeded, producing twelve total new rows. [Admission diagnostic](ingestion/rate-proof.json).

These are functional counts from controlled fault/admission checks. Their raw timing samples have no five-run noise bound and support no performance improvement claim.

## API and correctness changes

POST /api/events retains the existing event_id deduplication, signature checks and hash-chain semantics. Phase 3 adds header-only Idempotency-Key support for legacy unsigned producers. The header must match an event ID already present in signed data. Signed events cannot gain an unsigned identity through a header. Reusing an ID with changed readings returns 409. Legacy clients supplying neither identity form remain compatible but cannot receive an idempotency guarantee.

POST /api/events/batch accepts an events array containing 1–100 records for exactly one device/shipment pair, with an event_id on every item. This prevents cross-device lock ordering inside a batch and preserves accepted item order. Each item uses the existing ingestion implementation. Accepted items share one commit and one cache revision write.

A successful batch returns HTTP 200 with per-item status_code=200 and the normal event acknowledgment. Schema, authentication and identity-conflict errors normally abort the transaction. Quota failures are handled per item so an ordinary item cannot prevent a later critical item from being admitted. Mixed quota outcomes return HTTP 207. If every item is throttled, the response is 429. Denied items include retry_after, and the response has Retry-After. Retry denied IDs unchanged. Replaying the entire batch is also safe for already acknowledged IDs. Duplicate-only batches do not append events or advance the revision.

The gateway still uses the single-event endpoint. It already retains queued records on 429 and transient failures. Its capped exponential retry delay is unchanged. Adopting batching in a future gateway requires handling each item's acknowledgment and 207/429 outcomes before removing outbox entries. No client was silently switched to batching.

Tests cover lost-response retries, stable hashes, changed-body conflicts, batch rollback, bounded batches, accepted ordering, delayed capture time, quota exhaustion and critical admission.

## Rate-limit policy

Ordinary telemetry has per-process token buckets with defaults of two events/sec and burst 120 per canonical enrolled device ID, plus 1,000 events/sec and burst 2,000 per ASGI client IP. Authentication failures use a separate five-attempts/sec, burst-20 IP budget. Configuration comes from INGEST_DEVICE_RATE/BURST, INGEST_IP_RATE/BURST and INGEST_FAILURE_RATE/BURST environment variables.

Authentication and required signature checks run before admission. Existing identical retries return duplicate acknowledgments before charging ordinary quotas. After authentication, light exposure, shock or temperature above the existing critical threshold bypass ordinary device/IP quotas. Invalid credentials cannot spend the valid-producer IP budget. IP identity comes from the ASGI client address, so the deployment must configure trusted proxies correctly.

The limiter is deliberately not a complete DDoS defense. A compromised authenticated device can generate critical traffic, and admission bypass does not create extra compute or network capacity. Per-process limits reset on restart and multiply with worker count. Shared distributed quotas were not implemented. Unknown/malformed traffic, upstream saturation and unavailable connectivity still require platform controls.

Critical admission does not remove the gateway's FIFO backlog or override existing capture-time staleness rules. Historical critical evidence is retained even when it must not replace newer current-state telemetry. Physical alert-delivery latency is unmeasured.

## Reproduction

```powershell
python operations/run_ingestion_noise.py
python operations/summarize_ingestion.py
python operations/run_ingestion_noise.py --batch-comparison
python operations/summarize_ingestion.py --batch-comparison
python operations/run_benchmark.py --ingest-concurrency 1 --ingest-policy retry --output docs/benchmarks/ingestion/retry-proof.json
python operations/run_benchmark.py --ingest-concurrency 1 --ingest-policy rate --output docs/benchmarks/ingestion/rate-proof.json
```

Run the revision baseline from the pre-batch ingestion implementation at commit 7f384b9 if reproducing the exact Phase 3A code path. Later code adds rate admission and header handling. Do not silently replace the original baseline artifacts with results from a changed implementation.

Keep REPORT_CACHE_BACKEND=off. No database migration is required for the Phase 3 endpoints. Existing migrations remain required for the Phase 2 revision table and Phase 1 indexes. [Architecture, capacity and current provider limits](../ARCHITECTURE.md).

All 41 Python tests passed on SQLite and disposable PostgreSQL with the lab dependency stack, retaining the original 35. All four browser scripts passed. Functional compatibility was also checked separately with cryptography 46.0.7 in an isolated environment. That check is not a new ingestion performance benchmark.
