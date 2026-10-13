# SafeTrack

TrackSure is a shipment-security and condition-monitoring platform. It records environmental and motion data at the parcel, cryptographically signs each accepted record, preserves a hash-linked evidence trail, and presents the verified shipment state in separate Admin and User dashboards.

## Live portal

[Open SafeTrack](https://safetrack-portal.vercel.app). One login routes administrators to the operations console and assigned users to their shipment dashboard. Request an account from the project operator; production credentials are not published.

**Service status — 13 October 2026:** login is currently unavailable. The Vercel API returns HTTP 500 during database startup after the Render free PostgreSQL instance expired on 12 October and was suspended. Migration to Supabase PostgreSQL is pending; no production data has been migrated and the backend connection has not been changed. See [database recovery](docs/DEPLOYMENT.md#database-recovery-and-migration-status).

The shared login includes the truck introduction, optional sound replay, and a reduced-motion fallback. The user portal separates Overview, Conditions and Events; Conditions includes the sensor-driven 3D parcel. The admin Vehicles page supports fleet search, filtering and vehicle detail navigation.

## Why it exists

Shipment incidents such as unauthorised opening, abnormal movement, shock, or harmful environmental conditions are difficult to investigate when the sensor trail can be altered or cannot be tied to a device identity. SafeTrack provides timestamped device evidence, signature verification, and a per-shipment hash chain so that the stored history can be independently checked.

## Current implementation

```text
DHT11 + MPU6050 + LDR + ATECC508A
                |
          ESP32-S3 firmware
                |
        2.4 GHz Wi-Fi / HTTP
                |
 Laptop gateway :8765: signature verification + durable SQLite outbox
                |
            HTTPS /api/events
                |
       Vercel FastAPI API + PostgreSQL evidence ledger
                |
       Vercel Admin and User web dashboards
```

The battery-powered firmware emits signed telemetry over Wi-Fi. The laptop gateway accepts it at `POST /ingest`, verifies the enrolled device and ATECC P-256 signature, persists the reading before acknowledging it, and retries HTTPS cloud delivery. The retained backend stores accepted events against their shipment, while the dashboards retrieve current telemetry separately from their historical ledger view. USB Serial remains available only for development logs and firmware flashing; it is not an event transport.

## Sensors and evidence fields

| Hardware | Purpose | Evidence captured |
|---|---|---|
| DHT11 | Shipment environment | Temperature and humidity |
| MPU6050 | Motion, tilt and shock | Accelerometer axes, gyroscope axes, shock flag, pitch and roll |
| LDR + 10 kÎ© divider | Exposure/opening signal | Raw light ADC value and exposure state |
| ATECC508A | Device-backed identity | ECDSA signature over the telemetry envelope |

Each stored event carries an event ID, device ID, shipment code, sequence number, event timestamp, payload, SHA-256 chain reference, and signature-verification result.

## Security model

- **Hardware identity:** the physical ATECC508A signs the device envelope. Its private key is not stored in this repository.
- **Integrity chain:** the backend maintains a hash-linked ledger per shipment, allowing later verification of ordering and modification.
- **Gateway verification:** the local gateway verifies the device signature before it uploads an accepted record.
- **Transport and access control:** gateway-to-API traffic uses HTTPS and dashboards use JWT role checks.
- **Durable delivery:** the gateway stores outgoing readings locally and retries after transient network failures.

## Prototype scope and production roadmap

Future field deployments may add RTC-backed timing, SD-card evidence storage, network discovery and low-power operation. These remain roadmap capabilities.

The current prototype has been exercised while battery-powered through Wi-Fi, the laptop gateway, the existing HTTPS API, PostgreSQL, and the Vercel dashboard. It still depends on a manually started laptop gateway, local enrollment/configuration, a reachable 2.4 GHz network, and a LAN address that may change. It uses an **ATECC508A**, not an ATECC608A, and does not yet provide RTC time, SD-card recovery, deep sleep, or production operations/monitoring.

## Repository layout

- `firmware/tracksure_gateway` â€” ESP32-S3 firmware for the real device.
- `gateway` â€” Wi-Fi/LAN receiver, local signature verifier, durable uploader, and status endpoint.
- `Tamper_admin` â€” FastAPI backend, PostgreSQL model, API routes, and Admin dashboard.
- `Tamper_user` â€” shipment-user dashboard.
- `LIVE_GATEWAY_RUNBOOK.md` â€” flash, wiring, gateway, and production configuration instructions.

## Quick start with real hardware

1. Complete the supported wiring and flash the ESP32-S3 as described in [LIVE_GATEWAY_RUNBOOK.md](LIVE_GATEWAY_RUNBOOK.md).
2. Run the gateway:

   ```powershell
   cd gateway
   python -m pip install -r requirements.txt
   python gateway.py
   ```

3. Open `/status` on the configured gateway LAN address and port 8765. A working setup reports the latest accepted record as `sent` after cloud delivery succeeds.
4. Configure `DATABASE_URL`, `JWT_SECRET`, and `DEVICE_API_KEY` in the production API host. Keep the matching device key only in the ignored local gateway configuration.

For a dashboard-only local demo and its demo accounts, see [Tamper_admin/README.md](Tamper_admin/README.md). For the shipment-user interface, see [Tamper_user/README.md](Tamper_user/README.md).

## Hardware notes and limits

- Connect the ATECC508A and MPU6050 to the shared I2C bus: SDA GPIO 8 and SCL GPIO 9.
- The LDR requires a divider: `3V3 -> 10 kÎ© resistor -> GPIO 4 -> LDR -> GND`. A missing resistor leaves GPIO 4 floating, so its readings are undefined.
- MPU6050 pitch and roll are gravity-derived and stable at rest. A magnetometer is required for absolute yaw; the dashboard therefore holds yaw stable.
- Device timestamps in this bench setup come from the ESP32 uptime and gateway/backend timing. The proposed RTC synchronisation is a future field-device addition.

## Feasibility, impact, and future work

SafeTrack is built from low-cost, widely available embedded components and open protocols. The modular gateway lets a device operate during network interruptions and forward records after connectivity returns. The intended benefit is faster incident response, reduced disputes, and a verifiable chronological trail for asset owners, logistics operators, authorities, emergency responders, and investigators.

Next production steps include a stable gateway discovery/address strategy, battery and charging validation, RTC time synchronisation, SD-card recovery, versioned database migrations, configurable alert thresholds, monitoring, and a magnetometer for absolute heading.

## Research and standards

- [NIST FIPS 180-4 â€” Secure Hash Standard](https://csrc.nist.gov/pubs/fips/180-4/upd1/final) for SHA-256.
- [Espressif ESP32-S3 documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/) for the device platform.
- [Microchip CryptoAuthentication devices](https://www.microchip.com/en-us/products/security-ics/cryptoauthentication) for secure-element integration.
- [NXP UM10204 â€” I2C-bus specification](https://www.nxp.com/docs/en/user-guide/UM10204.pdf) for shared sensor-bus design.

## Security and repository hygiene

The repository excludes local gateway configuration, device keys, database files, private keys, `.env` files, Vercel metadata, and build output. Never commit production credentials or cryptographic key material.

## License

This repository is a project prototype. Add an explicit license before redistributing it outside the team.

## Deployment and validation

See [Deployment guide](docs/DEPLOYMENT.md), [release notes](docs/RELEASE_NOTES.md), and [shared portal architecture](Tamper_admin/frontend/SHARED_PORTAL.md).
