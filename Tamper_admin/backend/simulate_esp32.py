"""SafeTrack telemetry simulator with smooth room-condition sensor behavior."""
import json
import math
import os
from pathlib import Path
import random
import time
import urllib.error
import urllib.request
import uuid

API_URL = os.getenv("SAFETRACK_API_URL", "https://safetrack-api-live.vercel.app/api/events")
DEVICE_KEY = os.getenv("DEVICE_API_KEY", "").strip()
if not DEVICE_KEY:
    private_config = Path(__file__).resolve().parents[2] / "gateway" / "gateway.local.json"
    if private_config.is_file():
        DEVICE_KEY = json.loads(private_config.read_text(encoding="utf-8"))["device_key"]
if not DEVICE_KEY:
    raise SystemExit("Set DEVICE_API_KEY or configure the ignored gateway/gateway.local.json file.")
TARGET_TEMP_C = float(os.getenv("SIMULATOR_TEMPERATURE_C", "31.0"))
SEND_INTERVAL_S = max(2.0, float(os.getenv("SIMULATOR_INTERVAL_SECONDS", "5")))
SIMULATE_ALL = os.getenv("SIMULATE_ALL_SHIPMENTS", "false").lower() == "true"
DEMO_TAMPER = os.getenv("SIMULATOR_DEMO_TAMPER", "false").lower() == "true"

SHIPMENT_CONFIGS = [
    {"code": "PRCL-2024-05-21-001", "device": "ESP32-S3-TRACKER-01", "temp_offset": 0.0, "humidity": 56.0, "location": "Rewari Transit Hub, HR"},
    {"code": "PRCL-2024-05-21-007", "device": "ESP32-S3-TRACKER-02", "temp_offset": -0.3, "humidity": 58.0, "location": "Rewari Transit Hub, HR"},
    {"code": "PRCL-2024-05-21-002", "device": "ESP32-S3-TRACKER-03", "temp_offset": 0.4, "humidity": 62.0, "location": "Visakhapatnam Port Hub, AP"},
    {"code": "PRCL-2024-05-21-003", "device": "ESP32-S3-TRACKER-04", "temp_offset": 0.1, "humidity": 59.0, "location": "Vijayawada Transit Yard, AP"},
    {"code": "PRCL-2024-05-21-004", "device": "ESP32-S3-TRACKER-05", "temp_offset": 0.6, "humidity": 61.0, "location": "Panvel Checkpoint, MH"},
    {"code": "PRCL-2024-05-21-005", "device": "ESP32-S3-TRACKER-06", "temp_offset": -0.2, "humidity": 53.0, "location": "Jaipur Highway Hub, RJ"},
    {"code": "PRCL-2024-05-21-006", "device": "ESP32-S3-TRACKER-07", "temp_offset": 0.2, "humidity": 55.0, "location": "Agra Transit Hub, UP"},
    {"code": "PRCL-2024-05-21-008", "device": "ESP32-S3-TRACKER-08", "temp_offset": 0.3, "humidity": 63.0, "location": "Visakhapatnam Port Hub, AP"},
    {"code": "PRCL-2024-05-21-009", "device": "ESP32-S3-TRACKER-09", "temp_offset": 0.0, "humidity": 60.0, "location": "Vijayawada Transit Yard, AP"},
    {"code": "PRCL-2024-05-21-010", "device": "ESP32-S3-TRACKER-10", "temp_offset": -0.1, "humidity": 54.0, "location": "Agra Transit Hub, UP"},
]
if not SIMULATE_ALL:
    SHIPMENT_CONFIGS = SHIPMENT_CONFIGS[:1]

states = {cfg["code"]: {"temp": TARGET_TEMP_C + cfg["temp_offset"], "humidity": cfg["humidity"], "cycle": 0} for cfg in SHIPMENT_CONFIGS}


