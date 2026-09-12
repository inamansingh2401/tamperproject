# TrackSure live gateway runbook

Backend API:

`https://safetrack-admin-c243.onrender.com`

Live dashboards:

`https://safetrack-admin-live-baibhavkumar018-9376.vercel.app/live.html`

`https://safetrack-user-live-baibhavkumar018-9376.vercel.app/live.html`

## 1. Flash the ESP32-S3

Open and upload:

`firmware/tracksure_gateway/tracksure_gateway.ino`

The sketch reads DHT11, MPU6050 and LDR, then writes one serial line every 5 seconds:

`TRACKSURE { ...json... }`

It waits for the laptop gateway to reply:

`ACK <event_id>`

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
| ATECC608A | VCC | 3V3 |
| ATECC608A | GND | GND |
| ATECC608A | SDA | GPIO 8, shared I2C bus |
| ATECC608A | SCL | GPIO 9, shared I2C bus |

For the LDR divider used by this firmware, connect a 10 kΩ resistor from 3V3 to GPIO 4 and the LDR from GPIO 4 to GND. This produces a high ADC value in darkness and a low value in light. A bare DHT11 needs a 4.7–10 kΩ pull-up resistor between DATA and 3V3; most three-pin DHT11 modules already include it. I2C breakout boards commonly include SDA/SCL pull-ups, so do not add more unless the bus scan is unreliable.

USB data and power use the ESP32-S3 USB connector. Do not feed 5 V into any GPIO or I2C pin.

## 2. Run the laptop gateway

From this folder:

```powershell
cd C:\Astra_Tracksure\tamperproject\gateway
python -m pip install -r requirements.txt
python gateway.py
```

Gateway status:

`http://127.0.0.1:8765/status`

The gateway stores each reading locally before acknowledging the ESP32, then posts it to:

`POST https://safetrack-admin-c243.onrender.com/api/events`

## 3. Secure element

Unsigned readings are accepted right now so live demo can work. To enforce ATECC608A signatures:

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

Set these secrets on the Render backend service:

- `DATABASE_URL`: managed PostgreSQL connection URL with SSL enabled
- `JWT_SECRET`: a random value of at least 32 bytes
- `DEVICE_API_KEY`: a separate random value used only by the laptop gateway
- `DEMO_RESET=false`

Put the same `DEVICE_API_KEY` value in the ignored `gateway/gateway.local.json` file as `device_key`. Never commit these values.
