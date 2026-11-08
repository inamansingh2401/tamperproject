"""Own a disposable PostgreSQL cluster, seed it and save a reproducible baseline."""
import argparse
import os
from pathlib import Path
import secrets
import sys
import tempfile

import psycopg
from sqlalchemy.engine import URL, make_url
from backup_database import run
from seed_benchmark import ROOT, seed
from benchmark_api import benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin', type=Path, default=Path('C:/Program Files/PostgreSQL/18/bin'))
    parser.add_argument('--port', type=int, default=25435)
    parser.add_argument('--events', type=int, default=100000)
    parser.add_argument('--devices', type=int, default=100)
    parser.add_argument('--samples', type=int, default=30)
    parser.add_argument('--reports-profile', action='store_true')
    parser.add_argument('--force-serial', action='store_true', help='Diagnostic report transactions only')
    parser.add_argument('--index-profile', action='store_true')
    parser.add_argument('--verify-migrations', action='store_true')
    parser.add_argument('--cache-mix', choices=['off','memory'])
    parser.add_argument('--high-churn', action='store_true')
    parser.add_argument('--ingest-concurrency', type=int, choices=[1,5,10,20])
    parser.add_argument('--without-revision', action='store_true', help='Ingestion benchmark process only')
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--ingest-policy', choices=['retry','rate'])
    parser.add_argument('--strict-device',action='store_true',help='Benchmark enrolled counter_v1 devices with digest-only credentials')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/benchmarks/baseline.md')
    args = parser.parse_args()
    if not 100000 <= args.events <= 500000:
        parser.error('Use 100000 through 500000 events')
    scratch_root = ROOT/'.codex-tools'
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='benchmark-', dir=scratch_root) as directory:
        scratch = Path(directory)
        data = scratch/'cluster'
        password = secrets.token_urlsafe(32)
        password_file = scratch/'password.local.txt'
        password_file.write_text(password)
        env = dict(os.environ, PGHOST='127.0.0.1', PGPORT=str(args.port),
                   PGUSER='safetrack_benchmark', PGPASSWORD=password, PGDATABASE='postgres', PGSSLMODE='disable')
        run([str(args.pg_bin/'initdb.exe'), '-D', str(data), '-U', 'safetrack_benchmark',
             '--pwfile', str(password_file), '--auth-host=scram-sha-256',
             '--auth-local=scram-sha-256', '--encoding=UTF8'], env)
        started = False
        try:
            run([str(args.pg_bin/'pg_ctl.exe'), '-D', str(data), '-l', str(scratch/'postgres.log'),
                 '-o', f'-h 127.0.0.1 -p {args.port}', '-w', 'start'], env)
            started = True
            with psycopg.connect(host='127.0.0.1', port=args.port, user='safetrack_benchmark',
                                 password=password, dbname='postgres', autocommit=True) as conn:
                if Path(conn.execute("SELECT current_setting('data_directory')").fetchone()[0]).resolve() != data.resolve():
                    raise RuntimeError('Target is not the owned cluster')
                conn.execute('CREATE DATABASE safetrack_benchmark')
                if args.verify_migrations:
                    conn.execute('CREATE DATABASE safetrack_migration')
            url = URL.create('postgresql+psycopg', username='safetrack_benchmark',
                password=password, host='127.0.0.1', port=args.port, database='safetrack_benchmark').render_as_string(hide_password=False)
            metadata = seed(url, args.events, args.devices)
            if args.verify_migrations:
                migration_url = make_url(url).set(database='safetrack_migration').render_as_string(hide_password=False)
                migration_env = dict(env, DATABASE_URL=migration_url)
                for arguments in (['upgrade','head'], ['check'], ['downgrade','base']):
                    run([sys.executable,'-m','alembic','-c',str(ROOT/'alembic.ini'),*arguments], migration_env)
                from verify_concurrent_index import verify
                verify(migration_url, args.output.parent/'concurrent-index.json')
                legacy_env = dict(env, DATABASE_URL=url)
                run([sys.executable,str(ROOT/'operations/check_migration_schema.py')], legacy_env)
                for arguments in (['stamp','head'], ['upgrade','head'], ['check']):
                    run([sys.executable,'-m','alembic','-c',str(ROOT/'alembic.ini'),*arguments], legacy_env)
                print('PASS: PostgreSQL fresh upgrade/downgrade and existing-schema adoption')
            if args.ingest_concurrency:
                from benchmark_ingestion import measure
                measure(url,args.output,args.ingest_concurrency,not args.without_revision,
                        batch_size=args.batch_size,policy=args.ingest_policy,strict=args.strict_device)
            elif args.cache_mix:
                from benchmark_cache import measure
                measure(url,args.output,args.cache_mix,args.high_churn)
            elif args.index_profile:
                from profile_evidence_index import profile
                profile(url,args.output,args.samples)
            elif args.reports_profile:
                from profile_reports import profile
                profile(url, args.output, args.samples, args.force_serial)
            else:
                benchmark(url, args.output, args.samples, metadata)
        finally:
            if started:
                run([str(args.pg_bin/'pg_ctl.exe'), '-D', str(data), '-m', 'fast', '-w', 'stop'], env)


if __name__ == '__main__':
    main()
