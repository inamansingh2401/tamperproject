"""Own a disposable PostgreSQL cluster, seed it and save a reproducible baseline."""
import argparse
import os
from pathlib import Path
import secrets
import tempfile

import psycopg
from sqlalchemy.engine import URL
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
            url = URL.create('postgresql+psycopg', username='safetrack_benchmark',
                password=password, host='127.0.0.1', port=args.port, database='safetrack_benchmark').render_as_string(hide_password=False)
            metadata = seed(url, args.events, args.devices)
            benchmark(url, args.output, args.samples, metadata)
        finally:
            if started:
                run([str(args.pg_bin/'pg_ctl.exe'), '-D', str(data), '-m', 'fast', '-w', 'stop'], env)


if __name__ == '__main__':
    main()
