"""Actual loopback HTTP ingestion, software P-256 signatures and local PostgreSQL."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import socket
import sys
from threading import Lock, Thread
import time
import statistics

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from sqlalchemy import event, text
import uvicorn
from seed_benchmark import ROOT, validate_target
from benchmark_api import percentile


def measure(url, output, concurrency=1, revision=True, events=400, batch_size=1):
    validate_target(url)
    os.environ.update(DATABASE_URL=url, SAFETRACK_ENV='production', REPORT_CACHE_BACKEND='off', DEMO_RESET='false')
    for name in ('JWT_SECRET','DEVICE_API_KEY','BOOTSTRAP_ADMIN_PASSWORD','DEMO_USER_PASSWORD'):
        os.environ[name] = secrets.token_urlsafe(36)
    sys.path.insert(0,str(ROOT/'Tamper_admin/backend'))
    import main
    import report_cache
    from database import engine
    from models import Device
    # This switch lives only in the benchmark process. Production has no bypass.
    if not revision:
        report_cache.advance_revision = lambda db: None
    keys = [ec.generate_private_key(ec.SECP256R1()) for _ in range(100)]
    with engine.begin() as connection:
        for i,key in enumerate(keys):
            public = key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint).hex()
            connection.execute(Device.__table__.update().where(Device.device_id==f'BENCH-DEVICE-{i:05d}')
                .values(status='active',api_key=os.environ['DEVICE_API_KEY'],public_key=public))
    captured_ms = int(time.time()*1000)-10000
    def envelope(number, device, prefix):
        payload = dict(event_id=f'{prefix}-{number:07d}',device_id=f'BENCH-DEVICE-{device:05d}',
            shipment_code=f'BENCH-SHIP-{device:05d}',temperature=4.5,humidity=45.,ldr_raw=0 if number%20==0 else 3900,
            captured_at_ms=captured_ms+number,sequence=number,boot_id='synthetic-ingestion')
        raw = json.dumps(payload,separators=(',',':')).encode()
        signature = keys[device].sign(b'TrackSure:event:v1\0'+raw,ec.ECDSA(hashes.SHA256()))
        r,s = utils.decode_dss_signature(signature)
        return {**payload,'signed_envelope':dict(record_b64=base64.b64encode(raw).decode(),
            signature_b64=base64.b64encode(r.to_bytes(32,'big')+s.to_bytes(32,'big')).decode(),
            signature_algorithm='ECDSA_P256_SHA256',key_slot=0)}
    # Forty independent devices in both single and batch comparisons.
    payloads = [envelope(n,n%40,'measured') for n in range(events)]
    if batch_size > 1:
        grouped = []
        for device in range(40):
            group = payloads[device::40]
            grouped.extend(group[start:start+batch_size] for start in range(0,len(group),batch_size))
        requests = grouped
    else:
        requests = payloads
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0))
        port = reservation.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=port,log_level='error',access_log=False))
    thread = Thread(target=server.run,daemon=True)
    thread.start()
    deadline = time.monotonic()+15
    while not server.started:
        if not thread.is_alive() or time.monotonic()>deadline:
            raise RuntimeError('Local API did not start')
        time.sleep(.02)
    sql, revision_sql = [0], [0]
    lock = Lock()
    def count(conn,cursor,statement,parameters,context,executemany):
        with lock:
            sql[0] += 1
            revision_sql[0] += int(statement.startswith('INSERT INTO cache_revisions'))
    base = f'http://127.0.0.1:{port}'
    headers = {'x-device-key':os.environ['DEVICE_API_KEY']}
    clients = [httpx.Client(base_url=base,headers=headers,timeout=60) for _ in range(concurrency)]
    try:
        for n in range(20):
            clients[0].post('/api/events',json=envelope(n,n,'warmup')).raise_for_status()
        with engine.connect() as connection:
            initial = connection.execute(text('SELECT count(*) FROM sensor_events')).scalar()
        chunks = [requests[i::concurrency] for i in range(concurrency)]
        def worker(index):
            rows = []
            for payload in chunks[index]:
                start = time.perf_counter()
                try:
                    response = clients[index].post('/api/events/batch' if batch_size>1 else '/api/events',
                        json={'events':payload} if batch_size>1 else payload)
                    accepted = len(payload) if batch_size>1 and response.status_code==200 else int(batch_size==1 and response.status_code==200)
                    rows.append(dict(ms=(time.perf_counter()-start)*1000,status=response.status_code,accepted=accepted))
                except httpx.HTTPError as error:
                    rows.append(dict(ms=(time.perf_counter()-start)*1000,status=type(error).__name__,accepted=0))
            return rows
        event.listen(engine,'before_cursor_execute',count)
        try:
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                rows = [row for group in pool.map(worker,range(concurrency)) for row in group]
            elapsed = time.perf_counter()-started
        finally:
            event.remove(engine,'before_cursor_execute',count)
        with engine.connect() as connection:
            final = connection.execute(text('SELECT count(*) FROM sensor_events')).scalar()
        accepted = sum(row['accepted'] for row in rows)
        assert final-initial == accepted, 'Acknowledgments differ from durable event count'
        result = dict(concurrency=concurrency,revision_enabled=revision,cache_backend='off',
            initial_events=initial,events_requested=events,events_stored=final-initial,
            batch_size=batch_size,requests=len(rows),elapsed_seconds=elapsed,events_per_second=accepted/elapsed,
            p50_ms=percentile([r['ms'] for r in rows],.5),p95_ms=percentile([r['ms'] for r in rows],.95),
            error_rate=sum(r['status']!=200 for r in rows)/len(rows),sql_calls=sql[0],
            sql_per_request=sql[0]/len(rows),revision_writes=revision_sql[0],raw_requests=rows,
            scope='Real loopback HTTP, one Uvicorn process, PostgreSQL pool 5+5, software signatures verified by API; signing excluded; 100k seed plus 20 warmups')
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='raw_requests'}),flush=True)
    finally:
        for client in clients:
            client.close()
        server.should_exit = True
        thread.join(timeout=15)
        engine.dispose()
