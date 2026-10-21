# SafeTrack architecture map

## Scope and repository selection

This map covers the authoritative Git repository `tamperproject/`. The adjacent workspace directory the archived workspace snapshot is a legacy snapshot outside this repository and is not an active source tree. Generated firmware artifacts, local databases, credentials, logs, and deployment metadata are intentionally excluded.

## End-to-end data flow

1. The battery-powered ESP32-S3 firmware reads the same DHT11, LDR, and MPU6050, attaches persistent device/shipment assignment and per-boot identity/sequence metadata, signs the exact event bytes with the ATECC secure element, and commits a bounded LittleFS queue before Wi-Fi HTTP delivery to the laptop gateway's LAN `POST /ingest`. Reboot resumes committed records unchanged. USB Serial is debug/configuration/flashing only, never event transport.
2. The laptop gateway verifies P-256 signatures and enrollment values, commits its SQLite outbox, and returns the matching JSON ACK. A single FIFO worker uploads every queued payload plus its original envelope and gateway receipt time to the existing HTTPS `POST /api/events`, retrying transient failures. Historical archived/blocked records are retained untouched, not automatically recovered.
3. FastAPI retains device-key authentication and the same telemetry/alert normalization. Explicitly enrolled devices enforce shipment binding and public-key signature checks; legacy unbound devices remain compatible. Version-2 events store signed evidence and hash links. Signed SNTP generation time (when available), otherwise original gateway receipt time, orders live telemetry so delayed replay cannot overwrite newer state; chain order remains insertion order. Unsynchronized generation time remains explicitly unknown.
4. Admin and user browser clients authenticate with JWTs. Admin pages use CRUD/reporting endpoints; user pages can read only assigned shipment data. Live views poll shipment detail/live endpoints and render telemetry, history, status, charts, and package orientation.
5. The static frontends target `https://safetrack-api-live.vercel.app`; their Vercel files build/serve assets and apply browser security headers. The backend is written to use managed PostgreSQL through `DATABASE_URL`, but this repository has no backend `vercel.json` or other explicit backend deployment manifest.

## Future task domains

### Additions implemented locally on 14 October 2026

- `firmware/tracksure_gateway/durable_queue.h`: atomic committed flash records, checksums, FIFO reboot recovery, removal only after gateway ACK. Maximum 512 records; full/corrupt storage fails closed without erasing committed events.
- `Tamper_admin/backend/evidence.py`: canonical evidence hashing, legacy hash compatibility, signature/link verification, and independent JSON-export verifier.
- `GET /api/devices` and `PUT /api/devices/{device_id}/assignment`: admin-only enrollment using an existing device, existing shipment and public P-256 key. No device API keys are returned. Reuse requires paused/drained queues and matching firmware/gateway configuration.
- `GET /api/shipments/{code}/evidence`: authenticated, shipment-scoped, insertion-order paginated evidence/export route. Existing `/api/events`, shipment detail and 500 ms live polling are retained.
- `Tamper_admin/frontend/evidence.js` and its standalone-user copy: browser-side SHA-256/link/P-256 verification and evidence download. The active unified user dashboard is `Tamper_admin/frontend/user/dashboard.html` (with `dashboard.js`), not the older `Tamper_user/frontend/app.js`.
- PostgreSQL remains on Supabase through the existing TLS session pooler; no Supabase Auth or direct browser database access is introduced. Additive columns/indexes use the existing backend migration function; no existing table/data is deleted.

These additions are compile/test verified locally. A protected staged API deployment passed existing-account and existing-data reads; the primary alias remains unchanged. Its additive columns are present in Supabase with RLS retained and event count unchanged. Later local report changes have not been staged. Flashing and physical interruption/reboot/battery validation are deferred because the operator has no ESP32 available. Legacy hashes/signatures can be incomplete, and no external chain anchor exists. See `LIVE_GATEWAY_RUNBOOK.md` for safe rollout/reuse and `docs/IMPROVEMENTS.md` for completed/partial/pending work. `PROJECT_STATUS.md` is absent in the current checkout; status is maintained in README and `docs/RELEASE_NOTES.md` rather than recreating it.

