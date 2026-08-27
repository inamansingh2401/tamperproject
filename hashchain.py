import hashlib

GENESIS_HASH = "0" * 64


def compute_event_hash(
    prev_hash: str,
    device_id: int,
    light_value: int,
    motion_detected: bool,
    timestamp: str,
) -> str:
  raw = f"{prev_hash}{device_id}{light_value}{motion_detected}{timestamp}"
  return hashlib.sha256(raw.encode()).hexdigest()