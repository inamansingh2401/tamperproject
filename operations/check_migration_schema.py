"""Read-only schema comparison before adopting Alembic on an existing database."""
import os
import argparse
from pathlib import Path
import sys
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, MetaData

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from migrations.schema import target_metadata
from database import DATABASE_URL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', action='store_true', help='Compare against 0001 before adopting legacy databases')
    args = parser.parse_args()
    if not os.environ.get('DATABASE_URL'):
        raise SystemExit('Set DATABASE_URL in the environment')
    engine = create_engine(DATABASE_URL)
    try:
        metadata = MetaData()
        for table in target_metadata.sorted_tables:
            table.to_metadata(metadata)
        if args.baseline:
            table = metadata.tables['sensor_events']
            for index in list(table.indexes):
                if index.name == 'ix_events_shipment_id':
                    table.indexes.remove(index)
        with engine.connect() as connection:
            differences = compare_metadata(
                MigrationContext.configure(connection, opts={'compare_type': True}), metadata)
        if differences:
            raise SystemExit('Schema differs from the migration baseline. Review differences before stamping: '
                             + ', '.join(str(item[0]) for item in differences))
        print('PASS: schema matches the Alembic baseline; no changes applied')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
