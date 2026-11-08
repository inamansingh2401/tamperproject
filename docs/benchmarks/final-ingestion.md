# Final-code ingestion experiment — INCOMPLETE

Stopped at the operator request. This is descriptive partial evidence, not a completed five-run noise comparison, final capacity estimate or replay/authentication overhead claim. Nothing was deployed.

## Scope

The unchanged final API was exercised using software P-256 signatures against disposable loopback PostgreSQL clusters. Each case used the same deterministic 100k-event seed and original request/pool settings, plus signed warmups. Compatibility and strict replay/digest-credential modes were interleaved with single-event and ten-event requests at the requested concurrency levels. Caching stayed OFF and revision writes stayed ON. Client signing/startup were excluded. Existing API accounts, passwords and hosted databases were untouched.

Completed 36 cases, storing 14,400 timed events with zero timed request errors. Only two complete rounds and the concurrency-one portion of the next round finished. The remaining rounds were not run.

## Partial observations

Each cell reports the median of available run metrics [minimum, maximum]. Batch p50/p95 describe the whole request, not latency per event. These are not five-run estimates.

| Mode | Concurrency | Events/request | Completed runs | Events/sec | p50 ms | p95 ms | SQL/request |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| counter_v1 | 1 | 1 | 3 | 49.07 [33.17, 65.40] | 20.52 [14.14, 29.63] | 25.02 [22.83, 34.00] | 13.1525 |
| legacy | 1 | 1 | 3 | 66.24 [44.84, 77.66] | 14.87 [12.46, 22.07] | 17.08 [15.29, 25.49] | 10.0525 |
| counter_v1 | 1 | 10 | 3 | 84.74 [64.15, 121.90] | 118.19 [78.53, 156.84] | 129.99 [100.82, 170.97] | 112.5250 |
| legacy | 1 | 10 | 3 | 155.72 [138.69, 163.67] | 63.27 [60.04, 74.80] | 71.63 [68.85, 81.47] | 81.5250 |
| counter_v1 | 5 | 1 | 2 | 79.70 [72.74, 86.67] | 60.88 [54.83, 66.92] | 80.56 [74.63, 86.50] | 13.1525 |
| legacy | 5 | 1 | 2 | 60.53 [45.13, 75.94] | 84.77 [63.25, 106.29] | 122.72 [92.46, 152.97] | 10.0525 |
| counter_v1 | 5 | 10 | 2 | 145.53 [119.26, 171.80] | 352.17 [285.81, 418.52] | 423.84 [330.77, 516.91] | 112.5250 |
| legacy | 5 | 10 | 2 | 199.69 [167.03, 232.36] | 251.97 [209.48, 294.46] | 301.46 [250.56, 352.36] | 81.5250 |
| counter_v1 | 10 | 1 | 2 | 75.93 [74.40, 77.45] | 126.91 [124.42, 129.39] | 185.52 [177.43, 193.61] | 13.1525 |
| legacy | 10 | 1 | 2 | 95.42 [90.93, 99.91] | 99.00 [94.50, 103.50] | 154.53 [148.38, 160.69] | 10.0525 |
| counter_v1 | 10 | 10 | 2 | 120.87 [118.34, 123.40] | 825.09 [799.84, 850.34] | 937.21 [928.67, 945.75] | 112.5250 |
| legacy | 10 | 10 | 2 | 148.17 [142.61, 153.72] | 626.93 [620.40, 633.46] | 852.03 [747.53, 956.53] | 81.5250 |
| counter_v1 | 20 | 1 | 2 | 39.90 [39.52, 40.28] | 453.98 [448.83, 459.12] | 773.90 [754.65, 793.14] | 13.1525 |
| legacy | 20 | 1 | 2 | 46.08 [46.07, 46.09] | 402.85 [398.09, 407.62] | 587.84 [562.24, 613.45] | 10.0525 |
| counter_v1 | 20 | 10 | 2 | 74.56 [68.00, 81.12] | 2295.13 [2233.07, 2357.20] | 3075.47 [2863.18, 3287.75] | 112.5250 |
| legacy | 20 | 10 | 2 | 116.78 [80.06, 153.50] | 1515.36 [1156.74, 1873.97] | 2232.42 [1510.89, 2953.95] | 81.5250 |

## Interpretation and pending work

The completed cases exercise strict replay successfully and show additional SQL work. The incomplete timing sample cannot establish a stable overhead percentage outside noise. Do not compare these partial medians with historical Phase 3 values as a controlled causal estimate. Phase 3 already included signature verification; it did not include the new replay ledger. The completed historical five-run results remain separately labeled in [Phase 3](phase3.md).

All raw per-case JSON and [partial summary](final-ingestion/partial-summary.json) are retained. Finish a full matched experiment before replacing this report with a five-run conclusion. The runner refuses to overwrite existing measurements: choose a fresh `--output-dir`. The summarizer requires a complete set of runs. No secure-element signing, WAN/TLS, hosted capacity or sustained fleet measurement is included.
