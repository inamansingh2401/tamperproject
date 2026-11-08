# Phase 4 local verification

Scope: Windows/Python 3.13.7, local SQLite and disposable loopback PostgreSQL 18.6, software-generated P-256 signatures. No hosted database, deployment or hardware-signing measurement. The current ingestion comparison was stopped incomplete; see [partial results](../benchmarks/final-ingestion.md). Caching remains OFF by default and no deployment setting was enabled.

## A. Declared cryptography version

Chose option 2: verify and support the newer version. Cryptography 50.0.1 passed the original 41 tests on SQLite and PostgreSQL before implementation; backend and gateway now both declare `>=50.0.1,<51`. Final security tests also use 50.0.1. See [the dependency decision](dependencies.md).

The existing five-run interleaved Phase 3 comparison used 50.0.1: concurrency-10 median throughput 75.95 events/s single versus 141.45 events/s for batches of 10, run ranges 59.06–93.51 versus 131.68–160.19. These ranges do not overlap. This is a measurement of **Phase 3 software**, with the 100k-event local seed, not a performance measurement of the new replay ledger/security controls. The Phase 4 throughput/noise comparison remains incomplete; ledger storage cost, hardware signing and hosted latency remain unmeasured. Other performance claims remain subject to the Phase 1 five-run noise qualifications.

## B. Threat model

[SECURITY.md](../SECURITY.md) covers assets, trust boundaries, all four requested attacker types, controls, residual risks and an OWASP 2025 checklist. The independent source review identified forged local gateway ACKs and privileged history deletion as material limitations. No immutable-retention or physical-truth claim is made.

## C. Verification results

| Check | Result |
|---|---|
| Original regressions | All original 41 tests retained and passing on both databases |
| Full PostgreSQL suite | 59 tests passed, including actual browser roles/RLS and a separate fresh Alembic upgrade/check/downgrade database |
| Full SQLite suite | 59 discovered: 57 passed, two PostgreSQL-only tests skipped |
| Existing browser logic scripts | All four passed: reports, WebCrypto evidence, UI state, alert pagination |
| Frontend production build | Passed after the two transitive dependency patches; no generated UI/JS diff |
| Actual installed application dependency audit | No known vulnerabilities reported after updating PyJWT/certifi; cryptography remains 50.0.1 |
| Fresh requirements resolution audit | No known vulnerabilities reported; resolves crypto 50.0.2, a different version from the measured/tested runtime |
| Actual frontend pnpm lock audit | Two advisories before; none reported after patching source-map-js and postcss-selector-parser |
| Isolated npm audit | No known vulnerabilities in fresh npm resolution; not evidence about the old pnpm lock |

The tests cover replay/reordering/delay/window expiry, lost-ACK idempotency, nonce transaction rollback, registration/revocation/rotation, chain row edits/deletion/reordering, external checkpoints, all implemented field bounds/body limits, credential redaction, origin/header controls, JWT algorithm/expiry checks, environment-only gateway credentials and browser-role isolation. Tests do not establish hosted behavior, multi-process throughput or hardware reliability. The four browser scripts are Node logic tests, not four real-browser end-to-end runs.

Commands executed from the repo root:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python operations/run_postgres_tests.py
node tests/test_reports.cjs
node tests/test_evidence.cjs
node tests/test_ui_state.cjs
node tests/test_alert_pagination.cjs
pnpm --dir Tamper_admin/frontend build
```

Audit commands and raw reports are linked from SECURITY.md; `runtime-requirements.txt` records the actual installed dependency closure. Security checks are pass/fail observations, not statistically estimated speedups. No number of advisory entries is presented as a count of distinct exploitable vulnerabilities.

## D. Manual work and honest limits

Follow [the rollout guide](rollout.md): pause/retain queued ingestion, back up data **and ACL/policy state**, migrate before starting the new app, verify deployment roles, provision environment-only gateway credentials, and explicitly enroll/rotate devices. Existing devices remain `legacy` until then. New strict devices need the firmware's signed epoch and timestamp support; current NVS boot counting still needs physical reboot/power-loss verification. Handle per-item batch ACKs, counter/epoch persistence/reset recovery and authenticated cloud-custody acknowledgments in firmware. Keep caches off.

ATECC508A performance/configuration is not measured. Supabase hosted policy behavior/TLS/deployment settings are not verified. Counter-ledger overhead is not benchmarked. A compromised signer can report false readings; a compromised gateway can drop evidence or forge the existing local ACK; an administrator/database owner can erase history. Suffix/all-history deletion requires an independently trusted checkpoint for detection. MFA, login throttling, immutable audit logging and external transparency anchoring remain absent.

## Resume-safe bullets

- Added transactional replay protection and device registration/revocation/rotation while preserving lost-ACK retries; expanded the local regression suite from 41 to 59 PostgreSQL tests.
- Built shipment-chain verification with tested detection of modified, interior-deleted and reordered records, plus external-checkpoint detection of deleted history suffixes using software P-256 signatures.
- Isolated browser database roles with locally tested restrictive RLS and patched audited Python/build dependencies; final installed-runtime and pnpm-lock audits reported no known vulnerabilities.
