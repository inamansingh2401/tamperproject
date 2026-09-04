# SafeTrack — SIH Demo

SafeTrack is a shipment-condition monitoring prototype built around FastAPI, SQLAlchemy, SQLite for the local demo, ESP32-S3 sensor input/simulation, JWT authentication, and separate Admin/User dashboards.

## Run the complete local demo

From the `Tamper_admin_SIH` root folder:

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

ESP32-S3 simulator → FastAPI → SQLite/SQLAlchemy → Admin + User dashboards.

Each shipment has independent telemetry and its own hash chain, even when multiple shipments share a vehicle.

## Production deployment

For deployment, move the database from SQLite to managed PostgreSQL, store `JWT_SECRET` and device credentials in environment/secret storage, restrict CORS to the deployed domains, and serve the application over HTTPS.

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
