"""Check fresh install and legacy adoption without touching application records."""
import os
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
                    table.to_metadata(legacy)
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
