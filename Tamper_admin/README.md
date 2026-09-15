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

## Demo accounts

### Admin
- Username: `admin`
- Password: `admin123`

### Users
- `Rahul Sharma` / `1234` — shipments 001, 007
- `Priya Sharma` / `1234` — shipments 002, 008
- `Arjun Reddy` / `1234` — shipments 003, 009
- `Neha Kapoor` / `1234` — shipments 004, 010

The prototype intentionally has only two application roles: `admin` and `user`.

## Demo architecture

ESP32-S3 → Wi-Fi → laptop gateway → HTTPS FastAPI → PostgreSQL/SQLAlchemy → Admin + User dashboards.

Each shipment has independent telemetry and its own hash chain, even when multiple shipments share a vehicle.

## Production deployment

For deployment, set `DATABASE_URL` to a managed PostgreSQL connection string. Also set unique `JWT_SECRET` and `DEVICE_API_KEY` values in Render's environment settings. The code accepts provider URLs beginning with either `postgres://` or `postgresql://` and uses psycopg 3.

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
