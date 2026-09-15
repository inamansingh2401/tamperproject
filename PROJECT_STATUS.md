# SafeTrack Project Status

## 1. Overall Status

SafeTrack is a working end-to-end prototype: a battery-powered ESP32-S3 sends ATECC-signed sensor events over Wi-Fi to a laptop gateway, which verifies and durably queues them before uploading to the existing Vercel FastAPI backend and PostgreSQL database. The deployed Admin dashboard has been verified with current telemetry and a populated 30-record event/hash ledger; the User dashboard uses the same retained API pipeline. USB event transport has been removed, while USB Serial remains available for development logs and firmware flashing. This is not production-ready: the laptop gateway is manually operated, local network addressing/configuration is fragile, backend deployment infrastructure is not reproducible from this repository alone, and endurance/security operations remain incomplete.

Status terms: **Implemented** means the code and a relevant check were observed; **Partially implemented** means core code exists but important field, scale, or operational verification remains; **Not implemented** means the expected capability is absent.

## 2. Component Status

| Component | Status | Relevant paths | Currently implemented | What remains |
|---|---|---|---|---|
| Firmware | Partially implemented | `firmware/tracksure_gateway/tracksure_gateway.ino`, `orientation.h` | Authoritative ESP32-S3 sketch reads sensors, signs events, delivers over Wi-Fi, validates matching gateway ACKs, retries retained events, and keeps Serial for debug/flashing only. | Long-duration battery testing, stable gateway discovery, RTC/deep sleep, and field recovery. |
| Sensors / MPU / LDR | Partially implemented | `firmware/tracksure_gateway/` | DHT11, filtered ADC brightness proxy, MPU6050 vectors/shock/orientation, and sensor retry logic. | Calibration, accuracy, drift, threshold, and extended fault testing. |
| Gateway | Partially implemented | `gateway/gateway.py`, `start-gateway.cmd` | Signed LAN `POST /ingest`, identity/signature validation, disk-backed SQLite outbox, matching ACK, HTTPS upload/retry, and local status. USB event ingestion is removed. | Automatic service startup, stable LAN addressing, monitoring, and review of latest-only backlog archival semantics. |
| Backend API | Implemented | `Tamper_admin/backend/main.py` | Existing authentication/domain routes and device-key/idempotent `POST /api/events`; live and historical shipment reads retained. | Broader integration/load testing and reproducible deployment configuration. |
| Database | Partially implemented | `Tamper_admin/backend/database.py`, `models.py` | PostgreSQL persistence is active; models cover users, devices, shipments, events, alerts, and settings. | Versioned migrations, backup/restore procedure, concurrency and migration testing. |
| Authentication | Implemented | `Tamper_admin/backend/auth.py`, frontend session code | Password hashing, JWT sessions, role checks, shipment assignment checks, and device API-key authentication. | Token revocation/refresh and production identity lifecycle controls. |
| Admin frontend | Partially implemented | `Tamper_admin/frontend/` | Deployed telemetry, shipment management, alerts, charts, orientation, and 30-record event/hash ledger. Ledger count and modal visibility regressions are fixed. | Wider browser/accessibility testing and removal of remaining static report data. |
| User frontend | Partially implemented | `Tamper_user/frontend/` | Assigned-shipment telemetry, history, charts, orientation, and live polling against the Vercel API. | Full deployed browser/authorization regression coverage. |
| Deployment / Vercel | Partially implemented | frontend `vercel.json` files; backend ASGI app | Vercel API and both static dashboard projects are live; Admin deployment and real event reads were verified. | Checked-in backend deployment manifest/IaC, documented environment ownership, monitoring, and recovery. |
| Tamper-evident logging | Partially implemented | firmware, `gateway.py`, `hashchain.py`, `models.py` | ATECC device signature is checked at the gateway; the original signed envelope is retained locally; backend stores an idempotent per-shipment hash-linked event ledger. | Backend-side signature provenance/audit storage, a full chain-audit tool, and retention/export policy. |

## 3. Working Data Flow

```text
ESP32-S3 sensors + ATECC508A
        -> signed HTTP over 2.4 GHz Wi-Fi
Laptop gateway :8765 POST /ingest
        -> identity/P-256 verification -> durable local outbox -> JSON ACK
        -> HTTPS POST /api/events
Vercel FastAPI backend -> PostgreSQL
        -> authenticated shipment live/detail APIs
Vercel Admin/User dashboards
```

The complete real-event path through Wi-Fi, gateway verification/ACK, HTTPS ingestion, PostgreSQL persistence, live API readback, and Admin dashboard telemetry/ledger rendering has been verified. USB does not carry events.

## 4. Known Issues / Risks

- The gateway must be started manually; when it is stopped, the ESP32 cannot reach `/ingest` and no cloud POST occurs.
- The laptop LAN address is DHCP-dependent and is stored only in ignored local firmware/gateway configuration; address changes can require configuration, firewall, and firmware updates.
- Gateway backlog handling keeps the newest queued sample for cloud delivery and archives older queued samples locally. It is durable local evidence, not guaranteed cloud upload of every sample.
- Gateway configuration, device key, enrolled public key, Wi-Fi credentials, database, logs, and outbox are intentionally local and absent from Git.
- The backend is deployed, but its Vercel project manifest and infrastructure configuration are not checked in.
- Backend startup performs schema creation/light migration rather than using a versioned migration framework.
- Device signatures are verified at the gateway, while the backend receives normalized telemetry and does not independently verify the original envelope.
- `tracksure_final_code.ino` is a historical, non-authoritative sketch; only the nested firmware sketch should be flashed.
- The adjacent `safetrack_Admin_SIH_Final/` workspace directory is legacy and outside this repository.
- The current hardware/software path is a prototype; endurance, load, offline duration, backup, monitoring, and operational security testing are incomplete.

## 5. Not Yet Implemented

- Stable gateway discovery or reserved-address provisioning.
- RTC-backed event time, deep sleep, and optional SD-card recovery.
- Versioned PostgreSQL migrations and automated managed-PostgreSQL integration tests.
- Reproducible backend deployment infrastructure.
- Backend-side storage/verification of the original device signature and a complete chain-audit/export tool.
- Automated hardware-in-loop, outage/endurance, and full deployed browser regression suites.

## 6. Next Recommended Work

1. Install the gateway as a monitored auto-start service and adopt a stable LAN address/discovery strategy.
2. Replace startup schema mutation with versioned PostgreSQL migrations plus backup/restore and integration tests.
3. Run controlled multi-hour battery, Wi-Fi interruption, backlog, and dashboard-latency testing with bounded telemetry.

## 7. Verification Notes

**Verification date:** 2026-09-16

Verified evidence includes: authoritative firmware compilation; battery-powered ESP32 Wi-Fi association/IP assignment; signed real-event delivery to the laptop `/ingest`; ATECC P-256 verification and matching ACK; gateway HTTPS `POST /api/events`; authenticated PostgreSQL-backed live/detail reads; deployed Admin telemetry cards; and a 30-row event/hash ledger that survives live polling and opens with its rows visible. Targeted gateway/security tests, Python and JavaScript syntax checks, and dashboard browser checks have passed during this work.

Not verified as production-grade: long-duration battery/network behavior, automatic gateway startup, every backlog record reaching the cloud, full managed-database migration/recovery, load/concurrency behavior, complete chain audits, and comprehensive cross-browser/accessibility coverage.
