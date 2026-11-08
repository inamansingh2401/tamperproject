"""Measure the evidence cursor query before/after a candidate shipment/id index."""
import json
from pathlib import Path
import time
from sqlalchemy import create_engine
from seed_benchmark import ROOT, validate_target
from benchmark_api import percentile


def profile(url, output, samples=30):
    validate_target(url)
    data = json.loads((ROOT/'docs/benchmarks/phase1-run.json').read_text())
    query = next(row for row in data['slowest_sql'] if '/evidence?' in row['endpoint'])
    engine = create_engine(url)
    result = {}
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('DROP INDEX IF EXISTS ix_events_shipment_id')
            for stage in ('before', 'after'):
                if stage == 'after':
                    connection.exec_driver_sql('CREATE INDEX ix_events_shipment_id ON sensor_events (shipment_id, id)')
                durations = []
                for attempt in range(samples+3):
                    start = time.perf_counter()
                    records = connection.exec_driver_sql(query['sql'],query['parameters']).fetchall()
                    elapsed = (time.perf_counter()-start)*1000
                    if attempt >= 3:
                        durations.append(elapsed)
                plan = connection.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+query['sql'],query['parameters']).scalar()
                result[stage] = dict(p50_ms=percentile(durations,.5),p95_ms=percentile(durations,.95),
                    raw_ms=durations,rows=len(records),plan=plan)
            connection.rollback()  # Candidate exists only inside this experiment.
        result.update(sql=query['sql'],parameters=query['parameters'],
                      scope='Exact evidence SQL, same 100k seed, cursor zero and limit 101, three warmups and 30 serial executions')
        Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({stage:{key:value for key,value in result[stage].items() if key not in ('plan','raw_ms')}
                          for stage in ('before','after')},indent=2))
    finally:
        engine.dispose()
