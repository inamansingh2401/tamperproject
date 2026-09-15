# SafeTrack architecture map

## Scope and repository selection

This map covers the authoritative Git repository `tamperproject/`. The adjacent workspace directory `safetrack_Admin_SIH_Final/` is a legacy snapshot outside this repository and is not an active source tree. Generated firmware artifacts, local databases, credentials, logs, and deployment metadata are intentionally excluded.

## End-to-end data flow

1. The battery-powered ESP32-S3 firmware reads the DHT11, LDR, and MPU6050, derives shock/orientation values, attaches device/shipment identity and sequence metadata, signs the exact event bytes with the ATECC secure element, and sends the signed envelope by HTTP over 2.4 GHz Wi-Fi to the laptop gateway's LAN `POST /ingest` endpoint. USB Serial is available only for firmware flashing and debug logs.
2. The laptop gateway verifies the P-256 signature and enrollment values, commits the event to a local SQLite outbox, then returns JSON containing `status: success` and the matching `event_id`. It uploads the normalized payload over HTTPS to `POST /api/events` with a device key and idempotency key, retrying transient failures.
3. FastAPI authenticates the device, validates the event and per-shipment hash-chain relationship, updates shipment state, stores the sensor event, and creates alerts when thresholds or seal/shock conditions require them.
4. Admin and user browser clients authenticate with JWTs. Admin pages use CRUD/reporting endpoints; user pages can read only assigned shipment data. Live views poll shipment detail/live endpoints and render telemetry, history, status, charts, and package orientation.
5. The static frontends target `https://safetrack-api-live.vercel.app`; their Vercel files build/serve assets and apply browser security headers. The backend is written to use managed PostgreSQL through `DATABASE_URL`, but this repository has no backend `vercel.json` or other explicit backend deployment manifest.

## Future task domains

### Firmware / MPU / LDR

| Path | Responsibility | Data in → data out |
|---|---|---|
| `tamperproject/firmware/tracksure_gateway/tracksure_gateway.ino` | Canonical ESP32-S3 device entry point: initializes DHT11, inverted LDR, MPU6050, ATECC, and optional local Wi-Fi settings; samples sensors, derives shock/orientation, signs and queues telemetry. | GPIO/I2C readings + identity + ignored Wi-Fi configuration + HTTP ACKs → signed envelopes over Wi-Fi/LAN. USB Serial is debugging/flashing only. |
| `tamperproject/firmware/tracksure_gateway/orientation.h` | Orientation helper used by the canonical firmware for filtered/quaternion orientation state. | Accelerometer/gyroscope samples and elapsed time → orientation values included in telemetry. |
| `tamperproject/tracksure_final_code.ino` | Root-level alternate firmware entry with substantially the same USB/signed telemetry role. Its presence makes the authoritative sketch ambiguous. | DHT/LDR/MPU/ATECC readings + ACKs → signed `TRACKSURE` serial records. |

### Gateway delivery

| Path | Responsibility | Data in → data out |
|---|---|---|
| `tamperproject/gateway/gateway.py` | Gateway entry point; accepts signed HTTP `POST /ingest` records over a configured LAN bind, strictly parses and verifies them, persists a SQLite outbox, returns JSON ACKs after disk commits, uploads one ordered live record at a time, and exposes local `/status`. | Signed device envelope + ignored local config (`gateway.local.json`) → local outbox row + matching JSON ACK + HTTPS `POST /api/events` + local status JSON. |
| `tamperproject/gateway/start-gateway.cmd` | Windows launcher for the gateway. | Command-line arguments → `python gateway.py` process and console output. |
| `tamperproject/gateway/enable-wifi-firewall.ps1` | Optional Windows firewall setup for the gateway's signed Wi-Fi ingest listener. | Local firewall/network parameters → Windows firewall rule permitting the configured gateway port. |
| `tamperproject/gateway/requirements.txt` | Pins gateway HTTP and crypto libraries. | Package installer → `httpx` and `cryptography` runtime dependencies. |

