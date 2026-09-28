# SafeTrack

SafeTrack is a shipment-condition monitoring prototype built around FastAPI, SQLAlchemy, PostgreSQL for deployment, ESP32-S3 sensor input, JWT authentication, and separate Admin/User dashboards.

## Run the complete local demo

From the `Tamper_admin` root folder:

```powershell
python run_all.py
```

The launcher starts:

- FastAPI API: `http://127.0.0.1:8000`
- Admin dashboard: `http://127.0.0.1:5501/login.html`
- User dashboard: `http://127.0.0.1:5500`
- Multi-shipment ESP32-S3 simulator (disable it for real hardware)

Only one backend/database is used. The Admin and User dashboards read the same SafeTrack data.

## Accounts

Provision credentials through private environment configuration. Use `BOOTSTRAP_ADMIN_PASSWORD` and `DEMO_USER_PASSWORD` for isolated development; production values must be unique and never published. The supported roles are `admin` and `user`.

## Demo architecture

ESP32-S3 â†’ Wi-Fi â†’ laptop gateway â†’ HTTPS FastAPI â†’ PostgreSQL/SQLAlchemy â†’ Admin + User dashboards.

Each shipment has independent telemetry and its own hash chain, even when multiple shipments share a vehicle.

## Production deployment

For deployment, set `DATABASE_URL` to a managed PostgreSQL connection string. Set unique `JWT_SECRET`, `DEVICE_API_KEY`, account bootstrap passwords and `CORS_ORIGINS` in the API host environment. The code accepts provider URLs beginning with either `postgres://` or `postgresql://` and uses psycopg 3.

To copy an existing local SQLite database once:

```powershell
$env:DATABASE_URL="<managed PostgreSQL connection string with sslmode=require>"
python backend/migrate_sqlite_to_postgres.py --sqlite backend/safetrack.db
```

## Notes

`frontend/auth.js` protects the Admin Console. Backend admin APIs also require a valid JWT with the `admin` role, so hiding pages in the browser is not the only security layer.

## Real ESP32-S3 mode

The project uses one shared FastAPI backend. The simulator is optional so the same `/api/events` endpoint can receive real ESP32-S3 sensor readings.

To run without the simulator, start the master launcher with:

```powershell
$env:SAFETRACK_SIMULATOR="false"
python run_all.py
```

The FastAPI server listens on the local network (`0.0.0.0:8000`). A real ESP32 should POST sensor data to the laptop's LAN IP, for example `http://192.168.1.105:8000/api/events`, with the `x-device-key` header matching the registered device.

Each shipment remains isolated: telemetry, alerts, and the hash chain are stored against that shipment's database ID.

## Vehicle identity

Vehicle codes and shipment codes are intentionally different. Example: `TRK-MH-001` is a vehicle code, while `PRCL-2024-05-21-001` is a shipment code. The UI displays the vehicle registration number where appropriate.

## User portal

The User portal is intentionally simplified into tabs: Overview, Shipment, Environment, Alerts, and History. It uses a light, restrained visual theme and only shows shipments assigned to the logged-in user.

## Current unified frontend

The deployed frontend is `frontend/`: a single login serves both roles. Run `npm install` and `npm run build` there, then serve the folder. See [deployment guide](../docs/DEPLOYMENT.md).
