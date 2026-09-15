import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./safetrack.db").strip()

# Older providers still expose postgresql:// URLs. SQLAlchemy's explicit
# psycopg v3 driver form is predictable on Render and locally.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

connect_args = {"check_same_thread": False, "timeout": 15} if "sqlite" in DATABASE_URL else {}

engine_options = {"connect_args": connect_args, "pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    engine_options.update({"pool_recycle": 300, "pool_size": 5, "max_overflow": 5})

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