Runtime-only inputs intentionally absent from version control: `gateway/gateway.local.json` supplies `cloud_url`, `device_id`, `shipment_code`, `device_key`, signature policy, and public-key path; the referenced enrolled public key and generated `gateway-outbox.db` also remain local.

### Backend API / database

| Path | Responsibility | Data in → data out |
|---|---|---|
| `tamperproject/Tamper_admin/backend/main.py` | FastAPI application entry and complete route layer; configures CORS/security headers, seeds/migrates schema, enforces JWT roles, handles domain CRUD, ingests telemetry, validates chaining, updates shipment state, and raises alerts. | HTTP JSON/headers + authenticated user/device + SQLAlchemy session → HTTP JSON/errors + database reads/writes. |
| `tamperproject/Tamper_admin/backend/database.py` | Selects SQLite or PostgreSQL from `DATABASE_URL`, creates the SQLAlchemy engine/session factory, and supplies request-scoped sessions. | Environment/database URL → engine, schema base, and DB sessions. |
| `tamperproject/Tamper_admin/backend/models.py` | Persistence schema for users, enrolled devices, vehicles, shipments, sensor events, shipment alerts, and system settings. | ORM object changes → relational rows/relationships; queries → domain objects. |
| `tamperproject/Tamper_admin/backend/auth.py` | Password hashing/verification and JWT creation/decoding using environment-backed secrets and expiry. | Credentials/claims + `JWT_SECRET` → password hashes or signed/decoded access tokens. |
| `tamperproject/Tamper_admin/backend/hashchain.py` | Produces deterministic event hashes linking telemetry records. | Shipment/device/sensor fields + previous hash → SHA-256 event hash. |
| `tamperproject/Tamper_admin/backend/simulate_esp32.py` | Optional development producer that generates bounded sensor payloads and sends them to the ingest API. | Simulator configuration/state → repeated `/api/events` requests. |
| `tamperproject/Tamper_admin/backend/migrate_sqlite_to_postgres.py` | One-time data migration utility from the local SQLite schema to the configured PostgreSQL database. | Local `safetrack.db` + target `DATABASE_URL` → copied PostgreSQL rows/sequences. |
| `tamperproject/Tamper_admin/backend/requirements.txt` | Declares API, ORM, PostgreSQL, authentication, and validation dependencies. | Package installer → backend Python runtime. |
| `tamperproject/Tamper_admin/run_all.py` | Local orchestration entry: starts Uvicorn, optional simulator, and static admin/user servers, then opens dashboards and coordinates shutdown. | Environment/CLI flag (`--simulator`) → four local processes and browser pages. |

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