Local operations: `operations/backup_database.py` makes private dumps and validates restoration into its own disposable PostgreSQL cluster; `inspect_outbox.py` reads metadata without leasing or changing rows; `run_postgres_tests.py` creates an isolated local regression database; `verify_cloud.py` performs bounded login/read checks, never telemetry uploads. Gateway `/status` reports queue/receipt/ACK ages, worker state and disk headroom locally. `.github/workflows/regression.yml` prepares isolated software and no-secret-header firmware CI; no GitHub run has occurred. Standalone user `dashboard.js`/`common.js` and `evidence.js` are canonical for the bundled user logic; parcel-aware HTML/CSS remains separate.

### Firmware / MPU / LDR

| Path | Responsibility | Data in â†’ data out |
|---|---|---|
| `tamperproject/firmware/tracksure_gateway/tracksure_gateway.ino` | Canonical ESP32-S3 device entry point: initializes DHT11, inverted LDR, MPU6050, ATECC, and optional local Wi-Fi settings; samples sensors, derives shock/orientation, signs and queues telemetry. | GPIO/I2C readings + identity + ignored Wi-Fi configuration + HTTP ACKs â†’ signed envelopes over Wi-Fi/LAN. USB Serial is debugging/flashing only. |
| `tamperproject/firmware/tracksure_gateway/orientation.h` | Orientation helper used by the canonical firmware for filtered/quaternion orientation state. | Accelerometer/gyroscope samples and elapsed time â†’ orientation values included in telemetry. |
| `tamperproject/tracksure_final_code.ino` | Retained non-authoritative historical USB/signed telemetry sketch. Do not flash for production; the canonical Wi-Fi sketch above is authoritative. | Historical DHT/LDR/MPU/ATECC readings + ACKs â†’ signed `TRACKSURE` serial records. |

### Gateway delivery

| Path | Responsibility | Data in â†’ data out |
|---|---|---|
| `tamperproject/gateway/gateway.py` | Gateway entry point; accepts signed HTTP `POST /ingest` records over a configured LAN bind, strictly parses and verifies them, persists a SQLite outbox, returns JSON ACKs after disk commits, uploads one ordered live record at a time, and exposes local `/status`. | Signed device envelope + ignored local config (`gateway.local.json`) â†’ local outbox row + matching JSON ACK + HTTPS `POST /api/events` + local status JSON. |
| `tamperproject/gateway/start-gateway.cmd` | Windows launcher for the gateway. | Command-line arguments â†’ `python gateway.py` process and console output. |
| `tamperproject/gateway/enable-wifi-firewall.ps1` | Optional Windows firewall setup for the gateway's signed Wi-Fi ingest listener. | Local firewall/network parameters â†’ Windows firewall rule permitting the configured gateway port. |
| `tamperproject/gateway/requirements.txt` | Pins gateway HTTP and crypto libraries. | Package installer â†’ `httpx` and `cryptography` runtime dependencies. |

Runtime-only inputs intentionally absent from version control: `gateway/gateway.local.json` supplies `cloud_url`, `device_id`, `shipment_code`, `device_key`, signature policy, and public-key path; the referenced enrolled public key and generated `gateway-outbox.db` also remain local.

### Backend API / database

