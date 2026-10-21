# TrackSure live gateway runbook

## Rollout note — 14 October 2026

Reboot-safe buffering, complete queued-history delivery, backend enrollment and evidence verification are implemented locally, not yet flashed/deployed. Keep the working installation intact until the local changes are reviewed. Install the updated backend dependency (`cryptography`) and deploy its additive migrations first; existing PostgreSQL tables and RLS/access controls are retained. Then update the gateway/frontend and enroll the current device using its existing ATECC public key and shipment. Flash the canonical firmware with the same ignored Wi-Fi configuration and board/partition settings, **without erasing NVS/LittleFS**, and perform the bounded independent-power acceptance test below. Do not upload/format a filesystem image over retained events.

First installation may format the previously unused LittleFS partition once. Subsequent mount failures never auto-format. A corrupt committed record stops the queue and requires reviewed recovery; this prototype does not include a corrupt-flash repair utility.

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

The production gateway requires a valid ATECC508A signature. Keep the public-key enrollment file local; its public point may also be enrolled in the backend and included in evidence exports. Never upload the private key. To configure verification:

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

These remain the first-use defaults. Ordinary reboot does not change identity or create a new shipment. Once an assignment is saved in NVS, it overrides the compiled shipment default; use the reuse workflow below rather than reflashing random IDs.

## 5. Reboot and device reuse

### Ordinary reboot / power restoration

1. Power the ESP32 independently. It initializes the same sensors/ATECC and joins the configured Wi-Fi without waiting indefinitely for USB.
2. It loads the saved shipment and pause state, increments a persistent boot counter and creates a new random boot ID. Sequence numbers start at zero **per boot**; event IDs remain unique across boots.
3. Previously committed envelopes are replayed FIFO with their original event IDs, bytes and signatures. New signed events are appended to flash. A matching gateway ACK removes only that committed record; the gateway then owns durable cloud delivery.
4. Gateway restart retains its SQLite outbox and resumes FIFO retries. Cloud duplicate IDs are acknowledged without adding another row. IDs reused with changed version-2 readings are rejected.
5. The backend stores events under the payload's shipment and enforces the enrolled binding. Admin and assigned-user dashboards already query that shipment; no alternate telemetry pipeline or manual dashboard mapping is added.

The flash buffer holds at most 512 records (approximately 8.5 minutes at one event/second, possibly less if space runs out). Full/corrupt storage retains old records but cannot record new samples; logs report the gap. An abrupt outage **before** a flash commit cannot preserve that in-flight sample. New firmware signs `captured_at_ms` after SNTP synchronization; before that it records null/unknown plus boot ID and uptime. The backend uses signed capture UTC when available, otherwise original gateway receipt time. SNTP is unauthenticated; an offline reboot still needs synchronization or a future RTC for reliable generation UTC.

### Reusing the same device for another shipment

1. On the development Serial console send `PAUSE` followed by newline. This is a local configuration command, not USB event transport. Sampling pause persists across reboot, while Wi-Fi queued delivery continues.
2. Send `STATUS` and wait for ESP32 `queue=0`. Check the existing gateway `/status` locally: `queued` and `blocked` must both be zero. Investigate blocked rows; never clear/delete them just to reassign. Previously archived historical rows are preserved and do not count as current queue delivery.
3. Stop the gateway after queues drain. In Admin → Shipments → Inspect the target shipment → Device assignment, select the existing device and enter its **existing public P-256 point** (128/130 hex characters). Confirm queues are drained and save. Only administrators can bind; key rotation is rejected by this workflow.
4. Set the same `shipment_code` in the ignored `gateway/gateway.local.json`. Keep device ID, device key, public key and Wi-Fi transport unchanged. Restart the gateway with that configuration.
5. Send `ASSIGN <exact-shipment-code>` followed by newline to the paused ESP32. It refuses reassignment with pending device records. Then send `RESUME`. No firmware reflash is required for shipment reuse.
6. Disconnect USB, independently power the device and verify **one** event appears under the new shipment in both authorized dashboards. Old history stays with the previous shipment; a new event with the old shipment is rejected after enrollment.

Backend `confirm_drained` records an operator assertion, not a remotely proven empty hardware/gateway queue. Changing cloud binding alone does not configure the ESP32/gateway. Keep the three assignments consistent and perform the bounded test; no automatic remote provisioning is claimed.

### Evidence checks

Use **Verify evidence** in the admin inspector or user Events view. Browser WebCrypto recomputes hashes and checks links and available P-256 signatures; the existing live polling stays unchanged. Download the JSON evidence and independently run:

```powershell
python Tamper_admin/backend/evidence.py <shipment-evidence.json>
```

Legacy events without original signatures are reported as unavailable, not hardware-verified. Enroll the existing device public key before requiring server-side signature checks. Trust the enrollment key and any prefix anchor independently; a hash chain without an external anchor cannot prove that a server omitted the end of history. Replayed history with an older signed capture timestamp or original gateway receipt timestamp is persisted without reverting newer live state.

### Required physical acceptance after rollout (not performed in this change)

Deferred on 14 October 2026 at the operator's request: the ESP32 is unavailable. Firmware compilation is not physical acceptance. Do not flash another board or substitute USB events.

Create one signed event during a controlled Wi-Fi interruption; power-cycle the device after the committed-record log/debug indication; restore Wi-Fi; confirm the same ID/signature reaches the gateway/cloud once and appears under the correct shipment. Also restart the gateway with a queued event. USB must be disconnected during event delivery. Do not mutate the production outbox, perform mass archived-history replay, or treat USB debug activity as network success.

### Read-only delivery diagnostics

Check local `/status`: `cloud_upload_enabled`, `cloud_worker_alive`, queue/blocked counts, `oldest_queued_age_seconds`, verified receipt/ACK ages, and `free_disk_bytes`. A responding dashboard GET is not proof of fresh cloud delivery. `python operations/inspect_outbox.py` reads the existing outbox in SQLite read-only/query-only mode and prints metadata, not signed payloads or keys. It never retries, requeues or deletes a record. The current archived/blocked backlog still requires a separately reviewed recovery plan.

## 6. PostgreSQL deployment settings

Set these secrets in the existing backend deployment environment:

- `DATABASE_URL`: managed PostgreSQL connection URL with SSL enabled
- `JWT_SECRET`: a random value of at least 32 bytes
- `DEVICE_API_KEY`: a separate random value used only by the laptop gateway
- `DEMO_RESET=false`

Put the same `DEVICE_API_KEY` value in the ignored `gateway/gateway.local.json` file as `device_key`. Never commit these values.
