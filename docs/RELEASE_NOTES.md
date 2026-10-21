# Release notes

## 14 October 2026 — Buffering, evidence and software reliability (staged / local)

- Added bounded LittleFS buffering of exact signed envelopes; gateway ACK deletion, FIFO reboot recovery, persistent assignment/pause state and debug-only `STATUS` / `PAUSE` / `ASSIGN` / `RESUME` commands. Sensors, Wi-Fi protocol, ATECC signing and USB flashing remain unchanged.
- Gateway now forwards every queued record in receive order, preserving the signed envelope and original gateway receipt time. Historical archived/blocked production rows remain untouched.
- Added version-2 evidence storage and real hash/link/signature checks, browser verification/export and an offline verifier. Legacy records remain readable and are never labelled hardware-verified without signatures. No blockchain or external anchor was introduced.
- Added admin-only existing-device/shipment/public-key binding; enrolled mismatches are rejected. Reuse retains old shipment history and requires matching firmware/gateway assignment and drained queues. Legacy unbound clients remain compatible until enrolled.
- Delayed gateway history is persisted without reverting newer live cards/seal/health state; existing live/detail paths, login, role boundaries, count/scroll fixes and 500 ms polling are retained.
- Added signed SNTP capture time with explicit unknown fallback; shared seal/UTC presentation, honest relative-light units and missing-MPU labels; startup preserves operational vehicle assignments. New reports use stored status/alert/temperature counts rather than fabricated performance percentages. No promised/actual delivery timestamps exist, so on-time delivery remains unavailable.
- Canonical user dashboard logic now synchronizes into the bundled portal without replacing parcel-aware HTML/CSS. Added local queue/upload/disk health and a read-only outbox inventory; no production record was requeued/deleted.
- A private PostgreSQL backup was successfully restored into an isolated authenticated local cluster (15,334 events). Added safe PostgreSQL regression runner and prepared pinned-action GitHub CI; remote CI has not run.
- Validation: 20 isolated Python regressions passed on SQLite and PostgreSQL, including real loopback HTTP `/ingest`, unsigned rejection, durable signed ACK and local-only health. Firmware compiled with Wi-Fi settings and without the private header. WebCrypto (including signed timestamp consistency), seal/UTC and report-contract tests, Python/JavaScript syntax and frontend build passed. Actual isolated Admin **and User** browser verification checked 3 records each with 0 integrity failures / 3 signatures and no JavaScript errors; report showed 3/3 stored readings, not the former placeholder. See backlog for remaining rollout checks.
- The protected staged API passed real login/detail/live/evidence reads with 30 existing ledger records. Primary API/frontend aliases remain unchanged. Staging applied additive telemetry/device columns/indexes to Supabase; event count remains 15,334 and app RLS remains enabled. Later report/timestamp-verifier changes are local, not yet in that staged deployment.
- **Hardware NOT TESTED / deferred at the operator's request:** no ESP32 is available, so no flashing, reboot, battery or new real-event acceptance. No Git staging/commit/push or legacy-tree changes. These improvements are not all finished or production-ready.

## 13 October 2026 — LDR interpretation and database incident

- Raw LDR ADC readings now map to increasing relative brightness while retaining the existing exposure boundary at 2500 ADC. The stored brightness is not calibrated lux.
- Added a regression check for dark/exposed polarity, seal state, and the live API's returned brightness. Eight security tests pass against an isolated temporary database.
- Restored production login and shipment APIs by moving the existing Vercel backend connection to Supabase PostgreSQL's TLS session pooler. Recovered the historical snapshot and verified one retained real gateway-event replay; newer cloud-only history remains incomplete. Render and the gateway outbox were left intact. See the deployment guide for recovery counts and verification limits.

## 28 September 2026

## Unified portal

- Shared SafeTrack login with cinematic truck video, audio replay and accessible motion fallback.
- Admin/user role routing on one origin with existing server authorization.
- Separate user sections and restored sensor-driven parcel visualization.
- Dedicated Vehicles page and corrected fleet/detail navigation.
- Independent admin data loading so slow alerts do not block the fleet list.
- Local gateway rotating logs and Windows gateway setup helpers.

## Validation

Production browser checks passed for role login, live shipment data, parcel rendering, video controls, mobile fallback and fleet navigation/search/detail flows. Alert API latency remains a known limitation. Demo values and visual summaries must not be presented as validated production fleet metrics.