| Path | Responsibility | Data in â†’ data out |
|---|---|---|
| `tamperproject/Tamper_admin/backend/main.py` | FastAPI application entry and complete route layer; configures CORS/security headers, seeds/migrates schema, enforces JWT roles, handles domain CRUD, ingests telemetry, validates chaining, updates shipment state, and raises alerts. | HTTP JSON/headers + authenticated user/device + SQLAlchemy session â†’ HTTP JSON/errors + database reads/writes. |
| `tamperproject/Tamper_admin/backend/database.py` | Selects SQLite or PostgreSQL from `DATABASE_URL`, creates the SQLAlchemy engine/session factory, and supplies request-scoped sessions. | Environment/database URL â†’ engine, schema base, and DB sessions. |
| `tamperproject/Tamper_admin/backend/models.py` | Persistence schema for users, enrolled devices, vehicles, shipments, sensor events, shipment alerts, and system settings. | ORM object changes â†’ relational rows/relationships; queries â†’ domain objects. |
| `tamperproject/Tamper_admin/backend/auth.py` | Password hashing/verification and JWT creation/decoding using environment-backed secrets and expiry. | Credentials/claims + `JWT_SECRET` â†’ password hashes or signed/decoded access tokens. |
| `tamperproject/Tamper_admin/backend/hashchain.py` | Produces deterministic event hashes linking telemetry records. | Shipment/device/sensor fields + previous hash â†’ SHA-256 event hash. |
| `tamperproject/Tamper_admin/backend/simulate_esp32.py` | Optional development producer that generates bounded sensor payloads and sends them to the ingest API. | Simulator configuration/state â†’ repeated `/api/events` requests. |
| `tamperproject/Tamper_admin/backend/migrate_sqlite_to_postgres.py` | One-time data migration utility from the local SQLite schema to the configured PostgreSQL database. | Local `safetrack.db` + target `DATABASE_URL` â†’ copied PostgreSQL rows/sequences. |
| `tamperproject/Tamper_admin/backend/requirements.txt` | Declares API, ORM, PostgreSQL, authentication, and validation dependencies. | Package installer â†’ backend Python runtime. |
| `tamperproject/Tamper_admin/run_all.py` | Local orchestration entry: starts Uvicorn, optional simulator, and static admin/user servers, then opens dashboards and coordinates shutdown. | Environment/CLI flag (`--simulator`) â†’ four local processes and browser pages. |

Route groups in `main.py`:

- `POST /api/auth/login`: credentials in; JWT, role, identity, and assigned shipment codes out.
- `GET /api/admin/dashboard`: admin token in; aggregate metrics out.
- `/api/vehicles` and `/api/vehicles/{vehicle_id}` plus assignment/removal actions: admin-authenticated vehicle CRUD and shipment links.
- `/api/shipments`, `/api/shipments/{code}`, and `/api/shipments/{code}/live`: admin/user-scoped shipment lists/details, latest telemetry, and event history; write operations are admin-only.
- `/api/alerts` and resolve actions: admin alert reads and resolution writes.
- `/api/users`: admin user CRUD/status operations.
- `/api/settings` and `/api/settings/change-password`: admin system preferences and credential changes.
- `GET /api/reports/summary`: admin reporting aggregates.
- `POST /api/events`: device-key-authenticated, idempotent telemetry ingestion; event/shipment/alert rows out.

### Dashboard UI

All browser-to-backend data uses JSON over HTTPS. Authentication state is held in `sessionStorage`; shared helpers remove legacy persistent `localStorage` sessions.

#### Admin frontend

