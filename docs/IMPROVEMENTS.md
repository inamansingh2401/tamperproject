# SafeTrack engineering improvement backlog

Updated 14 October 2026. Keep the core architecture: battery ESP32-S3 → Wi-Fi → laptop gateway :8765 → existing HTTPS `/api/events` → PostgreSQL → existing Admin/User dashboards. This is a scoped implementation review, not an exhaustive security audit of every repository file.

## Implemented locally in this change

| Improvement | Implementation | Verification / remaining acceptance |
|---|---|---|
| Reboot-safe evidence delivery | Bounded, checksummed LittleFS queue; exact envelope replay; persistent boot count and per-boot unique IDs; gateway ACK removes only the corresponding record. Gateway FIFO uploads every queued event. | Firmware compiles; gateway restart/FIFO/retry/idempotency tests pass. Real power-cut/flash-wear/corrupt-storage tests remain. |
| Real evidence verification | Preserved signed envelopes + public-key snapshots, versioned hashes, authenticated paginated evidence/export, browser WebCrypto checks and offline verification. Legacy signatures are unavailable, not invented. | Tamper/link/signature tests and both browser previews pass. No external anchor; legacy formatting/history may be incomplete. |
| Exact device ↔ shipment routing and reuse | Admin binding, signed shipment validation, persisted ESP32 assignment/pause, drained-queue reuse, old history retained; dashboards use existing shipment endpoints. | Binding, wrong-shipment rejection, duplicate ACK recovery, old/new-history isolation tests pass. Operator must match all three configurations; production device enrollment not changed. |

## Remaining work, in priority order

### Progress on the requested sequence

| Step | Current state (14 October) | Remaining |
|---|---|---|
| 1. Staged rollout / physical acceptance | PARTIAL: protected staged API login/live/30-record history/evidence reads passed; primary aliases unchanged. | Frontend/current-source staging and controlled promotion; physical tests deferred because no ESP32 is available. |
| 2. Consistent seal states | IMPLEMENTED locally: shared normalization and admin/user presentation checks. | Production frontend rollout. |
| 3. Honest generation timestamps | PARTIAL: signed SNTP UTC, explicit unknown fallback, separate receipt/arrival context. | Authenticated clock/RTC and offline-reboot hardware validation. |
| 4. Assignment safety/audit | PARTIAL: exact binding, device-side pause/drain and history isolation exist. | Persistent assignment audit and interrupted provisioning coordinator; drain confirmation is still an operator assertion. |
| 5. Stable gateway discovery | NOT IMPLEMENTED. Existing LAN address configuration is retained. | DHCP reservation/discovery, cross-network validation. No permanent IP assumption. |
| 6. Delivery health | PARTIAL: local worker-enabled/alive, queue/verified receipt/ACK age and disk headroom. | Dashboard health/stall alerts, upload timing and sensor diagnostics. |
| 7. Capacity / endurance | PARTIAL: bounded non-overwriting flash queue and fail-closed corruption behavior. | Gap counters and physical throughput/flash-wear/battery measurements. |
| 8. Safe recovery tools | PARTIAL: read-only outbox integrity/count/candidate inventory. | Reviewed bounded recovery/export and corrupt-device record retrieval; no production replay performed. |
| 9. Individual credential lifecycle | NOT IMPLEMENTED beyond existing enrollment/key authentication. | Coordinated rotation/revocation without stranding offline events; no credentials rotated blindly. |
| 10. Backups / migrations | PARTIAL: private backup + isolated restore drill passed; migration failures stop startup. | Versioned out-of-band migrations, concurrent upgrade tests, scheduled/offsite retention. |
| 11. Honest units / UTC / sensor validity | IMPLEMENTED locally for updated views/API metadata. Unknown legacy units and unavailable MPU readings are labelled. | Production rollout and physical calibration; do not treat LDR as lux or SNTP as trusted RTC. |
| 12. Real report metrics | IMPLEMENTED locally for Reports: stored status/alert/temperature counts; unsupported on-time metrics unavailable. | Deployment; broader demo fleet summaries still need review. |
| 13. Regression CI | PARTIAL: 20 tests pass on isolated SQLite/PostgreSQL, including bounded real HTTP `/ingest`/ACK/signature checks; WebCrypto/UI/report contracts; pinned-action CI prepared. | First remote CI run, automated browser/concurrency/migration coverage. Firmware compilation is not hardware acceptance. |
| 14. User logic drift | IMPLEMENTED locally: canonical standalone dashboard/common/evidence logic synced to bundled portal. | Deploy/recheck both shells; parcel-aware HTML/CSS remains intentionally distinct. |
| 15. Battery / enclosure | NOT TESTED; explicitly deferred by operator. | Device runtime, brownout, charging, mounting and interruption acceptance. |

