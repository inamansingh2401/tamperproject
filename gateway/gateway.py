"""TrackSure USB gateway: serial -> durable outbox -> existing HTTPS API."""
import argparse
import base64
import hashlib
import json
import logging
import math
import sqlite3
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import serial
from serial.tools import list_ports

LOG = logging.getLogger('tracksure')
ROOT = Path(__file__).resolve().parent
STOP = threading.Event()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('Non-finite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


def decode_record(line, config):
    """Verify exact original bytes when a signed envelope is supplied."""
    if len(line) > 16384:
        raise ValueError('Record too large')
    if line.startswith(b'TRACKSURE '):
        line = line[len(b'TRACKSURE '):]
    envelope = strict_json(line)
    verified = False
    original = line.decode('utf-8').strip()
    if 'record_b64' in envelope:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        key_path = config.get('public_key_file')
        if not key_path:
            raise ValueError('Signed record received but no enrolled public key')
        key_text = (ROOT / key_path).read_text().strip()
        if key_text.startswith('-----BEGIN'):
            key = serialization.load_pem_public_key(key_text.encode())
        else:
            point = bytes.fromhex(''.join(key_text.split()))
            if len(point) == 64:
                point = b'\x04' + point
            key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
            raise ValueError('Public key must use P-256')
        raw = base64.b64decode(envelope['record_b64'], validate=True)
        signature = base64.b64decode(envelope['signature_b64'], validate=True)
        if len(signature) != 64:
            raise ValueError('Signature must be raw 64-byte r||s')
        der = utils.encode_dss_signature(int.from_bytes(signature[:32], 'big'), int.from_bytes(signature[32:], 'big'))
        digest = hashlib.sha256(b'TrackSure:event:v1\0' + raw).digest()
        key.verify(der, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        payload = strict_json(raw)
        verified = True
    else:
        if config.get('require_signature', False):
            raise ValueError('Unsigned record rejected: signature required')
        payload = envelope
    if not isinstance(payload, dict):
        raise ValueError('Record must be an object')
    if payload.get('device_id') != config['device_id'] or payload.get('shipment_code') != config['shipment_code']:
        raise ValueError('Device or shipment not enrolled in this gateway')
    # Current cloud schema needs real finite temperature/humidity. Never invent defaults.
    for name in ('temperature', 'humidity'):
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(name + ' unavailable; waiting for a valid sensor reading')
    if not -100 <= payload['temperature'] <= 150 or not 0 <= payload['humidity'] <= 100:
        raise ValueError('Sensor value outside supported range')
    event_id = payload.get('event_id')
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128:
        raise ValueError('Missing/invalid event_id; flash the gateway firmware')
    return event_id, payload, verified, original


class Outbox:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS outbox (event_id TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL, original TEXT NOT NULL, verified INTEGER NOT NULL, state TEXT NOT NULL DEFAULT \'queued\', attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0, error TEXT, received TEXT NOT NULL, sent TEXT)')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        return db

    def enqueue(self, event_id, payload, verified, original):
        body = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
        digest = hashlib.sha256(body.encode()).hexdigest()
        with self.connect() as db:
            row = db.execute('SELECT digest FROM outbox WHERE event_id=?', (event_id,)).fetchone()
            if row:
                if row['digest'] != digest:
                    raise ValueError('Event identity conflict: payload changed')
                return False
            db.execute('INSERT INTO outbox(event_id,digest,payload,original,verified,received) VALUES(?,?,?,?,?,?)',
                       (event_id, digest, body, original, int(verified), datetime.now(timezone.utc).isoformat()))
        return True

    def pending(self):
        with self.connect() as db:
            return db.execute("SELECT * FROM outbox WHERE state='queued' AND next_attempt<=? ORDER BY rowid LIMIT 1", (time.time(),)).fetchone()

    def mark(self, event_id, state, error=None, delay=0):
        with self.connect() as db:
            db.execute('UPDATE outbox SET state=?,error=?,attempts=attempts+1,next_attempt=?,sent=? WHERE event_id=?',
                       (state, error, time.time()+delay, datetime.now(timezone.utc).isoformat() if state == 'sent' else None, event_id))

    def status(self):
        with self.connect() as db:
            counts = {row['state']: row['n'] for row in db.execute('SELECT state,COUNT(*) n FROM outbox GROUP BY state')}
            row = db.execute('SELECT event_id,payload,verified,state,error,received,sent FROM outbox ORDER BY rowid DESC LIMIT 1').fetchone()
        return {'counts': counts, 'latest': dict(row) if row else None}


def send_one(outbox, config, client):
    row = outbox.pending()
    if not row:
        return False
    try:
        response = client.post(config['cloud_url'].rstrip('/') + '/api/events',
            content=row['payload'], headers={'Content-Type': 'application/json',
            'x-device-key': config['device_key'], 'Idempotency-Key': row['event_id']})
        if 200 <= response.status_code < 300:
            result = response.json()
            if result.get('status') != 'success':
                raise ValueError('Cloud returned an unexpected acknowledgment')
            outbox.mark(row['event_id'], 'sent')
            LOG.info('Cloud stored %s (signature %s)', row['event_id'], 'verified locally' if row['verified'] else 'not configured')
        elif response.status_code in (408, 429) or response.status_code >= 500:
            outbox.mark(row['event_id'], 'queued', 'Cloud HTTP '+str(response.status_code), min(60, 2 ** min(row['attempts']+1, 6)))
        else:
            outbox.mark(row['event_id'], 'blocked', 'Cloud HTTP '+str(response.status_code)+'; check enrollment/API configuration')
            LOG.error('Record %s blocked: HTTP %s', row['event_id'], response.status_code)
    except (httpx.HTTPError, ValueError):
        outbox.mark(row['event_id'], 'queued', 'Connection/acknowledgment failed', min(60, 2 ** min(row['attempts']+1, 6)))
    return True


def upload_loop(outbox, config):
    with httpx.Client(timeout=httpx.Timeout(65, connect=15), verify=True, follow_redirects=False) as client:
        while not STOP.is_set():
            if not send_one(outbox, config, client):
                STOP.wait(1)


def choose_port(requested):
    if requested != 'auto':
        return requested
    candidates = [p for p in list_ports.comports() if p.vid in (0x303A,0x10C4,0x1A86,0x0403)]
    return candidates[0].device if len(candidates) == 1 else None


def serial_loop(outbox, config, port):
    while not STOP.is_set():
        selected = choose_port(port)
        if not selected:
            STOP.wait(3)
            continue
        try:
            with serial.Serial(selected, 115200, timeout=1, write_timeout=2) as connection:
                # ESP32-S3 native USB uses these control lines for reset/boot.
                # PySerial asserts both by default on some Windows drivers, which
                # can leave the board in reset or ROM download mode.
                connection.setDTR(False)
                connection.setRTS(False)
                time.sleep(0.25)
                LOG.info('ESP32 connected on %s', selected)
                while not STOP.is_set():
                    line = connection.read_until(b'\n', 16385).strip()
                    if not line.startswith(b'TRACKSURE '):
                        continue
                    try:
                        event_id, payload, verified, original = decode_record(line, config)
                        inserted = outbox.enqueue(event_id, payload, verified, original)
                        # ACK means laptop disk commit, not cloud receipt.
                        connection.write(('ACK '+event_id+'\n').encode())
                        if inserted:
                            LOG.info('Received %.1f C, %.1f%% RH; %s', payload['temperature'], payload['humidity'], event_id)
                    except Exception as exc:
                        LOG.warning('Record rejected: %s', type(exc).__name__ + ': ' + str(exc)[:160])
        except (serial.SerialException, OSError):
            LOG.warning('USB disconnected/busy; reconnecting. Close Arduino Serial Monitor.')
            STOP.wait(3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT/'gateway.local.json'))
    parser.add_argument('--port', default='auto')
    parser.add_argument('--status-port', type=int, default=8765)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    if not config['cloud_url'].startswith('https://'):
        raise SystemExit('Cloud URL must use HTTPS')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    outbox = Outbox(ROOT/'gateway-outbox.db')
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/','/status'):
                self.send_error(404)
                return
            data = outbox.status()
            data['serial_ports'] = [p.device for p in list_ports.comports()]
            data['signature_required'] = bool(config.get('require_signature'))
            data['cloud_url'] = config['cloud_url']
            body = json.dumps(data, indent=2).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', args.status_port), Handler)
    for target, params in [(upload_loop,(outbox,config)),(serial_loop,(outbox,config,args.port))]:
        threading.Thread(target=target, args=params, daemon=True).start()
    LOG.info('Gateway ready. USB auto-detection enabled; status http://127.0.0.1:%s/status',args.status_port)
    LOG.info('Signature enforcement: %s', bool(config.get('require_signature')))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        STOP.set()
        server.server_close()


if __name__ == '__main__':
    main()