| Path | Responsibility | Data in â†’ data out |
|---|---|---|
| `tamperproject/Tamper_admin/frontend/login.html` | Admin/user sign-in page shell. | User form input + shared styles/scripts â†’ login submission UI. |
| `tamperproject/Tamper_admin/frontend/login.js` | Calls login, stores returned session data, and routes users by role. | Username/password â†’ JWT/session fields â†’ admin or user dashboard navigation. |
| `tamperproject/Tamper_admin/frontend/index.html` | Main admin dashboard markup for KPIs, vehicles, alerts, and charts. | Controller-rendered domain data â†’ visible dashboard and navigation actions. |
| `tamperproject/Tamper_admin/frontend/script.js` | Loads vehicles, shipments, and alerts and renders dashboard tables, KPIs, filters, and charts. | `SafeTrackAPI` results + UI actions â†’ DOM/chart updates and API-triggering actions. |
| `tamperproject/Tamper_admin/frontend/shipments.html` | Shipment management and telemetry inspection page shell. | Shipment/controller state â†’ list, forms, inspector, and 3D package UI. |
| `tamperproject/Tamper_admin/frontend/shipments.js` | Shipment CRUD/filtering and live telemetry/orientation controller. | Shipment API data + form/inspection actions â†’ writes, tables, telemetry history, and Three.js orientation. |
| `tamperproject/Tamper_admin/frontend/vehicle-details.html` | Vehicle detail/assignment page shell. | Vehicle and shipment state â†’ details, charts, assignment controls. |
| `tamperproject/Tamper_admin/frontend/vehicle-details.js` | Loads one vehicle and related shipments and handles assignment/removal. | URL vehicle ID + API results/actions â†’ rendered detail and relationship mutations. |
| `tamperproject/Tamper_admin/frontend/alerts.html` | Alert management page shell. | Alert data/actions â†’ alert table and resolution controls. |
| `tamperproject/Tamper_admin/frontend/alerts.js` | Loads, filters, and resolves individual/all alerts. | Alert API results + user actions â†’ resolution requests and refreshed DOM. |
| `tamperproject/Tamper_admin/frontend/users.html` | User/role administration page shell. | User records/actions â†’ user table and edit/create controls. |
| `tamperproject/Tamper_admin/frontend/users.js` | User CRUD/status controller. | User API data + form actions â†’ user mutations and rendered table. |
| `tamperproject/Tamper_admin/frontend/settings.html` | System, notification, and security settings page shell. | Settings state/actions â†’ settings forms. |
| `tamperproject/Tamper_admin/frontend/settings.js` | Loads/saves settings and changes the admin password. | Settings/password forms + API values â†’ settings/password requests and UI feedback. |
| `tamperproject/Tamper_admin/frontend/reports.html` | Reports page shell. | Report/controller data â†’ report cards and charts. |
| `tamperproject/Tamper_admin/frontend/reports.js` | Initializes report visualizations; some displayed series are static while summary access exists in the shared API layer. | Page load (and any API-fed summary consumers) â†’ Chart.js graphics. |
| `tamperproject/Tamper_admin/frontend/live.html` | Compact live sensor monitor page shell. | Login/shipment selections â†’ latest values/history display. |
| `tamperproject/Tamper_admin/frontend/live.js` | Authenticates and repeatedly reads shipment detail for the selected shipment. | Credentials/JWT + shipment code â†’ telemetry/status/history DOM updates. |
| `tamperproject/Tamper_admin/frontend/api.js` | Central authenticated API client for vehicles, shipments/live data, alerts, users, settings, and reports. | Session JWT + method payloads â†’ HTTPS requests to cloud API â†’ normalized JSON/errors. |
| `tamperproject/Tamper_admin/frontend/auth.js` | Admin route guard and logout/role redirect logic. | Session token/role â†’ allowed page, login redirect, or user-dashboard redirect. |
| `tamperproject/Tamper_admin/frontend/common.js` | Shared timeout, output escaping, safe action dispatch, and responsive navigation/accessibility behavior. | DOM/events/fetch requests â†’ sanitized UI behavior and bounded network calls. |
| `tamperproject/Tamper_admin/frontend/style.css` | Shared custom admin visual styles. | CSS selectors/HTML state â†’ desktop presentation. |
| `tamperproject/Tamper_admin/frontend/mobile.css` | Responsive/mobile overrides shared by admin pages. | Viewport and DOM state â†’ mobile layout/navigation. |
| `tamperproject/Tamper_admin/frontend/tailwind.input.css` | Tailwind source stylesheet. | Tailwind directives/config/content scan â†’ compiled CSS input. |
| `tamperproject/Tamper_admin/frontend/tailwind.config.cjs` | Tailwind content/theme configuration. | HTML/JS source paths and theme values â†’ build-time class generation. |
| `tamperproject/Tamper_admin/frontend/tailwind.css` | Generated stylesheet served by the static frontend. | Tailwind build â†’ browser styling rules. |

#### User frontend