### Remaining engineering backlog

| Priority | Improvement | Relevant module / reason |
|---|---|---|
| P0 | Controlled staged rollout and physical reboot acceptance | Runbook/backend/gateway/firmware: backup, additive migrations, public-key enrollment, non-erasing flash, one independently powered offline→reboot→retry test. Local tests cannot establish hardware acceptance. |
| P0 | Trusted timing across offline reboot | Signed SNTP generation time/unknown fallback is implemented locally. Add RTC/authenticated synchronization and hardware validation; unknown generation time still falls back to receipt timing. |
| P0 | Recover newer historical data separately | Recovery/outbox: review retained archived records against cloud IDs and enrolled keys; use bounded, idempotent, reviewed recovery. Do not automatically requeue the production archive. September snapshot recovery is not complete current history. |
| P1 | Reliable gateway addressing and onboarding | Firmware/private configuration: DHCP reservation/discovery and validated setup rather than fixed laptop IPs. Add authenticated remote provisioning only with an explicit security design; do not reintroduce USB events. |
| P1 | Backlog capacity, throughput and flash endurance | `durable_queue.h`, gateway worker: measure delivery rate vs 1 Hz capture, flash wear, filesystem overhead and battery use; configure retention/cadence and expose full-buffer/sample-gap counters. Bounded buffering is not unlimited lossless capture. |
| P1 | Dead-letter and corruption recovery tools | Device flash/gateway: review/export blocked or corrupt evidence with explicit operator actions and audit trail. Never silently drop a blocking record or format retained flash. |
| P1 | Provisioning transaction / assignment audit | Device enrollment: persist actor/time/old/new assignment, prove queues drained where practical, surface all three configurations, and make interrupted reassignment recoverable. Current confirmation is an operator assertion. |
| P1 | Versioned, fail-fast database migrations | Backend startup: move reviewed schema evolution out of request/cold-start paths; test upgrade on restored PostgreSQL and concurrent instances. Avoid swallowing failed migrations. Preserve existing RLS and server-only database access. |
| P1 | Expand remaining regression coverage / CI | Isolated PostgreSQL/HTTP ingest and no-secret-header firmware compile now pass. Add concurrency, automated browser, migration/rollback, assignment interruption and physical flash/reboot coverage. Pin remaining runtime dependencies. |
| P1 | Device credential lifecycle and enforcement | Backend/gateway: finish enrolling real devices, use individually scoped/rotatable device keys, define reviewed key rotation/revocation and signing-key trust anchors. Keep compatible legacy mode explicit rather than treating unbound clients as fully enrolled. Rotate credentials shared outside trusted storage separately. |
| P1 | Operational health instead of a generic connected banner | Gateway/API/UI: expose queue depth/oldest age/blocked errors, last verified event age, upload latency, disk pressure and sensor health; alert when cloud delivery stalls even if live GET requests return 200. |
| P2 | Threshold configuration with calibration/version metadata | Sensor rules/settings: make thresholds genuinely configurable, calibrate against hardware tests, and preserve rule/calibration version per event. Do not silently change established alert boundaries. |
| P2 | Larger, resumable evidence exports | Evidence API/browser: stream/paginate exports, support cancellation/resume and fixed snapshot boundaries; current browser retains the complete verified export in memory and has a bounded page limit. |
| P2 | External trust anchors and independently pinned keys | Evidence: publish/safely retain signed checkpoints and enrollment key fingerprints to detect history truncation/server rewriting. No need to add blockchain or replace PostgreSQL. |
| P2 | Review remaining placeholder fleet summaries | Reports now uses stored-data metrics. Other admin summaries/demo series need separate review; working telemetry does not validate operational analytics. |
| P2 | Automated uptime/backup operations | Manual private backup/isolated restore drill passed. Add scheduled reviewed exports, encrypted offsite retention, restore alerts and realistic hosted-plan limits. A free provider is not a retention/uptime guarantee. |
| P2 | Battery and physical enclosure validation | Firmware/hardware: measure runtime, brownout behavior, charging safety, sensor mounting, tamper response and recovery. Add power-aware sampling/deep sleep only after protecting current delivery semantics. |

Only the explicitly implemented/verified portions above are complete. Hardware work is deferred, not passed; staged reads are not a new physical E2E test. Primary aliases, production outbox and historical tree remain unchanged. No production-ready or zero-loss guarantee is made.
