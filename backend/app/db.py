"""
Database engine setup. The core app (sessions, complaint records, the ID
counter) works with either Postgres or MySQL — just point DATABASE_URL at
whichever you're running:

  Postgres:  postgresql+psycopg2://user:password@host:5432/qms_pharma
  MySQL:     mysql+pymysql://user:password@host:3306/qms_pharma

The one exception is the regulatory-guidance RAG table (regulatory_chunks,
see db_models.py / app/rag.py), which uses pgvector and is Postgres-only —
that's a deliberate choice to keep vector storage in the same database as
the rest of the app's state instead of running a second store, rather than
chasing MySQL/Postgres parity on that one feature. On MySQL, everything
else still works; RAG grounding just becomes a no-op.
"""
from __future__ import annotations

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://qms_user:qms_pass@localhost:5432/qms_pharma",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    """Create tables if they don't exist yet. Called once at app startup."""
    from app import db_models  # noqa: F401  (ensures models are registered on Base)

    if DATABASE_URL.startswith("postgresql"):
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(bind=engine)
    else:
        # Skip the pgvector-backed RegulatoryChunk table on non-Postgres
        # engines — create everything else normally.
        from app.db_models import RegulatoryChunk

        tables = [t for t in Base.metadata.sorted_tables if t is not RegulatoryChunk.__table__]
        Base.metadata.create_all(bind=engine, tables=tables)