| Path | Responsibility | Data in → data out |
|---|---|---|
| `tamperproject/Tamper_admin/frontend/login.html` | Admin/user sign-in page shell. | User form input + shared styles/scripts → login submission UI. |
| `tamperproject/Tamper_admin/frontend/login.js` | Calls login, stores returned session data, and routes users by role. | Username/password → JWT/session fields → admin or user dashboard navigation. |
| `tamperproject/Tamper_admin/frontend/index.html` | Main admin dashboard markup for KPIs, vehicles, alerts, and charts. | Controller-rendered domain data → visible dashboard and navigation actions. |
| `tamperproject/Tamper_admin/frontend/script.js` | Loads vehicles, shipments, and alerts and renders dashboard tables, KPIs, filters, and charts. | `SafeTrackAPI` results + UI actions → DOM/chart updates and API-triggering actions. |
| `tamperproject/Tamper_admin/frontend/shipments.html` | Shipment management and telemetry inspection page shell. | Shipment/controller state → list, forms, inspector, and 3D package UI. |
| `tamperproject/Tamper_admin/frontend/shipments.js` | Shipment CRUD/filtering and live telemetry/orientation controller. | Shipment API data + form/inspection actions → writes, tables, telemetry history, and Three.js orientation. |
| `tamperproject/Tamper_admin/frontend/vehicle-details.html` | Vehicle detail/assignment page shell. | Vehicle and shipment state → details, charts, assignment controls. |
| `tamperproject/Tamper_admin/frontend/vehicle-details.js` | Loads one vehicle and related shipments and handles assignment/removal. | URL vehicle ID + API results/actions → rendered detail and relationship mutations. |
| `tamperproject/Tamper_admin/frontend/alerts.html` | Alert management page shell. | Alert data/actions → alert table and resolution controls. |
| `tamperproject/Tamper_admin/frontend/alerts.js` | Loads, filters, and resolves individual/all alerts. | Alert API results + user actions → resolution requests and refreshed DOM. |
| `tamperproject/Tamper_admin/frontend/users.html` | User/role administration page shell. | User records/actions → user table and edit/create controls. |
| `tamperproject/Tamper_admin/frontend/users.js` | User CRUD/status controller. | User API data + form actions → user mutations and rendered table. |
| `tamperproject/Tamper_admin/frontend/settings.html` | System, notification, and security settings page shell. | Settings state/actions → settings forms. |
| `tamperproject/Tamper_admin/frontend/settings.js` | Loads/saves settings and changes the admin password. | Settings/password forms + API values → settings/password requests and UI feedback. |
| `tamperproject/Tamper_admin/frontend/reports.html` | Reports page shell. | Report/controller data → report cards and charts. |
| `tamperproject/Tamper_admin/frontend/reports.js` | Initializes report visualizations; some displayed series are static while summary access exists in the shared API layer. | Page load (and any API-fed summary consumers) → Chart.js graphics. |
| `tamperproject/Tamper_admin/frontend/live.html` | Compact live sensor monitor page shell. | Login/shipment selections → latest values/history display. |
| `tamperproject/Tamper_admin/frontend/live.js` | Authenticates and repeatedly reads shipment detail for the selected shipment. | Credentials/JWT + shipment code → telemetry/status/history DOM updates. |
| `tamperproject/Tamper_admin/frontend/api.js` | Central authenticated API client for vehicles, shipments/live data, alerts, users, settings, and reports. | Session JWT + method payloads → HTTPS requests to cloud API → normalized JSON/errors. |
| `tamperproject/Tamper_admin/frontend/auth.js` | Admin route guard and logout/role redirect logic. | Session token/role → allowed page, login redirect, or user-dashboard redirect. |
| `tamperproject/Tamper_admin/frontend/common.js` | Shared timeout, output escaping, safe action dispatch, and responsive navigation/accessibility behavior. | DOM/events/fetch requests → sanitized UI behavior and bounded network calls. |
| `tamperproject/Tamper_admin/frontend/style.css` | Shared custom admin visual styles. | CSS selectors/HTML state → desktop presentation. |
| `tamperproject/Tamper_admin/frontend/mobile.css` | Responsive/mobile overrides shared by admin pages. | Viewport and DOM state → mobile layout/navigation. |
| `tamperproject/Tamper_admin/frontend/tailwind.input.css` | Tailwind source stylesheet. | Tailwind directives/config/content scan → compiled CSS input. |
| `tamperproject/Tamper_admin/frontend/tailwind.config.cjs` | Tailwind content/theme configuration. | HTML/JS source paths and theme values → build-time class generation. |
| `tamperproject/Tamper_admin/frontend/tailwind.css` | Generated stylesheet served by the static frontend. | Tailwind build → browser styling rules. |

#### User frontend

