"""Check fresh install and legacy adoption without touching application records."""
import os
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_security as fixture  # Establish isolated application configuration first.
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text, MetaData
from migrations.schema import target_metadata

ROOT = Path(__file__).resolve().parents[1]


class MigrationTests(unittest.TestCase):
    @unittest.skipUnless(os.getenv('SAFETRACK_TEST_DATABASE_URL'),'Requires disposable local PostgreSQL')
    def test_postgresql_fresh_security_migrations(self):
        from database import engine as app_engine
        import secrets
        from sqlalchemy.engine import make_url
        self.assertIn(app_engine.url.host,('localhost','127.0.0.1'))
        self.assertEqual(app_engine.url.database,'safetrack_test')
        name = 'safetrack_migration_' + secrets.token_hex(6)
        migration_url = app_engine.url.set(database=name)
        with app_engine.connect().execution_options(isolation_level='AUTOCOMMIT') as owner:
            owner.execute(text('CREATE DATABASE '+name))
            try:
                with patch.dict(os.environ,DATABASE_URL=migration_url.render_as_string(hide_password=False)):
                    config = Config(str(ROOT/'alembic.ini'))
                    command.upgrade(config,'head')
                    command.check(config)
                    probe = create_engine(migration_url)
                    try:
                        with probe.connect() as connection:
                            self.assertIn('device_replay_nonces',inspect(connection).get_table_names())
                            self.assertEqual(connection.execute(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity")).scalar(),0)
                    finally:
                        probe.dispose()
                    command.downgrade(config,'0003_report_cache_revision')
            finally:
                owner.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))

    def test_postgresql_index_ddl_is_concurrent_and_outside_transaction(self):
        with patch.dict(os.environ, DATABASE_URL='postgresql+psycopg://localhost/offline_only'):
            output = io.StringIO()
            config = Config(str(ROOT/'alembic.ini'), output_buffer=output)
            command.upgrade(config, '0001_existing_schema:0002_evidence_cursor_index', sql=True)
            sql = output.getvalue()
            self.assertIn('COMMIT;', sql)
            self.assertIn('CREATE INDEX CONCURRENTLY ix_events_shipment_id', sql)
            output = io.StringIO()
            config = Config(str(ROOT/'alembic.ini'), output_buffer=output)
            command.downgrade(config, '0002_evidence_cursor_index:0001_existing_schema', sql=True)
            self.assertIn('DROP INDEX CONCURRENTLY ix_events_shipment_id', output.getvalue())

    def test_empty_database_upgrade_check_and_downgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            url = 'sqlite:///' + (Path(directory)/'migration.db').as_posix()
            with patch.dict(os.environ, DATABASE_URL=url):
                config = Config(str(ROOT/'alembic.ini'))
                command.upgrade(config, 'head')
                command.check(config)
                engine = create_engine(url)
                try:
                    with engine.connect() as connection:
                        self.assertIn('sensor_events', inspect(connection).get_table_names())
                        indexes = inspect(connection).get_indexes('sensor_events')
                        self.assertIn('ix_events_shipment_time', [index['name'] for index in indexes])
                    command.downgrade(config, 'base')
                    self.assertNotIn('sensor_events', inspect(engine).get_table_names())
                finally:
                    engine.dispose()

    def test_adopting_existing_schema_preserves_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            url = 'sqlite:///' + (Path(directory)/'legacy.db').as_posix()
            engine = create_engine(url)
            try:
                legacy = MetaData()
                for table in target_metadata.sorted_tables:
                    if table.name in ('cache_revisions','device_replay_nonces'):
                        continue
                    table.to_metadata(legacy)
                for name in ('key_hash','key_version','replay_policy','replay_boot'):
                    legacy.tables['devices']._columns.remove(legacy.tables['devices'].c[name])
                table = legacy.tables['sensor_events']
                for index in list(table.indexes):
                    if index.name == 'ix_events_shipment_id':
                        table.indexes.remove(index)
                legacy.create_all(engine)
                with engine.begin() as connection:
                    connection.execute(text("INSERT INTO system_settings (category,key,value) VALUES ('test','retained','yes')"))
                with patch.dict(os.environ, DATABASE_URL=url):
                    config = Config(str(ROOT/'alembic.ini'))
                    command.stamp(config,'0001_existing_schema')
                    command.upgrade(config,'head')
                    command.check(config)
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(text("SELECT value FROM system_settings WHERE key='retained'")).scalar(),'yes')
            finally:
                engine.dispose()
