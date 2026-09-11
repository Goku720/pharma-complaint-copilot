from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.db import Base

# pgvector's SQLAlchemy type is Postgres-only. Importing it is harmless even
# on a MySQL DATABASE_URL (it's just a column type declaration), but the
# RegulatoryChunk table itself will only ever be created/used against
# Postgres — see app/rag.py for why.
from pgvector.sqlalchemy import Vector

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size


class ComplaintSession(Base):
    """One row per browser session: the form, the AI risk assessment, and
    the chat history, all as JSON blobs. A session holds exactly one
    complaint at a time (matching the UI's "New complaint" reset button)."""

    __tablename__ = "complaint_sessions"

    session_id = Column(String(64), primary_key=True)
    form = Column(JSON, nullable=False, default=dict)
    risk = Column(JSON, nullable=False, default=dict)
    history = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ComplaintRecord(Base):
    """One row per complaint ID. This is the durable complaint registry that
    survives a browser session reset and the UI's in-session state model."""

    __tablename__ = "complaint_records"

    complaint_id = Column(String(32), primary_key=True)
    session_id = Column(String(64), nullable=False)
    form = Column(JSON, nullable=False, default=dict)
    risk = Column(JSON, nullable=False, default=dict)
    history = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RegulatoryChunk(Base):
    """One row per chunk of an ingested regulatory document (ICH Q9(R1),
    ICH Q10, ICH Q7, 21 CFR 211, WHO GMP, ...), with its embedding stored
    alongside it via pgvector. Lives in the same Postgres database as the
    rest of the app's data rather than a separate vector store — see
    app/rag.py for the reasoning. Requires DATABASE_URL to be Postgres with
    the `vector` extension enabled (app/db.py:init_db() does this
    automatically)."""

    __tablename__ = "regulatory_chunks"
    __table_args__ = (UniqueConstraint("source", "chunk_index", name="uq_regulatory_chunk_source_idx"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False)  # filename, e.g. "ICH_Q9R1.pdf"
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)


class ComplaintIdCounter(Base):
    """A row is inserted every time a new complaint is logged; the
    auto-increment primary key doubles as a globally unique, gap-free-enough
    complaint sequence number. Works identically on Postgres and MySQL."""

    __tablename__ = "complaint_id_counter"

    id = Column(Integer, primary_key=True, autoincrement=True)