def bounded_mean_reversion(value, target, noise, minimum, maximum):
    next_value = value + 0.12 * (target - value) + random.gauss(0.0, noise)
    return max(minimum, min(maximum, next_value))


def make_payload(cfg, state):
    state["cycle"] += 1
    target = TARGET_TEMP_C + cfg["temp_offset"] + 0.25 * math.sin(state["cycle"] / 40.0)
    state["temp"] = bounded_mean_reversion(state["temp"], target, 0.035, target - 0.8, target + 0.8)
    humidity_target = cfg["humidity"] - (state["temp"] - target) * 1.5
    state["humidity"] = bounded_mean_reversion(state["humidity"], humidity_target, 0.10, 35.0, 80.0)
    tamper_open = DEMO_TAMPER and 24 <= state["cycle"] % 60 < 30
    ldr_raw = random.randint(90, 220) if tamper_open else random.randint(3800, 4095)
    shock = random.random() < 0.01
    if shock:
        ax, ay = random.uniform(-2.8, 2.8), random.uniform(-2.8, 2.8)
        az = random.uniform(0.6, 1.5)
        gx, gy, gz = (random.uniform(-90, 90) for _ in range(3))
    else:
        ax, ay = random.gauss(0, 0.012), random.gauss(0, 0.012)
        az = random.gauss(1.0, 0.012)
        gx, gy, gz = (random.gauss(0, 0.25) for _ in range(3))
    shock_g = math.sqrt(ax * ax + ay * ay)
    return {
        "event_id": f"SIM-{cfg['device']}-{uuid.uuid4().hex}",
        "firmware_version": "tracksure-simulator-2", "signature_status": "simulated",
        "device_id": cfg["device"], "shipment_code": cfg["code"],
        "temperature": round(state["temp"], 1), "humidity": round(state["humidity"], 1),
        "ldr_raw": ldr_raw, "light_lux": 1000.0 if tamper_open else 0.0,
        "accel_g": round(math.sqrt(ax * ax + ay * ay + az * az), 3),
        "accel_x_g": round(ax, 3), "accel_y_g": round(ay, 3), "accel_z_g": round(az, 3),
        "gyro_dps": round(math.sqrt(gx * gx + gy * gy + gz * gz), 2),
        "gyro_x_dps": round(gx, 2), "gyro_y_dps": round(gy, 2), "gyro_z_dps": round(gz, 2),
        "shock_reading_g": round(shock_g, 3), "shock_detected": shock_g >= 1.2,
        "warehouse_location": cfg["location"],
    }


def send(payload):
    request = urllib.request.Request(API_URL, data=json.dumps(payload, allow_nan=False).encode("utf-8"), headers={
        "Content-Type": "application/json", "x-device-key": DEVICE_KEY,
        "Idempotency-Key": payload["event_id"], "User-Agent": "TrackSure-Simulator/2",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


print(f"TrackSure simulator -> {API_URL}")
print(f"Shipments: {len(SHIPMENT_CONFIGS)} | ambient target: {TARGET_TEMP_C:.1f} C | interval: {SEND_INTERVAL_S:.0f} s")
while True:
    started = time.monotonic()
    for config in SHIPMENT_CONFIGS:
        payload = make_payload(config, states[config["code"]])
        try:
            result = send(payload)
            seal = "OPEN" if payload["ldr_raw"] < 2500 else "SEALED"
            print(f"[SIM] {config['code']} T={payload['temperature']:.1f} C RH={payload['humidity']:.1f}% LDR={payload['ldr_raw']} {seal} shock={payload['shock_reading_g']:.3f}g -> {result.get('status')}")
        except urllib.error.HTTPError as exc:
            print(f"[SIM HTTP {exc.code}] {config['code']}: {exc.read().decode('utf-8', 'replace')[:200]}")
        except Exception as exc:
            print(f"[SIM WAITING] {config['code']}: {type(exc).__name__}: {exc}")
    time.sleep(max(0.1, SEND_INTERVAL_S - (time.monotonic() - started)))