| Path | Responsibility | Data in → data out |
|---|---|---|
| `tamperproject/Tamper_user/frontend/index.html` | Operator/user dashboard shell with shipment telemetry, charts, and 3D package view. | Controller-rendered assigned shipment data → dashboard UI and user actions. |
| `tamperproject/Tamper_user/frontend/app.js` | Login/session flow, assigned-shipment reads, polling, charts, and MPU-driven package orientation. | Credentials/JWT + shipment API data → authenticated dashboard, telemetry/history, charts, and Three.js pose. |
| `tamperproject/Tamper_user/frontend/live.html` | Compact live sensor monitor shell. | Login/shipment selection → current telemetry and history table. |
| `tamperproject/Tamper_user/frontend/live.js` | Authenticates, constrains shipment choices by assignment, and polls `/shipments/{code}/live`. | Credentials/JWT + assigned shipment code → live values, freshness, seal state, and history DOM. |
| `tamperproject/Tamper_user/frontend/common.js` | Shared timeout, escaping, session cleanup, and responsive navigation/accessibility behavior. | DOM/events/fetch requests → safe responsive UI and bounded calls. |
| `tamperproject/Tamper_user/frontend/style.css` | Main user-dashboard styling. | HTML/DOM state → desktop presentation. |
| `tamperproject/Tamper_user/frontend/mobile.css` | User-dashboard responsive overrides. | Viewport and DOM state → mobile presentation. |

### Deployment / Vercel

| Path | Responsibility | Data in → data out |
|---|---|---|
| `tamperproject/Tamper_admin/frontend/vercel.json` | Configures the admin static build/output and response security/cache headers; CSP permits the live API and required UI CDNs. | Vercel build/request context → Tailwind build, static files, and HTTP headers. |
| `tamperproject/Tamper_admin/frontend/package.json` | Defines the admin Tailwind production build and its development dependency. | `npm run build` + source CSS/config → minified `tailwind.css`. |
| `tamperproject/Tamper_admin/frontend/pnpm-lock.yaml` | Locks the frontend build dependency graph. | Package manager resolution → reproducible installed build packages. |
| `tamperproject/Tamper_user/frontend/vercel.json` | Configures static user-site security/cache headers and allows connections to the live API. | Vercel request context → static responses with CSP and security headers. |
| `tamperproject/Tamper_admin/backend/database.py` | Deployment-sensitive database adapter; translates provider PostgreSQL URLs and enables connection health checks. | Vercel/host `DATABASE_URL` → PostgreSQL connection pool (or local SQLite fallback). |
| `tamperproject/Tamper_admin/backend/main.py` | ASGI application object (`app`) expected by an external Python deployment adapter. | Platform ASGI requests/environment → API responses and managed-database access. |

Required production configuration inferred from code/docs includes `DATABASE_URL`, `JWT_SECRET`, and `DEVICE_API_KEY`. The gateway must carry the matching device key locally. Frontend API URLs and cross-site policy are currently hard-coded to the live API hostname.

## Important uncertainties

- **Firmware entry point:** `tamperproject/firmware/tracksure_gateway/tracksure_gateway.ino` is authoritative and was compiled/flashed for the verified Wi-Fi path. `tamperproject/tracksure_final_code.ino` is a retained, non-authoritative historical sketch and must not be used for production flashing.
- **Legacy workspace tree:** the adjacent `safetrack_Admin_SIH_Final/` directory remains outside this repository for historical recovery and must not be mixed into active changes.
- **Backend deployment:** the existing API is running on Vercel and was verified through `/api/events` and shipment live/detail reads. No checked-in backend Vercel manifest or infrastructure-as-code is present, so recreating that deployment still depends on external project configuration.
- **Gateway local configuration:** `gateway.local.json`, the enrolled public key, and runtime outbox are intentionally ignored, so enrollment values and the actual cloud target cannot be verified from committed files.
- **Admin live endpoint difference:** the compact admin live client reads `/shipments/{code}`, while the compact user live client reads `/shipments/{code}/live`; both route shapes exist, but their refresh semantics differ.
- **Verified dashboard behavior:** the Admin shipment inspector renders current telemetry and the 30-record hash ledger. Live polling preserves the ledger count, and opening the modal scrolls the existing ledger rows into view.
