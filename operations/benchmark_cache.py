"""Local report-cache benchmark with an explicit logical polling schedule."""
import contextlib
import io
import json
import os
from pathlib import Path
import secrets
import statistics
import sys
import time
from sqlalchemy import event
from seed_benchmark import ROOT, validate_target
from benchmark_api import percentile


def measure(url, output, mode='off', high_churn=False):
    validate_target(url)
    os.environ.update(DATABASE_URL=url, SAFETRACK_ENV='production', DEMO_RESET='false', REPORT_CACHE_BACKEND='off')
    for key in ('JWT_SECRET','DEVICE_API_KEY','BOOTSTRAP_ADMIN_PASSWORD','DEMO_USER_PASSWORD'):
        os.environ[key] = secrets.token_urlsafe(36)
    sys.path.insert(0,str(ROOT/'Tamper_admin/backend'))
    import main
    from database import engine
    from fastapi.testclient import TestClient
    from report_cache import ReportCache, MemoryTTLCache
    logical_time = [0.]
    main.report_cache = ReportCache(MemoryTTLCache(clock=lambda:logical_time[0]) if mode=='memory' else None)
    statements, rows = [], []
    def track(conn,cursor,sql,parameters,context,executemany):
        statements.append(sql)
    def request(client, method, path, headers, **kwargs):
        start_calls = len(statements)
        start = time.perf_counter()
        response = client.request(method,path,headers=headers,**kwargs)
        elapsed = (time.perf_counter()-start)*1000
        response.raise_for_status()
        return response.json(),elapsed,len(statements)-start_calls
    try:
        with TestClient(main.app) as client:
            login = client.post('/api/auth/login',json={'username':'admin','password':os.environ['BOOTSTRAP_ADMIN_PASSWORD']})
            login.raise_for_status()
            headers = {'Authorization':'Bearer '+login.json()['access_token']}
            device_headers = {'x-device-key':os.environ['DEVICE_API_KEY']}
            # Warm the application and database without priming the cache.
            original = main.report_cache
            main.report_cache = ReportCache()
            for _ in range(3):
                client.get('/api/reports/summary',headers=headers).raise_for_status()
            main.report_cache = original
            last_event_count = 100000
            event.listen(engine,'before_cursor_execute',track)
            try:
                for tick in range(60):
                    logical_time[0] = float(tick)
                    for admin in range(2):
                        if admin == 0 or high_churn:
                            with contextlib.redirect_stdout(io.StringIO()):
                                _,elapsed,calls = request(client,'POST','/api/events',device_headers,json={
                                    'event_id':f'cache-mix-{tick}-{admin}', 'device_id':'ESP32-S3-TRACKER-01',
                                    'shipment_code':'PRCL-2024-05-21-001','temperature':4.5,'humidity':45,
                                    'ldr_raw':0 if tick%10==0 else 3900})
                            rows.append(dict(kind='ingest',ms=elapsed,sql=calls))
                            last_event_count += 1
                        hits = main.report_cache.metrics()['hits']
                        data,elapsed,calls = request(client,'GET','/api/reports/summary',headers)
                        assert data['total_events'] == last_event_count, 'Stale report after ingestion'
                        outcome = 'off' if mode=='off' else 'hit' if main.report_cache.metrics()['hits']>hits else 'miss'
                        rows.append(dict(kind='report',outcome=outcome,ms=elapsed,sql=calls))
                    for kind,path in [('live','/api/shipments/PRCL-2024-05-21-001/live'),
                                      *([('alerts','/api/alerts')] if tick%2==0 else []),
                                      *([('shipments','/api/shipments')] if tick%5==0 else [])]:
                        _,elapsed,calls = request(client,'GET',path,headers)
                        rows.append(dict(kind=kind,ms=elapsed,sql=calls))
                revision_writes = sum('INSERT INTO cache_revisions' in sql for sql in statements)
            finally:
                event.remove(engine,'before_cursor_execute',track)
            metrics = client.get('/api/admin/cache-metrics',headers=headers).json()
        summaries = {}
        for kind in sorted({row['kind'] for row in rows}):
            selected = [r for r in rows if r['kind']==kind]
            summaries[kind] = dict(requests=len(selected),p50_ms=percentile([r['ms'] for r in selected],.5),
                p95_ms=percentile([r['ms'] for r in selected],.95),sql_calls=sum(r['sql'] for r in selected),
                mean_sql=statistics.mean(r['sql'] for r in selected))
        for outcome in ('off','hit','miss'):
            selected = [r for r in rows if r.get('outcome')==outcome]
            if selected:
                summaries['report_'+outcome] = dict(requests=len(selected),
                    p50_ms=percentile([r['ms'] for r in selected],.5),
                    p95_ms=percentile([r['ms'] for r in selected],.95),
                    mean_sql=statistics.mean(r['sql'] for r in selected))
        result = dict(mode=mode, high_churn=high_churn, ttl_seconds=5,
            schedule='60 logical one-second ticks, two report reads/tick, one live read/tick, alerts every two ticks, shipment list every five ticks',
            ingest_schedule='One event before every report' if high_churn else 'One event before the first report each tick',
            time_scope='Logical schedule executed without wall-clock sleeps; latency is actual local elapsed time, not a throughput/load claim',
            cache_metrics=metrics,revision_writes=revision_writes,summary=summaries,
            total_sql=sum(r['sql'] for r in rows),raw_requests=rows)
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({key:value for key,value in result.items() if key!='raw_requests'},indent=2))
    finally:
        engine.dispose()