| Path | Responsibility | Data in â†’ data out |
|---|---|---|
| `tamperproject/Tamper_user/frontend/index.html` | Operator/user dashboard shell with shipment telemetry, charts, and 3D package view. | Controller-rendered assigned shipment data â†’ dashboard UI and user actions. |
| `tamperproject/Tamper_user/frontend/app.js` | Login/session flow, assigned-shipment reads, polling, charts, and MPU-driven package orientation. | Credentials/JWT + shipment API data â†’ authenticated dashboard, telemetry/history, charts, and Three.js pose. |
| `tamperproject/Tamper_user/frontend/live.html` | Compact live sensor monitor shell. | Login/shipment selection â†’ current telemetry and history table. |
| `tamperproject/Tamper_user/frontend/live.js` | Authenticates, constrains shipment choices by assignment, and polls `/shipments/{code}/live`. | Credentials/JWT + assigned shipment code â†’ live values, freshness, seal state, and history DOM. |
| `tamperproject/Tamper_user/frontend/common.js` | Shared timeout, escaping, session cleanup, and responsive navigation/accessibility behavior. | DOM/events/fetch requests â†’ safe responsive UI and bounded calls. |
| `tamperproject/Tamper_user/frontend/style.css` | Main user-dashboard styling. | HTML/DOM state â†’ desktop presentation. |
| `tamperproject/Tamper_user/frontend/mobile.css` | User-dashboard responsive overrides. | Viewport and DOM state â†’ mobile presentation. |

### Deployment / Vercel

| Path | Responsibility | Data in â†’ data out |
|---|---|---|
| `tamperproject/Tamper_admin/frontend/vercel.json` | Configures the admin static build/output and response security/cache headers; CSP permits the live API and required UI CDNs. | Vercel build/request context â†’ Tailwind build, static files, and HTTP headers. |
| `tamperproject/Tamper_admin/frontend/package.json` | Defines the admin Tailwind production build and its development dependency. | `npm run build` + source CSS/config â†’ minified `tailwind.css`. |
| `tamperproject/Tamper_admin/frontend/pnpm-lock.yaml` | Locks the frontend build dependency graph. | Package manager resolution â†’ reproducible installed build packages. |
| `tamperproject/Tamper_user/frontend/vercel.json` | Configures static user-site security/cache headers and allows connections to the live API. | Vercel request context â†’ static responses with CSP and security headers. |
| `tamperproject/Tamper_admin/backend/database.py` | Deployment-sensitive database adapter; translates provider PostgreSQL URLs and enables connection health checks. | Vercel/host `DATABASE_URL` â†’ PostgreSQL connection pool (or local SQLite fallback). |
| `tamperproject/Tamper_admin/backend/main.py` | ASGI application object (`app`) expected by an external Python deployment adapter. | Platform ASGI requests/environment â†’ API responses and managed-database access. |

Required production configuration inferred from code/docs includes `DATABASE_URL`, `JWT_SECRET`, and `DEVICE_API_KEY`. The gateway must carry the matching device key locally. Frontend API URLs and cross-site policy are currently hard-coded to the live API hostname.

## Important uncertainties

- **Firmware entry point:** `tamperproject/firmware/tracksure_gateway/tracksure_gateway.ino` is authoritative and was compiled/flashed for the verified Wi-Fi path. `tamperproject/tracksure_final_code.ino` is a retained, non-authoritative historical sketch and must not be used for production flashing.
- **Legacy workspace tree:** the adjacent the archived workspace snapshot directory remains outside this repository for historical recovery and must not be mixed into active changes.
- **Backend deployment:** the existing API is running on Vercel and was verified through `/api/events` and shipment live/detail reads. No checked-in backend Vercel manifest or infrastructure-as-code is present, so recreating that deployment still depends on external project configuration.
- **Gateway local configuration:** `gateway.local.json`, the enrolled public key, and runtime outbox are intentionally ignored, so enrollment values and the actual cloud target cannot be verified from committed files.
- **Admin live endpoint difference:** the compact admin live client reads `/shipments/{code}`, while the compact user live client reads `/shipments/{code}/live`; both route shapes exist, but their refresh semantics differ.
- **Verified dashboard behavior:** the Admin shipment inspector renders current telemetry and the 30-record hash ledger. Live polling preserves the ledger count, and opening the modal scrolls the existing ledger rows into view.
