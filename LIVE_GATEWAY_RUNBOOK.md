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
