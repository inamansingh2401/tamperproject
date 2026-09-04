import json
import math
import random
import time
import urllib.request

API_URL = "http://127.0.0.1:8000/api/events"
DEVICE_KEY = "secret_device_key_esp32_2026"

# Realistic Cold-Chain Profiles
SHIPMENT_CONFIGS = [
    {"code": "PRCL-2024-05-21-001", "device": "ESP32-S3-TRACKER-01", "base_temp": 4.1, "base_hum": 49.0, "location": "Rewari Transit Hub, HR", "demo_tamper": False},
    {"code": "PRCL-2024-05-21-007", "device": "ESP32-S3-TRACKER-02", "base_temp": 4.5, "base_hum": 52.0, "location": "Rewari Transit Hub, HR", "demo_tamper": False},
    {"code": "PRCL-2024-05-21-002", "device": "ESP32-S3-TRACKER-03", "base_temp": 5.0, "base_hum": 53.0, "location": "Visakhapatnam Port Hub, AP", "demo_tamper": False},
    {"code": "PRCL-2024-05-21-003", "device": "ESP32-S3-TRACKER-04", "base_temp": 3.8, "base_hum": 47.0, "location": "Vijayawada Transit Yard, AP", "demo_tamper": False},
    # PRCL-004 features periodic dynamic tamper cycles (0 LUX Intact <-> 1000 LUX Compromised) for live demonstration
    {"code": "PRCL-2024-05-21-004", "device": "ESP32-S3-TRACKER-05", "base_temp": 4.8, "base_hum": 55.0, "location": "Panvel Checkpoint, MH", "demo_tamper": True},
    {"code": "PRCL-2024-05-21-005", "device": "ESP32-S3-TRACKER-06", "base_temp": 4.2, "base_hum": 48.0, "location": "Jaipur Highway Hub, RJ", "demo_tamper": False},
    {"code": "PRCL-2024-05-21-006", "device": "ESP32-S3-TRACKER-07", "base_temp": 4.4, "base_hum": 50.0, "location": "Agra Transit Hub, UP", "demo_tamper": False},
    {"code": "PRCL-2024-05-21-008", "device": "ESP32-S3-TRACKER-08", "base_temp": 4.6, "base_hum": 51.0, "location": "Visakhapatnam Port Hub, AP", "demo_tamper": False},
    {"code": "PRCL-2024-05-21-009", "device": "ESP32-S3-TRACKER-09", "base_temp": 3.9, "base_hum": 46.0, "location": "Vijayawada Transit Yard, AP", "demo_tamper": False},
    {"code": "PRCL-2024-05-21-010", "device": "ESP32-S3-TRACKER-10", "base_temp": 4.3, "base_hum": 49.0, "location": "Agra Transit Hub, UP", "demo_tamper": False},
]

# Track live state for smooth natural drift across polling cycles
states = {}
for cfg in SHIPMENT_CONFIGS:
    states[cfg["code"]] = {
        "temp": cfg["base_temp"],
        "hum": cfg["base_hum"],
        "cycle": 0
    }

print(f"Starting calibrated multi-shipment ESP32-S3 simulator ({len(SHIPMENT_CONFIGS)} shipments)...")
print("Target Ranges: Cold-chain Temp 2.0°C–8.0°C | Humidity 45%–65% | Sealed Light 0 LUX (Tamper 1000 LUX) | Accel ~1.00g\n")

while True:
    for cfg in SHIPMENT_CONFIGS:
        code = cfg["code"]
        st = states[code]
        st["cycle"] += 1

        try:
            # 1. Natural temperature drift (+-0.15C) within strict 2.0C - 7.5C
            temp_delta = round(random.uniform(-0.15, 0.15), 2)
            st["temp"] = round(max(2.5, min(7.2, st["temp"] + temp_delta)), 1)

            # 2. Natural humidity drift (+-0.3%) within 45% - 62%
            hum_delta = round(random.uniform(-0.3, 0.3), 2)
            st["hum"] = round(max(45.0, min(62.0, st["hum"] + hum_delta)), 1)

            # 3. Light & Seal Status logic:
            # Standard shipments remain 0.0 LUX (Container Sealed / Intact).
            # PRCL-004 cycles between Intact (0 LUX) and Tampered (1000 LUX) every 20 cycles for dynamic demonstration.
            if cfg["demo_tamper"]:
                phase = st["cycle"] % 40
                if 20 <= phase < 35:
                    light = 1000.0  # Container open / breached
                    temp_val = round(st["temp"] + 2.5, 1)  # Warm-up due to lid open
                else:
                    light = 0.0     # Container resealed / intact
                    temp_val = st["temp"]
            else:
                light = 0.0
                temp_val = st["temp"]

            # 4. Realistic 3-Axis MPU6050 readings:
            # Stationary cargo: Z-axis = 0.98g - 1.02g (gravity), X/Y minor vibration (~0.01 - 0.04g)
            # Occasional transit bump (4% chance)
            is_bump = random.random() < 0.04
            if is_bump:
                ax = round(random.uniform(-0.25, 0.25), 3)
                ay = round(random.uniform(-0.25, 0.25), 3)
                az = round(random.uniform(1.10, 1.35), 3)
                gx = round(random.uniform(1.0, 3.5), 2)
                gy = round(random.uniform(1.0, 3.5), 2)
                gz = round(random.uniform(0.5, 2.0), 2)
            else:
                ax = round(random.uniform(-0.03, 0.03), 3)
                ay = round(random.uniform(-0.03, 0.03), 3)
                az = round(random.uniform(0.97, 1.03), 3)
                gx = round(random.uniform(0.05, 0.40), 2)
                gy = round(random.uniform(0.05, 0.40), 2)
                gz = round(random.uniform(0.02, 0.25), 2)

            accel_mag = round(math.sqrt(ax**2 + ay**2 + az**2), 2)
            gyro_mag = round(math.sqrt(gx**2 + gy**2 + gz**2), 2)

            payload = {
                "device_id": cfg["device"],
                "shipment_code": code,
                "light_lux": light,
                "temperature": temp_val,
                "humidity": st["hum"],
                "accel_g": accel_mag,
                "accel_x_g": ax,
                "accel_y_g": ay,
                "accel_z_g": az,
                "gyro_dps": gyro_mag,
                "gyro_x_dps": gx,
                "gyro_y_dps": gy,
                "gyro_z_dps": gz,
                "warehouse_location": cfg["location"],
            }

            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-device-key": DEVICE_KEY},
            )

            with urllib.request.urlopen(req, timeout=3) as response:
                result = json.loads(response.read().decode("utf-8"))

            status_str = "BREACH" if light >= 800 else "INTACT"
            print(f"[SIM] {code} | T={temp_val}°C H={st['hum']}% L={light:.0f}Lux [{status_str}] A={accel_mag}g | {result.get('health_level')}")

        except Exception as exc:
            print(f"[SIM WAITING] {code}: {exc}")

    time.sleep(1)
