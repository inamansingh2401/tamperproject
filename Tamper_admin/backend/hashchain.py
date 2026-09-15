import hashlib

def calculate_event_hash(shipment_id: int, device_id: str, light_lux: float, temperature: float, humidity: float, accel_g: float, prev_hash: str) -> str:
    payload_str = f"{shipment_id}|{device_id}|{light_lux}|{temperature}|{humidity}|{accel_g}|{prev_hash}"
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
