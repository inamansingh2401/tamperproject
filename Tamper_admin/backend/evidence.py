"""Offline-verifiable event evidence. No database, network, or private keys required."""
import base64
import hashlib
import itertools
import json
import math
from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

DOMAIN = b'TrackSure:event:v1\0'
FIELDS = ('event_id', 'shipment_id', 'device_id', 'temperature', 'humidity',
          'light_lux', 'accel_g', 'gyro_dps', 'accel_x', 'accel_y', 'accel_z',
          'gyro_x', 'gyro_y', 'gyro_z', 'shock_g', 'pitch', 'roll',
          'orientation_q', 'mpu_read_ok', 'health_level', 'previous_hash', 'created_at')


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    def reject(_):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


def public_point(value):
    point = bytes.fromhex(''.join(value.split()))
    if len(point) == 64:
        point = b'\x04' + point
    key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    return key, point.hex()


def verify_envelope(envelope, public_key=None):
    if not isinstance(envelope, dict):
        raise ValueError('Invalid signed envelope')
    raw = base64.b64decode(envelope['record_b64'], validate=True)
    signature = base64.b64decode(envelope['signature_b64'], validate=True)
    if len(raw) > 8192 or len(signature) != 64:
        raise ValueError('Invalid signed record size')
    payload = strict_json(raw)
    if not isinstance(payload, dict):
        raise ValueError('Signed record must be an object')
    if public_key:
        key, _ = public_point(public_key)
        der = utils.encode_dss_signature(int.from_bytes(signature[:32], 'big'), int.from_bytes(signature[32:], 'big'))
        key.verify(der, DOMAIN + raw, ec.ECDSA(hashes.SHA256()))
    return payload


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def event_values(event):
    result = {name: getattr(event, name) for name in FIELDS}
    result['created_at'] = event.created_at.isoformat() if event.created_at else None
    return result


def make_evidence(event, source, ingest_digest, context=None):
    return canonical({'version': 2, 'event': event_values(event), 'source': source,
                      'public_key': event.public_key, 'signed_envelope':
                      strict_json(event.signed_envelope) if event.signed_envelope else None,
                      'ingest_digest': ingest_digest, 'context': context or {}})


def normalized_signed_readings(source):
    """Version-2 projection must agree with the signed sensor values."""
    axes = [float(source.get(name) or 0) for name in ('accel_x_g', 'accel_y_g')]
    axes.append(float(source['accel_z_g']) if source.get('accel_z_g') is not None else 1.0)
    gyros = [float(source.get(name) or 0) for name in ('gyro_x_dps', 'gyro_y_dps', 'gyro_z_dps')]
    accel = source.get('accel_g')
    if accel is None:
        accel = source.get('shock_reading_g')
    if accel is None:
        accel = round(math.sqrt(sum(v*v for v in axes)), 3) if any(source.get(n) is not None for n in ('accel_x_g','accel_y_g','accel_z_g')) else 1.0
    gyro = source.get('gyro_dps')
    if gyro is None:
        gyro = round(math.sqrt(sum(v*v for v in gyros)), 2) if any(source.get(n) is not None for n in ('gyro_x_dps','gyro_y_dps','gyro_z_dps')) else 0.0
    raw = source.get('ldr_raw')
    light = (4095.0-float(raw))*800.0/1595.0 if raw is not None else float(source.get('light_lux') or 0)
    exposed = float(raw) < 2500 if raw is not None else light >= 800
    pitch = roll = 0.0  # Existing ORM defaults when no sensor vector is available.
    if all(source.get(n) is not None for n in ('accel_x_g','accel_y_g','accel_z_g')):
        pitch = round(math.degrees(math.atan2(axes[1], math.sqrt(axes[0]**2+axes[2]**2))), 2)
        roll = round(math.degrees(math.atan2(-axes[0], axes[2] or 0.0001)), 2)
    health = 'Compromised' if exposed or source['temperature'] > 15 or source.get('shock_detected') is True or accel >= 3 else 'Degraded' if source['temperature'] > 8 else 'Optimal'
    return {'temperature':source['temperature'],'humidity':source['humidity'],'light_lux':light,
            'accel_g':accel,'gyro_dps':gyro,'accel_x':axes[0],'accel_y':axes[1],'accel_z':axes[2],
            'gyro_x':gyros[0],'gyro_y':gyros[1],'gyro_z':gyros[2],'shock_g':accel,
            'pitch':pitch,'roll':roll,'health_level':health,'mpu_read_ok':source.get('mpu_read_ok')}


