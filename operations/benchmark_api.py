"""Serial warm API baseline and exact SQL plans against synthetic local PostgreSQL."""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import secrets
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

from seed_benchmark import ROOT, validate_target


def percentile(samples, fraction):
    return sorted(samples)[max(0, math.ceil(len(samples) * fraction)-1)]


def benchmark(url, output, samples=30, seed_metadata=None):
    validate_target(url)
    if samples < 2:
        raise ValueError('Use at least two samples')
    os.environ.update(DATABASE_URL=url, SAFETRACK_ENV='production', DEMO_RESET='false')
    for name in ('JWT_SECRET', 'DEVICE_API_KEY', 'BOOTSTRAP_ADMIN_PASSWORD', 'DEMO_USER_PASSWORD'):
        os.environ[name] = secrets.token_urlsafe(36)
    sys.path.insert(0, str(ROOT / 'Tamper_admin/backend'))
    from main import app
    from database import engine
    from fastapi.testclient import TestClient
    from sqlalchemy import event, text
    measurements = []
    captured = []
    alert_history = None
    def before(conn, cursor, statement, parameters, context, executemany):
        context.benchmark_started = time.perf_counter()
    def after(conn, cursor, statement, parameters, context, executemany):
        captured.append((statement, parameters, (time.perf_counter()-context.benchmark_started)*1000))
    try:
        with TestClient(app) as client:
            response = client.post('/api/auth/login', json=dict(username='admin', password=os.environ['BOOTSTRAP_ADMIN_PASSWORD']))
            response.raise_for_status()
            headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
            paths = ['/api/admin/dashboard', '/api/vehicles', '/api/shipments', '/api/alerts',
                     '/api/shipments/BENCH-SHIP-00000', '/api/shipments/BENCH-SHIP-00000/live',
                     '/api/shipments/BENCH-SHIP-00000/evidence?limit=100', '/api/reports/summary']
            event.listen(engine, 'before_cursor_execute', before)
            event.listen(engine, 'after_cursor_execute', after)
            try:
                for path in paths:
                    for _ in range(3):
                        response = client.get(path, headers=headers)
                        response.raise_for_status()
                        if '/evidence?' in path:
                            verification = response.json()['verification']
                            if len(verification) != 100 or any(row['integrity'] != 'verified' for row in verification):
                                raise RuntimeError('Seed evidence failed integrity validation')
                    captured.clear()
                    latencies, calls, sizes = [], [], []
                    for _ in range(samples):
                        count_before = len(captured)
                        started = time.perf_counter()
                        response = client.get(path, headers=headers)
                        latencies.append((time.perf_counter()-started)*1000)
                        response.raise_for_status()
                        calls.append(len(captured)-count_before)
                        sizes.append(len(response.content))
                    measurements.append(dict(path=path, p50_ms=round(percentile(latencies,.5),3),
                        p95_ms=round(percentile(latencies,.95),3), mean_db_calls=statistics.mean(calls),
                        response_bytes=sizes[0], raw_ms=latencies))
                    # Retain distinct exact SQL and bindings from each endpoint.
                    measurements[-1]['sql'] = list(captured)
                # Preserve a full-history comparison: the new default alert
                # page is smaller than Phase 0's unbounded response.
                history_ms, history_calls = [], []
                for attempt in range(samples + 3):
                    captured.clear()
                    before_id = None
                    ids = []
                    started = time.perf_counter()
                    while True:
                        params = {'limit': 500}
                        if before_id is not None:
                            params['before_id'] = before_id
                        response = client.get('/api/alerts',params=params,headers=headers)
                        response.raise_for_status()
                        page = response.json()
                        ids.extend(row['id'] for row in page)
                        if len(page) != 500:
                            break
                        next_id = page[-1]['id']
                        if before_id is not None and next_id >= before_id:
                            raise RuntimeError('Cursor did not advance')
                        before_id = next_id
                    elapsed = (time.perf_counter()-started)*1000
                    if len(ids) != len(set(ids)):
                        raise RuntimeError('Alert pagination returned duplicates')
                    if attempt >= 3:
                        history_ms.append(elapsed)
                        history_calls.append(len(captured))
                alert_history = dict(p50_ms=percentile(history_ms,.5),p95_ms=percentile(history_ms,.95),
                    mean_db_calls=statistics.mean(history_calls), rows=len(ids),raw_ms=history_ms,
                    description='Complete alert history via limit=500 descending keyset pages, including authentication per page')
            finally:
                event.remove(engine, 'before_cursor_execute', before)
                event.remove(engine, 'after_cursor_execute', after)
        queries = {}
        for item in measurements:
            for sql, params, elapsed in item.pop('sql'):
                if not sql.lstrip().upper().startswith('SELECT'):
                    continue
                entry = queries.setdefault(sql, dict(params=params, times=[], path=item['path']))
                entry['times'].append(elapsed)
        plans = []
        with engine.connect() as conn:
            version = conn.execute(text('SELECT version()')).scalar()
            counts = {table: conn.execute(text(f'SELECT count(*) FROM {table}')).scalar()
                      for table in ('sensor_events','devices','shipments','shipment_alerts')}
            size = conn.execute(text('SELECT pg_database_size(current_database())')).scalar()
            for sql, detail in sorted(queries.items(), key=lambda pair: statistics.mean(pair[1]['times']), reverse=True)[:5]:
                if detail['path'] == '/api/reports/summary':
                    conn.exec_driver_sql('SET LOCAL max_parallel_workers_per_gather = 0')
                else:
                    conn.exec_driver_sql('SET LOCAL max_parallel_workers_per_gather = DEFAULT')
                plan = conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql, detail['params']).scalar()
                plans.append(dict(endpoint=detail['path'], sql=sql, parameters=detail['params'],
                    mean_execute_ms=statistics.mean(detail['times']), plan=plan))
        result = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
            commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            platform=platform.platform(), python=platform.python_version(), postgres=version,
            logical_cpus=os.cpu_count(), processor=platform.processor(),
            tool_sha256={name:hashlib.sha256((ROOT/'operations'/name).read_bytes()).hexdigest()
                         for name in ('seed_benchmark.py','benchmark_api.py','run_benchmark.py')},
            versions={p:importlib.metadata.version(p) for p in ('fastapi','sqlalchemy','psycopg','httpx')},
            samples=samples, concurrency=1, warmups=3, counts=counts, database_bytes=size,
            seed=seed_metadata, endpoints=measurements, slowest_sql=plans)
        result['alert_history'] = alert_history
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.with_suffix('.json').write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
        rows = ['# API benchmark run', '', f"Measured {result['timestamp_utc']} at application commit {result['commit']}.",
                '', f"Environment: {result['platform']}, Python {result['python']}, {version}.",
                f"Dataset counts: {counts}. Database bytes including indexes: {size:,}.",
                '', 'Synthetic legacy-format, hash-linked events with exposure, shock and temperature excursions. No hardware signatures. Bulk seeding bypasses ingestion.',
                f'Serial FastAPI TestClient requests, concurrency 1, three warmups and {samples} timed requests per endpoint. JWT authentication, serialization and SQL included. Login excluded. Local PostgreSQL, warm caches, no network/TLS/browser rendering. p50/p95 use nearest-rank percentiles.',
                'API startup also adds its existing demo shipments/devices/vehicles. The seeded benchmark shipment is used for detail/live/evidence reads.',
                '', '| Endpoint | p50 ms | p95 ms | DB calls/request | Response bytes |',
                '| --- | ---: | ---: | ---: | ---: |']
        for item in measurements:
            rows.append(f"| {item['path']} | {item['p50_ms']} | {item['p95_ms']} | {item['mean_db_calls']} | {item['response_bytes']} |")
        rows += ['', '## Slow SQL plans', '', 'Exact application-generated statements, parameters and PostgreSQL EXPLAIN ANALYZE BUFFERS output follow. Ranking uses mean cursor execution time, excluding ORM hydration and response serialization. Plans run after the timed API requests.']
        for plan in plans:
            rows += ['', f"### {plan['endpoint']}", '', f"Mean SQL execution {plan['mean_execute_ms']:.3f} ms.",
                     '', '```sql', plan['sql'], '```', '', 'Parameters: '+json.dumps(plan['parameters'],default=str),
                     '', '```json', json.dumps(plan['plan'],indent=2), '```']
        rows += ['', '## Interpretation and next comparison', '',
                 'These are local measurements. The static admin dashboard loads vehicles, shipments and alerts separately. Its list endpoints must be evaluated together when optimizing query count. Live telemetry uses an existing shipment/time index and evidence already has cursor pagination.',
                 'Repeat the same event count, device count, seed, warmups and samples after each change. Raw timings and query plans are in the adjacent JSON file. Measure ingestion and signature-heavy version-2 evidence separately before making claims about those paths.']
        output.write_text('\n'.join(rows)+'\n',encoding='utf-8')
        print(json.dumps(dict(counts=counts, endpoints=measurements, report=str(output)),indent=2))
        return result
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/benchmarks/baseline.md')
    parser.add_argument('--samples', type=int, default=30)
    args = parser.parse_args()
    benchmark(os.environ['BENCHMARK_DATABASE_URL'], args.output, args.samples)
