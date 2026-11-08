"""Exercise concurrent index migration while a writer holds a transaction open."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psycopg
from sqlalchemy.engine import make_url
from backup_database import run
from seed_benchmark import ROOT


def verify(url, output):
    target = make_url(url)
    if target.host != '127.0.0.1' or target.database != 'safetrack_migration':
        raise ValueError('Only the owned disposable migration database is supported')
    env = dict(os.environ, DATABASE_URL=url)
    base = [sys.executable,'-m','alembic','-c',str(ROOT/'alembic.ini')]
    run(base+['upgrade','0001_existing_schema'], env)
    params = dict(host=target.host,port=target.port,user=target.username,password=target.password,dbname=target.database)
    process = None
    with psycopg.connect(**params) as held, psycopg.connect(**params,autocommit=True) as observer:
        observer.execute("INSERT INTO shipments (shipment_code) VALUES ('concurrent-test')")
        held.execute("INSERT INTO sensor_events (shipment_id,device_id,previous_hash,record_hash) VALUES (1,'held','0','0')")
        try:
            process = subprocess.Popen(base+['upgrade','0002_evidence_cursor_index'],env=env,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            deadline = time.monotonic()+15
            while time.monotonic() < deadline:
                waiting = observer.execute("SELECT phase FROM pg_stat_progress_create_index WHERE relid='sensor_events'::regclass").fetchone()
                if waiting and 'waiting for writers' in waiting[0]:
                    break
                if process.poll() is not None:
                    raise RuntimeError('Index process exited before concurrent-write check')
                time.sleep(.05)
            else:
                raise RuntimeError('Did not observe the expected concurrent-build wait')
            observer.execute("SET statement_timeout='1500ms'")
            started = time.perf_counter()
            observer.execute("INSERT INTO sensor_events (shipment_id,device_id,previous_hash,record_hash) VALUES (1,'second','0','0')")
            write_ms = (time.perf_counter()-started)*1000
            held.commit()
            if process.wait(timeout=15):
                raise RuntimeError('Concurrent index migration failed')
            valid = observer.execute("SELECT indisvalid,indisready FROM pg_index WHERE indexrelid='ix_events_shipment_id'::regclass").fetchone()
            assert valid == (True, True)
            result = dict(second_insert_ms=write_ms, statement_timeout_ms=1500,
                observed_phase=waiting[0], index_valid=True,
                scope='Disposable local PostgreSQL; one held writer and one additional insert during CREATE INDEX CONCURRENTLY')
            Path(output).write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result))
        finally:
            held.rollback()
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
    run(base+['downgrade','0001_existing_schema'],env)
    run(base+['downgrade','base'],env)