def verify_record(record, expected_previous=None, expected_shipment=None):
    """Recompute hashes, check links and verify preserved device signatures."""
    errors = []
    if expected_previous is not None and record['previous_hash'] != expected_previous:
        errors.append('Broken previous-hash link')
    signature = 'unavailable'
    if record.get('evidence_version') == 2 and record.get('evidence_payload'):
        proof_bytes = record['evidence_payload'].encode('utf-8')
        if hashlib.sha256(proof_bytes).hexdigest() != record['record_hash']:
            errors.append('Evidence hash mismatch')
        try:
            proof = strict_json(proof_bytes)
            if proof['event'] != {name: record.get(name) for name in FIELDS}:
                errors.append('Stored readings differ from hashed evidence')
            if proof.get('signed_envelope'):
                signed = verify_envelope(proof['signed_envelope'], proof.get('public_key'))
                if signed != proof.get('source'):
                    errors.append('Signed readings differ from evidence source')
                if signed.get('event_id') != record.get('event_id') or signed.get('device_id') != record.get('device_id'):
                    errors.append('Signed event identity mismatch')
                if expected_shipment and signed.get('shipment_code') != expected_shipment:
                    errors.append('Signed shipment mismatch')
                if signed.get('captured_at_ms') is not None:
                    timestamp = datetime.fromisoformat(record['created_at'])
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    if abs(timestamp.timestamp()*1000-signed['captured_at_ms']) > 1:
                        errors.append('Signed capture timestamp mismatch')
                for field, expected in normalized_signed_readings(signed).items():
                    actual = record.get(field)
                    matches = math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-8) if isinstance(expected, (int,float)) and not isinstance(expected, bool) and isinstance(actual, (int,float)) else expected == actual
                    if not matches:
                        errors.append('Signed reading mismatch: ' + field)
                orientation = signed.get('orientation_q') if signed.get('mpu_read_ok') is not False else None
                if orientation != (strict_json(record['orientation_q']) if record.get('orientation_q') else None):
                    errors.append('Signed orientation mismatch')
                signature = 'verified' if proof.get('public_key') else 'key_not_enrolled'
        except Exception:
            signature = 'invalid'
            errors.append('Invalid signature/evidence')
    else:
        # Historical hashes used Python string formatting; SQLite FLOAT coercion
        # loses the distinction between 1 and 1.0. Check only those exact variants.
        variants = []
        for name in ('light_lux', 'temperature', 'humidity', 'accel_g'):
            value = record.get(name)
            options = [str(value)]
            if isinstance(value, (int, float)) and float(value).is_integer():
                options = list({str(int(value)), str(float(value))})
            variants.append(options)
        valid = any(hashlib.sha256(
            f"{record['shipment_id']}|{record['device_id']}|{'|'.join(values)}|{record['previous_hash']}".encode()
        ).hexdigest() == record['record_hash'] for values in itertools.product(*variants))
        if not valid:
            errors.append('Legacy hash mismatch')
    return {'id': record['id'], 'event_id': record.get('event_id'),
            'integrity': 'invalid' if errors else 'verified', 'signature': signature, 'errors': errors}


def export_record(event):
    return {**event_values(event), 'id': event.id, 'record_hash': event.record_hash,
            'evidence_version': event.evidence_version, 'evidence_payload': event.evidence_payload}


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Independently verify a downloaded SafeTrack evidence JSON file')
    parser.add_argument('file')
    args = parser.parse_args()
    bundle = strict_json(Path(args.file).read_bytes())
    previous = bundle['anchor_previous_hash']
    results = []
    for record in bundle['records']:
        results.append(verify_record(record, previous, bundle.get('shipment_code')))
        previous = record['record_hash']
    print(canonical({'checked': len(results), 'invalid': sum(r['integrity'] == 'invalid' for r in results),
                     'signature_verified': sum(r['signature'] == 'verified' for r in results),
                     'scope': 'Exported records only; enrollment key and prefix anchor require independent trust',
                     'results': results}))
    raise SystemExit(1 if any(r['integrity'] == 'invalid' for r in results) else 0)
