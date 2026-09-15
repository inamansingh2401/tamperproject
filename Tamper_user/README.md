# SafeTrack user dashboard

This application is the shipment-user view of SafeTrack. It shows only the shipments assigned to the authenticated user and presents the latest verified telemetry, alert history, environmental conditions, and evidence-ledger history.

## What the user sees

- Shipment overview and current status.
- Latest temperature, humidity, light, motion, and shock data.
- Parcel pitch and roll derived from MPU6050 accelerometer data.
- Alerts and the recent cryptographic evidence ledger.

The dashboard polls the backend's live shipment endpoint for the newest verified record, then uses the historical endpoint for the broader ledger. It never connects directly to the ESP32 or database.

## Local development

Run the shared API and both dashboards from the Admin application root:

```powershell
cd ..\Tamper_admin
python run_all.py
```

The User dashboard is served at `http://127.0.0.1:5500`. The shared API runs at `http://127.0.0.1:8000`.

## Data boundaries

Authentication is handled by the shared backend. A user token is restricted to its assigned shipments; the browser navigation is not the security boundary.

## Orientation note

Pitch and roll follow gravity and therefore reflect a stationary parcel's tilt. The hardware has no magnetometer, so absolute yaw is not reported. This prevents visually misleading yaw drift while retaining reliable tilt and shock monitoring.
