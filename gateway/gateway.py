"""TrackSure Wi-Fi/LAN gateway: signed device records -> durable outbox -> HTTPS API."""
import argparse
import base64
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

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

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

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
            # Lease atomically: parallel uploaders must never select the same row.
            db.execute('BEGIN IMMEDIATE')
            now = time.time()
            row = db.execute("SELECT rowid AS ordinal,* FROM outbox WHERE state='queued' ORDER BY rowid DESC LIMIT 1").fetchone()
            if row and row['next_attempt'] > now:
                return None
            if row:
                # Preserve exact signed history locally, but never replay stale
                # samples over the current cloud display. This gateway is enrolled
                # to one device/shipment (validated by decode_record).
                db.execute("UPDATE outbox SET state='archived',error='Superseded for live delivery; signed original retained locally' WHERE state='queued' AND rowid<?", (row['ordinal'],))
                db.execute('UPDATE outbox SET next_attempt=? WHERE event_id=?', (now + 120, row['event_id']))
            return row

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
    # Multiple workers let the durable outbox catch up when API/database
    # latency is higher than the ESP sampling interval. Every row is still
    # retained and acknowledged independently, so no telemetry is discarded.
    def worker():
        with httpx.Client(timeout=httpx.Timeout(65, connect=15), verify=True, follow_redirects=False) as client:
            while not STOP.is_set():
                if not send_one(outbox, config, client):
                    STOP.wait(0.25)

    # One in-flight request preserves cloud ordering and the per-shipment chain.
    workers = [threading.Thread(target=worker, name='cloud-live-upload', daemon=True)]
    for thread in workers:
        thread.start()
    while not STOP.is_set():
        STOP.wait(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(ROOT/'gateway.local.json'))
    parser.add_argument('--status-port', type=int, default=None)
    parser.add_argument('--bind', default=None, help='Listener address; defaults to lan_bind in local config')
    parser.add_argument('--outbox', default=str(ROOT/'gateway-outbox.db'))
    parser.add_argument('--local-only', action='store_true', help='Accept and persist device records without cloud upload')
    parser.add_argument('--max-wifi-ingest', type=int, default=None, help='Stop after this many successful Wi-Fi requests')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    bind = args.bind or config.get('lan_bind', '127.0.0.1')
    status_port = args.status_port or int(config.get('lan_port', 8765))
    if not config['cloud_url'].startswith('https://'):
        raise SystemExit('Cloud URL must use HTTPS')
    if args.max_wifi_ingest is not None and args.max_wifi_ingest < 1:
        raise SystemExit('--max-wifi-ingest must be at least 1')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    file_log = RotatingFileHandler(ROOT / 'gateway-runtime.local.log', maxBytes=5_000_000,
                                   backupCount=3, encoding='utf-8')
    file_log.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    LOG.addHandler(file_log)
    outbox = Outbox(Path(args.outbox))
    local_status_clients = {'127.0.0.1', '::1'}
    if bind not in ('0.0.0.0', '::'):
        local_status_clients.add(bind)
    accepted_wifi_requests = 0
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            nonlocal accepted_wifi_requests
            if self.path != '/ingest':
                self.send_error(404)
                return
            self.connection.settimeout(5)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    self.send_error(413)
                    return
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError('Incomplete record')
                secure_config = dict(config, require_signature=True)
                event_id, payload, verified, original = decode_record(raw, secure_config)
                inserted = outbox.enqueue(event_id, payload, verified, original)
                body = json.dumps({'status': 'success', 'event_id': event_id}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                LOG.info('Wi-Fi %s verified record %s from %s',
                         'received' if inserted else 're-acknowledged', event_id, self.client_address[0])
                accepted_wifi_requests += 1
                if args.max_wifi_ingest and accepted_wifi_requests >= args.max_wifi_ingest:
                    threading.Thread(target=server.shutdown, daemon=True).start()
            except Exception as exc:
                LOG.warning('Wi-Fi record rejected: %s', type(exc).__name__)
                self.send_error(400, 'Invalid signed record')

        def do_GET(self):
            if self.client_address[0] not in local_status_clients:
                self.send_error(403)
                return
            if self.path not in ('/','/status'):
                self.send_error(404)
                return
            data = outbox.status()
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
    server = ThreadingHTTPServer((bind, status_port), Handler)
    if not args.local_only:
        threading.Thread(target=upload_loop, args=(outbox, config), daemon=True).start()
    LOG.info('Gateway ready on %s:%s; signed Wi-Fi ingest POST /ingest.', bind, status_port)
    status_host = '127.0.0.1' if bind in ('0.0.0.0', '::') else bind
    LOG.info('Local status: http://%s:%s/status', status_host, status_port)
    LOG.info('Signature enforcement: %s', bool(config.get('require_signature')))
    if args.local_only:
        LOG.info('Local-only mode: cloud upload disabled.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        STOP.set()
        server.server_close()


if __name__ == '__main__':
    main()
