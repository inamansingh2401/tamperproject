# Phase 4 dependency decision

Chose option 2: support cryptography 50. Both Python requirements now declare `cryptography>=50.0.1,<51`. On the measured version, 50.0.1 / Python 3.13.7 / Windows, all 41 original tests passed again on SQLite (9.757 s) and isolated PostgreSQL (5.744 s). Suite durations are verification timings, not performance benchmarks.

The existing five-run interleaved measurements in [Phase 3](../benchmarks/phase3.md) use this now-declared version: concurrency 10 single-event median throughput 75.95 events/s versus batches of 10 at 141.45 events/s; run ranges 59.06–93.51 versus 131.68–160.19. These describe the Phase 3 write path, local software P-256 signatures and caching off. They do not measure Phase 4 controls, hosted infrastructure or ATECC508A hardware.

[Release notes](https://cryptography.io/en/latest/changelog/) document 50.0.0 security fixes and 50.0.1's OpenSSL wheel update. The application uses supported P-256 ECDSA, SHA-256, public-point serialization and DSS encoding; it does not use the removed APIs. [Platform support](https://cryptography.io/en/latest/installation/) includes this Python/platform combination. Future major versions require renewed verification.

The pre-change requirements audit resolved 46.0.7 and returned seven advisory entries in one package, with three PYSEC IDs each repeated. These are four distinct advisory IDs, not seven distinct vulnerabilities. Raw evidence: `pip-audit-before.json`. Final audit results are recorded separately.
