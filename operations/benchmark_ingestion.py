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


def measure(url, output, concurrency=1, revision=True, events=400, batch_size=1, policy=None):
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
    def envelope(number, device, prefix, critical=None):
        payload = dict(event_id=f'{prefix}-{number:07d}',device_id=f'BENCH-DEVICE-{device:05d}',
            shipment_code=f'BENCH-SHIP-{device:05d}',temperature=4.5,humidity=45.,
            ldr_raw=0 if (number%20==0 if critical is None else critical) else 3900,
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
    deadline = time.monotonic()+60
    try:
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError('Local API startup failed before measurement')
            if time.monotonic()>deadline:
                raise RuntimeError('Local API startup exceeded 60 seconds before measurement')
            time.sleep(.02)
    except Exception:
        server.should_exit = True
        thread.join(timeout=5)
        engine.dispose()
        raise
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
        if policy:
            return measure_policy(main,engine,clients[0],envelope,output,policy,base,headers,count,sql)
        with engine.connect() as connection:
            initial = connection.execute(text('SELECT count(*) FROM sensor_events')).scalar()
            initial_bytes = connection.execute(text("SELECT pg_total_relation_size('sensor_events')")).scalar()
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
            final_bytes = connection.execute(text("SELECT pg_total_relation_size('sensor_events')")).scalar()
        accepted = sum(row['accepted'] for row in rows)
        assert final-initial == accepted, 'Acknowledgments differ from durable event count'
        result = dict(concurrency=concurrency,revision_enabled=revision,cache_backend='off',
            initial_events=initial,events_requested=events,events_stored=final-initial,
            batch_size=batch_size,requests=len(rows),elapsed_seconds=elapsed,events_per_second=accepted/elapsed,
            p50_ms=percentile([r['ms'] for r in rows],.5),p95_ms=percentile([r['ms'] for r in rows],.95),
            error_rate=sum(r['status']!=200 for r in rows)/len(rows),sql_calls=sql[0],
            sensor_relation_growth_bytes=final_bytes-initial_bytes,
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


def measure_policy(main,engine,client,envelope,output,policy,base,headers,count,sql):
    rows = []
    with engine.connect() as connection:
        before = connection.execute(text('SELECT count(*) FROM sensor_events')).scalar()
    def post(payload,label,extra_headers=None):
        old_sql = sql[0]
        start = time.perf_counter()
        response = client.post('/api/events',json=payload,headers=extra_headers or {})
        rows.append(dict(kind=label,status=response.status_code,ms=(time.perf_counter()-start)*1000,
                         sql=sql[0]-old_sql,retry_after=response.headers.get('Retry-After')))
        return response
    event.listen(engine,'before_cursor_execute',count)
    try:
        if policy=='retry':
            payload = envelope(4000,0,'lost-ack',critical=False)
            class DropAck(httpx.HTTPTransport):
                def handle_request(self,request):
                    response = super().handle_request(request)
                    if response.status_code==200:
                        response.close()
                        raise httpx.ReadTimeout('Injected lost acknowledgment after HTTP success headers')
                    return response
            with httpx.Client(base_url=base,headers=headers,transport=DropAck(),timeout=60) as broken:
                try:
                    broken.post('/api/events',json=payload)
                except httpx.ReadTimeout:
                    lost_ack = True
                else:
                    raise RuntimeError('Timeout injection did not occur')
            hashes_seen = []
            for _ in range(100):
                response = post(payload,'retry',{'Idempotency-Key':payload['event_id']})
                response.raise_for_status()
                assert response.json()['duplicate']
                hashes_seen.append(response.json()['event_hash'])
            assert len(set(hashes_seen))==1
            extra = dict(lost_ack_injected=lost_ack,duplicate_acknowledgments=100,distinct_retry_hashes=1)
        else:
            from ingest_limits import IngestLimits
            # Deliberately small test policy, not a deployment configuration.
            main.ingest_limits = IngestLimits(device_rate=.01,device_burst=2,
                ip_rate=.01,ip_burst=2,failure_rate=.01,failure_burst=2)
            for n in range(200):
                post(envelope(n,0,'limited',critical=False),'ordinary')
            for n in range(10):
                post(envelope(n,0,'invalid',critical=False),'invalid_auth',{'x-device-key':'invalid-fixture-key'})
            for n in range(10):
                response = post(envelope(n,0,'critical',critical=True),'critical')
                response.raise_for_status()
            extra = dict(test_policy='0.01 events/sec, burst 2 per device/IP and failed-auth IP',
                         critical_accepted=sum(row['status']==200 and row['kind']=='critical' for row in rows))
    finally:
        event.remove(engine,'before_cursor_execute',count)
    with engine.connect() as connection:
        after = connection.execute(text('SELECT count(*) FROM sensor_events')).scalar()
    if policy=='retry':
        assert after-before==1
    result = dict(policy=policy,stored_events=after-before,cache_backend='off',**extra,
                  status_counts={kind:{str(status):sum(r['kind']==kind and r['status']==status for r in rows)
                    for status in sorted({r['status'] for r in rows if r['kind']==kind})}
                    for kind in sorted({r['kind'] for r in rows})},raw_requests=rows,
                  scope='Local real HTTP fault/admission diagnostic; counts are functional measurements, timing has no five-run noise bound')
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='raw_requests'}))
