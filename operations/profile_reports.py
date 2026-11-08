"""Attribute report request time to SQL and observed Python GC pauses."""
import gc
import json
import os
from pathlib import Path
import secrets
import sys
import time
from seed_benchmark import ROOT, validate_target
from benchmark_api import percentile


def profile(url, output, samples=30):
    validate_target(url)
    os.environ.update(DATABASE_URL=url, SAFETRACK_ENV='production', DEMO_RESET='false')
    for name in ('JWT_SECRET','DEVICE_API_KEY','BOOTSTRAP_ADMIN_PASSWORD','DEMO_USER_PASSWORD'):
        os.environ[name] = secrets.token_urlsafe(36)
    sys.path.insert(0, str(ROOT/'Tamper_admin/backend'))
    from main import app
    from database import engine
    from fastapi.testclient import TestClient
    from sqlalchemy import event
    rows, sql, pauses = [], [], []
    gc_start = {}
    def before(conn, cursor, statement, parameters, context, executemany):
        context.profile_start = time.perf_counter()
    def after(conn, cursor, statement, parameters, context, executemany):
        sql.append((time.perf_counter()-context.profile_start)*1000)
    def collection(phase, info):
        generation = info['generation']
        if phase == 'start':
            gc_start[generation] = time.perf_counter()
        elif generation in gc_start:
            pauses.append((time.perf_counter()-gc_start.pop(generation))*1000)
    try:
        with TestClient(app) as client:
            login = client.post('/api/auth/login',json={'username':'admin','password':os.environ['BOOTSTRAP_ADMIN_PASSWORD']})
            login.raise_for_status()
            headers = {'Authorization':'Bearer '+login.json()['access_token']}
            for _ in range(3):
                client.get('/api/reports/summary',headers=headers).raise_for_status()
            event.listen(engine,'before_cursor_execute',before)
            event.listen(engine,'after_cursor_execute',after)
            gc.callbacks.append(collection)
            try:
                for _ in range(samples):
                    sql.clear()
                    pauses.clear()
                    start = time.perf_counter()
                    client.get('/api/reports/summary',headers=headers).raise_for_status()
                    total = (time.perf_counter()-start)*1000
                    rows.append(dict(total_ms=total, sql_ms=sum(sql), sql_calls=len(sql),
                                     gc_ms=sum(pauses), gc_collections=len(pauses)))
            finally:
                gc.callbacks.remove(collection)
                event.remove(engine,'before_cursor_execute',before)
                event.remove(engine,'after_cursor_execute',after)
        result = dict(samples=rows, p50_ms=percentile([r['total_ms'] for r in rows],.5),
            p95_ms=percentile([r['total_ms'] for r in rows],.95),
            scope='Serial local requests; GC callbacks observe process collections during each request, not exclusive route CPU time')
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:
        engine.dispose()
