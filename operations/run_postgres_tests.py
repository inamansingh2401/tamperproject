"""Run regressions in a fresh, authenticated, disposable loopback PostgreSQL cluster."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from sqlalchemy.engine import URL
import psycopg
from backup_database import run

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--pg-bin',type=Path,default=Path('C:/Program Files/PostgreSQL/18/bin'))
    parser.add_argument('--port',type=int,default=25433)
    args=parser.parse_args()
    scratch_root=ROOT/'.codex-tools';scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='postgres-tests-',dir=scratch_root) as directory:
        scratch=Path(directory);data=scratch/'cluster'
        password=secrets.token_urlsafe(32);pwfile=scratch/'password.local.txt';pwfile.write_text(password)
        env=dict(os.environ,PGHOST='127.0.0.1',PGPORT=str(args.port),PGUSER='tracksure_test',PGPASSWORD=password,
                 PGDATABASE='postgres',PGSSLMODE='disable')
        run([str(args.pg_bin/'initdb.exe'),'-D',str(data),'-U','tracksure_test','--pwfile',str(pwfile),
             '--auth-host=scram-sha-256','--auth-local=scram-sha-256','--encoding=UTF8'],env)
        started=False
        try:
            run([str(args.pg_bin/'pg_ctl.exe'),'-D',str(data),'-l',str(scratch/'postgres.local.log'),
                 '-o',f'-h 127.0.0.1 -p {args.port}','-w','start'],env)
            started=True
            with psycopg.connect(host='127.0.0.1',port=args.port,user='tracksure_test',password=password,dbname='postgres',autocommit=True) as db:
                if Path(db.execute("SELECT current_setting('data_directory')").fetchone()[0]).resolve()!=data.resolve():
                    raise RuntimeError('Target is not our disposable cluster')
                db.execute('CREATE DATABASE safetrack_test')
            env['SAFETRACK_TEST_DATABASE_URL']=URL.create('postgresql+psycopg',username='tracksure_test',password=password,
                                                         host='127.0.0.1',port=args.port,database='safetrack_test').render_as_string(hide_password=False)
            result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py'],cwd=ROOT,env=env)
            if result.returncode:
                raise SystemExit(result.returncode)
        finally:
            if started:
                run([str(args.pg_bin/'pg_ctl.exe'),'-D',str(data),'-m','fast','-w','stop'],env)


if __name__=='__main__':
    main()
