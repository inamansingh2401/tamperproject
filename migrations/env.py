"""Read the connection URL only from the environment."""
import os
from alembic import context
from sqlalchemy import create_engine, pool
from migrations.schema import target_metadata

url = os.environ['DATABASE_URL'].strip()
if url.startswith('postgres://'):
    url = 'postgresql+psycopg://' + url[len('postgres://'):]
elif url.startswith('postgresql://'):
    url = 'postgresql+psycopg://' + url[len('postgresql://'):]

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                              transaction_per_migration=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
