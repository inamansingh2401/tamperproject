"""Private PostgreSQL backup and optional isolated restore drill. Never restores production."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from datetime import datetime, timezone
from sqlalchemy.engine import make_url


def run(command, env):
    # On Windows a started postmaster inherits pipes, keeping communicate()
    # blocked even after pg_ctl exits. Daemon control must not use output pipes.
    daemon = Path(command[0]).name == 'pg_ctl.exe'
    result = subprocess.run(command, env=env, stdout=subprocess.DEVNULL if daemon else subprocess.PIPE,
                            stderr=subprocess.DEVNULL if daemon else subprocess.PIPE, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        detail = next((line for line in (result.stderr or '').splitlines() if line.startswith('pg_restore: error:')), 'details withheld')
        if env.get('PGPASSWORD'):
            detail = detail.replace(env['PGPASSWORD'],'[redacted]')
        raise RuntimeError(f'{Path(command[0]).name} failed (exit {result.returncode}): {detail[:180]}')
    return result.stdout or ''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path, help='Ignored JSON file containing DATABASE_URL in value')
    parser.add_argument('--output-dir', type=Path, default=Path('.codex-tools/backups'))
    parser.add_argument('--pg-bin', type=Path, default=Path('C:/Program Files/PostgreSQL/18/bin'))
    parser.add_argument('--restore-check', action='store_true')
    parser.add_argument('--restore-from',type=Path,help='Check an existing private backup without exporting again')
    parser.add_argument('--restore-port', type=int, default=25432)
    args = parser.parse_args()
    url = os.getenv('DATABASE_URL')
    if args.env_file:
        url = json.loads(args.env_file.read_text())['value']
    if not url and not args.restore_from:
        raise SystemExit('DATABASE_URL or private --env-file is required')
    connection = make_url(url) if url else None
    if connection and not connection.drivername.startswith('postgresql'):
        raise SystemExit('PostgreSQL only')
    directory = args.output_dir.resolve()
    # Backups contain accounts and device credentials. Never write to a public source directory.
    if '.codex-tools' not in directory.parts:
        raise SystemExit('Use a private ignored .codex-tools output directory')
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = args.restore_from.resolve() if args.restore_from else directory / f'safetrack-{stamp}-{secrets.token_hex(3)}.dump'
    if not backup.is_relative_to(directory):
        raise SystemExit('Restore input must be a private backup inside output-dir')
    environment = dict(os.environ)
    if not args.restore_from:
        environment.update(PGHOST=connection.host, PGPORT=str(connection.port or 5432),
                           PGUSER=connection.username, PGPASSWORD=connection.password or '',
                           PGDATABASE=connection.database or 'postgres', PGSSLMODE='require')
        run([str(args.pg_bin/'pg_dump.exe'), '--schema=public', '--format=custom', '--no-owner', '--no-acl', '--file',str(backup)], environment)
    manifest = run([str(args.pg_bin/'pg_restore.exe'), '--list',str(backup)], environment)
    result = {'backup':str(backup),'bytes':backup.stat().st_size,'archive_readable':bool(manifest),'restore':'NOT TESTED','verified_at':stamp}
    if args.restore_check:
        import psycopg
        # A fresh authenticated loopback cluster on a separate port, never the production URL.
        with tempfile.TemporaryDirectory(prefix='tracksure-restore-',dir=directory) as temp:
            scratch = Path(temp)
            password = secrets.token_urlsafe(32)
            pwfile = scratch/'restore.local.txt'
            pwfile.write_text(password)
            local_env = dict(os.environ, PGHOST='127.0.0.1',PGPORT=str(args.restore_port),PGUSER='tracksure_restore',
                             PGPASSWORD=password,PGDATABASE='postgres',PGSSLMODE='disable')
            data = scratch/'cluster'
            run([str(args.pg_bin/'initdb.exe'),'-D',str(data),'-U','tracksure_restore', '--pwfile',str(pwfile),
                 '--auth-host=scram-sha-256','--auth-local=scram-sha-256','--encoding=UTF8'],local_env)
            started = False
            try:
                run([str(args.pg_bin/'pg_ctl.exe'),'-D',str(data),'-l',str(scratch/'restore.local.log'),'-o',
                     f'-h 127.0.0.1 -p {args.restore_port}', '-w','start'],local_env)
                started = True
                with psycopg.connect(host='127.0.0.1',port=args.restore_port,user='tracksure_restore',password=password,dbname='postgres') as db:
                    actual_directory = Path(db.execute("SELECT current_setting('data_directory')").fetchone()[0]).resolve()
                    if actual_directory != data.resolve() or db.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'").fetchone()[0]:
                        raise RuntimeError('Restore target is not our newly created empty cluster')
                    # The archive creates public; remove ONLY the empty template
                    # schema in this authenticated, verified disposable cluster.
                    db.execute('DROP SCHEMA public')
                run([str(args.pg_bin/'pg_restore.exe'),'--dbname=postgres','--no-owner','--no-acl','--exit-on-error',str(backup)],local_env)
                with psycopg.connect(host='127.0.0.1',port=args.restore_port,user='tracksure_restore',password=password,dbname='postgres') as db:
                    result['restored_counts'] = {table:db.execute(f'SELECT count(*) FROM public.{table}').fetchone()[0]
                                                for table in ('users','devices','shipments','sensor_events','vehicles')}
                result['restore'] = 'PASS'
            finally:
                if started:
                    run([str(args.pg_bin/'pg_ctl.exe'),'-D',str(data),'-m','fast','-w','stop'],local_env)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
