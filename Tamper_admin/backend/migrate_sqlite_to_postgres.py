"""One-time SafeTrack data copy from SQLite into DATABASE_URL PostgreSQL."""

import argparse
import os
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select, text

from database import Base, engine as target_engine
import models  # noqa: F401 - registers every ORM table on Base.metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default=os.getenv("SQLITE_SOURCE", "safetrack.db"))
    parser.add_argument("--replace", action="store_true", help="delete target rows before copying")
    args = parser.parse_args()

    if target_engine.dialect.name != "postgresql":
        raise SystemExit("Set DATABASE_URL to the target PostgreSQL connection string first.")
    source_path = Path(args.sqlite).resolve()
    if not source_path.is_file():
        raise SystemExit(f"SQLite source not found: {source_path}")

    source_engine = create_engine(f"sqlite:///{source_path.as_posix()}")
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)
    Base.metadata.create_all(target_engine)
    tables = list(Base.metadata.sorted_tables)

    with source_engine.connect() as source, target_engine.begin() as target:
        occupied = [table.name for table in tables if target.scalar(select(func.count()).select_from(table))]
        if occupied and not args.replace:
            raise SystemExit("Target contains data. Re-run with --replace only if that data may be overwritten.")
        if args.replace:
            for table in reversed(tables):
                target.execute(table.delete())
        for table in tables:
            source_table = source_metadata.tables.get(table.name)
            if source_table is None:
                print(f"{table.name}: source table absent, skipped")
                continue
            shared_names = [column.name for column in table.columns if column.name in source_table.c]
            rows = [dict(row) for row in source.execute(select(*(source_table.c[name] for name in shared_names))).mappings()]
            if rows:
                target.execute(table.insert(), rows)
            print(f"{table.name}: {len(rows)} rows")
        for table in tables:
            if "id" in table.c:
                target.execute(text(
                    "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM \"" + table.name + "\"), 1), true)"
                ), {"table_name": table.name})

    print("SQLite to PostgreSQL migration complete.")


if __name__ == "__main__":
    main()
