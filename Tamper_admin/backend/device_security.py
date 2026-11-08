"""Device-locked, transactional replay ledger. Exact stored retries precede this check."""
import hashlib
import hmac
import os
import time
from fastapi import HTTPException
from sqlalchemy import func
from models import DeviceReplayNonce


def key_matches(device, provided):
    if not isinstance(provided, str) or not 1 <= len(provided) <= 256:
        return False
    if device.key_hash:
        return hmac.compare_digest(hashlib.sha256(provided.strip().encode()).hexdigest(), device.key_hash)
    return hmac.compare_digest(provided.strip().encode(), device.api_key.strip().encode())


def check_replay(db, device, data):
    if device.replay_policy != 'counter_v1':
        return  # Explicit legacy compatibility, not a replay-protection claim.
    if data.device_id != device.device_id:
        raise HTTPException(403, 'Strict device identity must match enrollment exactly')
    if not device.public_key or not data.signed_envelope or not data.event_id or any(
        getattr(data, name, None) is None for name in ('key_version','boot_counter','sequence','captured_at_ms')
    ):
        raise HTTPException(422, 'Strict device requires signed epoch, boot counter, sequence and capture timestamp')
    if data.key_version != device.key_version:
        raise HTTPException(409, 'Device key epoch mismatch')
    age = time.time() - data.captured_at_ms / 1000
    if age < -300 or age > int(os.getenv('REPLAY_MAX_AGE_SECONDS', '604800')):
        raise HTTPException(409, 'Capture outside replay acceptance window')
    identity = (device.device_id,device.key_version,data.boot_counter,data.sequence)
    if db.get(DeviceReplayNonce, identity):
        raise HTTPException(409, 'Counter already used by a different event')
    if data.boot_counter < device.replay_boot - 8:
        raise HTTPException(409, 'Boot counter outside reorder window')
    maximum = db.query(func.max(DeviceReplayNonce.sequence)).filter_by(
        device_id=device.device_id,key_version=device.key_version,boot_counter=data.boot_counter).scalar()
    if maximum is not None and data.sequence < maximum - 511:
        raise HTTPException(409, 'Sequence outside reorder window')
    device.replay_boot = max(device.replay_boot, data.boot_counter)
    db.add(DeviceReplayNonce(device_id=device.device_id,key_version=device.key_version,
        boot_counter=data.boot_counter,sequence=data.sequence,event_id=data.event_id))
