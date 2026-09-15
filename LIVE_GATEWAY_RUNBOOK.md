# TrackSure live gateway runbook

Backend API:

`https://safetrack-api-live.vercel.app`

Live dashboards:

`https://safetrack-admin-live-mu.vercel.app/live.html`

`https://safetrack-user-live-chi.vercel.app/live.html`

Use these links on desktop, Android, or iOS. Hosting credentials are intentionally not stored in this repository.

## 1. Flash the ESP32-S3

Open and upload:

`firmware/tracksure_gateway/tracksure_gateway.ino`

The sketch reads DHT11, MPU6050 and LDR, signs the event with the ATECC508A, and sends the envelope over 2.4 GHz Wi-Fi to the laptop gateway every second:

`POST http://<configured-laptop-address>:8765/ingest`

It requires a JSON acknowledgment containing the matching event ID before advancing the queued event. USB Serial is used only for logs and firmware flashing.

`{"status":"success","event_id":"<event_id>"}`

For the currently detected FTDI USB-to-UART board (VID 0x0403, PID 0x6001), select **ESP32S3 Dev Module** and set **USB CDC On Boot** to **Disabled**. If you later plug directly into the ESP32-S3 native USB connector instead of its UART connector, enable USB CDC on boot for that native connection.

## Wiring

All modules must share ESP32-S3 GND. Use 3.3 V for the sensors and secure element.

| Component | Module pin | ESP32-S3 connection |
|---|---|---|
| DHT11 | VCC | 3V3 |
| DHT11 | DATA | GPIO 5 |
| DHT11 | GND | GND |
| MPU6050 | VCC/VIN | 3V3 |
| MPU6050 | GND | GND |
| MPU6050 | SDA | GPIO 8 |
| MPU6050 | SCL | GPIO 9 |
| MPU6050 | AD0 | GND, giving address 0x68 |
| LDR divider | ADC midpoint | GPIO 4 |
| ATECC508A | VCC | 3V3 |
| ATECC508A | GND | GND |
| ATECC508A | SDA | GPIO 8, shared I2C bus |
| ATECC508A | SCL | GPIO 9, shared I2C bus |

For the LDR divider used by this firmware, connect a 10 kΩ resistor from 3V3 to GPIO 4 and the LDR from GPIO 4 to GND. This produces a high ADC value in darkness and a low value in light. A bare DHT11 needs a 4.7–10 kΩ pull-up resistor between DATA and 3V3; most three-pin DHT11 modules already include it. I2C breakout boards commonly include SDA/SCL pull-ups, so do not add more unless the bus scan is unreliable.

USB can be used during development for flashing and Serial logs, but deployment-path event delivery must be tested from an independent power source. Do not feed 5 V into any GPIO or I2C pin.

## 2. Run the laptop gateway

From this folder:

```powershell
cd C:\Astra_Tracksure\tamperproject\gateway
python -m pip install -r requirements.txt
python gateway.py
```

Gateway status:

`http://<configured-laptop-address>:8765/status`

The gateway stores each reading locally before acknowledging the ESP32, then posts it to:

`POST https://safetrack-api-live.vercel.app/api/events`

## 3. Secure element

The production gateway requires a valid ATECC508A signature. The public key stays on the laptop and is never committed. To configure verification:

1. Put the public key in a PEM or raw hex file on the laptop.
2. Update `gateway/gateway.local.json`:

```json
{
  "require_signature": true,
  "public_key_file": "public_key.pem"
}
```

3. Update the firmware to send signed envelopes:

```json
{
  "record_b64": "...",
  "signature_b64": "..."
}
```

The gateway verifies signatures over:

`TrackSure:event:v1\0` + raw JSON bytes

## 4. Current fixed demo IDs

Device:

`ESP32-S3-TRACKER-01`

Shipment:

`PRCL-2024-05-21-001`

Change both in `gateway/gateway.local.json` and `firmware/tracksure_gateway/tracksure_gateway.ino` if the cloud shipment changes.

## 5. PostgreSQL deployment settings

Set these secrets in the existing backend deployment environment:

- `DATABASE_URL`: managed PostgreSQL connection URL with SSL enabled
- `JWT_SECRET`: a random value of at least 32 bytes
- `DEVICE_API_KEY`: a separate random value used only by the laptop gateway
- `DEMO_RESET=false`

Put the same `DEVICE_API_KEY` value in the ignored `gateway/gateway.local.json` file as `device_key`. Never commit these values.
