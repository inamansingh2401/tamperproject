import json
import random
import time
import urllib.request

API_URL = "http://127.0.0.1:8000/api/events"
SHIPMENT_CODE = "PRCL-2024-05-21-001"
DEVICE_ID = "ESP32-S3-TRACKER-01"

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
      "gyro_dps": round(random.uniform(0.1, 4.5), 1),
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
    with urllib.request.urlopen(req) as res:
      return json.loads(res.read().decode("utf-8"))
  except Exception as e:
    print(f"Transmission error: {e}")
    return None


def main():
  print("=" * 65)
  print(" SafeTrack Hardware Simulator (SHT31 + BH1750 + MPU6050)")
  print(" Streaming real-time multi-sensor telemetry to PostgreSQL ledger...")
  print("=" * 65)

  step = 0
  while True:
    step += 1
    curr_wh = WAREHOUSES[min(step // 5, len(WAREHOUSES) - 1)]

    # Default: Level 1 Optimal (Sealed, cold chain intact)
    lux = 0.0
    temp = round(random.uniform(3.5, 5.2), 1)
    hum = round(random.uniform(42.0, 50.0), 1)
    accel = round(random.uniform(0.95, 1.15), 2)

    # Trigger Level 2 Degraded on Cycle 6
    if step % 8 == 6:
      print("\n⚠️ [EVENT TRIGGERED] Transit Thermal Excursion (Degraded)")
      temp = 11.4
      hum = 68.0
      accel = 2.1

    # Trigger Level 3 Compromised (Lid Opened) on Cycle 12
    if step % 12 == 0:
      print("\n🚨 [EVENT TRIGGERED] Container Breach Detected (BH1750 Exposed!)")
      lux = 850.0
      accel = 3.6

    res = send_telemetry(lux, temp, hum, accel, curr_wh)
    if res:
      print(
          f"[{time.strftime('%H:%M:%S')}] Loc: {curr_wh} | Lux: {lux} | Temp:"
          f" {temp}°C | Accel: {accel}g | Health: {res.get('health_level')} |"
          f" Seal: {res.get('seal_status')}"
      )

    time.sleep(3)


if __name__ == "__main__":
  main()