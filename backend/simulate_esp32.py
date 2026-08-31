import json
import random
import time
import urllib.request

API_URL = "http://127.0.0.1:8000/api/events"
SHIPMENT_CODE = "PRCL-2024-05-21-001"
DEVICE_ID = "ESP32-S3-TRACKER-01"

# SIH demo mode:
# Keep False so the seal stays INTACT during normal simulation.
# Change to True only when you want to demonstrate a real tamper event.
SIMULATE_TAMPER = False
TAMPER_EVERY_N_CYCLES = 20

WAREHOUSES = [
    "Mumbai Central Dispatch Hub",
    "Surat Transit Node",
    "Vadodara Logistics Hub",
    "Kota Distribution Facility",
    "Rewari Sorting Terminal",
    "Delhi Destination Facility",
]


def send_telemetry(lux, temp, hum, accel, warehouse):
    payload = {
        "device_id": DEVICE_ID,
        "shipment_code": SHIPMENT_CODE,
        "light_lux": lux,
        "temperature": temp,
        "humidity": hum,
        "accel_g": accel,
        "gyro_dps": round(random.uniform(0.1, 2.0), 1),
        "warehouse_location": warehouse,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Device-Key": "secret_device_key_esp32_2026",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"Transmission error: {e}")
        return None


def main():
    print("=" * 65)
    print(" SafeTrack ESP32-S3 Sensor Simulator")
    print(" LDR + Temperature + Humidity + Motion telemetry")
    print(" Seal tamper threshold: 800 LUX")
    print(f" Tamper simulation: {'ON' if SIMULATE_TAMPER else 'OFF'}")
    print("=" * 65)

    step = 0

    while True:
        step += 1
        curr_wh = WAREHOUSES[min(step // 5, len(WAREHOUSES) - 1)]

        # Normal sealed-container readings.
        # A closed parcel should stay near darkness around the sensor.
        lux = round(random.uniform(0.0, 3.0), 1)
        temp = round(random.uniform(3.5, 5.2), 1)
        hum = round(random.uniform(42.0, 50.0), 1)
        accel = round(random.uniform(0.95, 1.15), 2)

        # Optional controlled breach demonstration.
        # This deliberately crosses the 800 LUX threshold.
        if SIMULATE_TAMPER and step % TAMPER_EVERY_N_CYCLES == 0:
            print("\n [EVENT TRIGGERED] Container opened - LDR exposed")
            lux = 1000.0

        res = send_telemetry(lux, temp, hum, accel, curr_wh)

        if res:
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"Loc: {curr_wh} | Lux: {lux} | Temp: {temp}°C | "
                f"Accel: {accel}g | Health: {res.get('health_level')} | "
                f"Seal: {res.get('seal_status')}"
            )

        time.sleep(3)


if __name__ == "__main__":
    main()
