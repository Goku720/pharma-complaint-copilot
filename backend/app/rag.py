"""
Local, no-external-API RAG layer over pharmaceutical regulatory guidance
(ICH Q9(R1), ICH Q10, ICH Q7, 21 CFR 211 Subpart J, WHO GMP — see
regulatory_docs/), grounding the agent's assess_risk reasoning in actual
regulatory text instead of the LLM's own recall.

Storage: Postgres, via pgvector (regulatory_chunks table in db_models.py) —
not a separate vector database. This keeps the whole persistence layer on
one engine: the app already stores complaint sessions as Postgres JSON
columns, so semantic search over regulatory guidance lives right alongside
it instead of standing up Chroma/Qdrant/etc. as a second store to run,
back up, and deploy. This is Postgres-specific (pgvector has no MySQL
equivalent); on a MySQL DATABASE_URL, retrieve() below just returns []
and the agent falls back to reasoning from its own knowledge — nothing
else breaks.

Embeddings: chromadb's local ONNX MiniLM-L6-v2 model, used purely as an
embedding function (no chromadb server/store involved) — downloaded once
on first use to ~/.cache/chroma, no API key, no torch dependency.
"""
from __future__ import annotations

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import DATABASE_URL, SessionLocal

_embedder = None


class RetrievedChunk(NamedTuple):
    text: str
    source: str
    chunk_index: int
    distance: float


def is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")


def _get_embedder():
    global _embedder
    if _embedder is None:
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

        _embedder = ONNXMiniLM_L6_V2()
    return _embedder


def embed(texts: list[str]) -> list[list[float]]:
    return _get_embedder()(texts)


def upsert_chunks(source: str, chunks: list[str]) -> int:
    """Embeds and stores chunks for one source document, replacing any
    existing chunks for that (source, chunk_index) pair. Postgres-only —
    see module docstring."""
    if not is_postgres():
        raise RuntimeError(
            "Regulatory RAG ingestion requires DATABASE_URL to point at Postgres "
            "(pgvector). The rest of the app works fine on MySQL; this feature "
            "doesn't."
        )
    from app.db_models import RegulatoryChunk

    vectors = embed(chunks)
    db = SessionLocal()
    try:
        for i, (text, vec) in enumerate(zip(chunks, vectors)):
            stmt = pg_insert(RegulatoryChunk).values(
                source=source, chunk_index=i, content=text, embedding=vec
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["source", "chunk_index"],
                set_={"content": stmt.excluded.content, "embedding": stmt.excluded.embedding},
            )
            db.execute(stmt)
        db.commit()
        return len(chunks)
    finally:
        db.close()


def is_corpus_ready() -> bool:
    if not is_postgres():
        return False
    from app.db_models import RegulatoryChunk

    db = SessionLocal()
    try:
        return db.query(RegulatoryChunk).first() is not None
    finally:
        db.close()


def retrieve(query: str, k: int = 4) -> list[RetrievedChunk]:
    """Returns the top-k most relevant regulatory chunks for the query
    (cosine distance via pgvector). Returns [] gracefully if the corpus
    hasn't been ingested yet, or DATABASE_URL isn't Postgres — the agent
    just falls back to its own knowledge in that case."""
    if not query or not query.strip() or not is_postgres():
        return []
    from app.db_models import RegulatoryChunk

    db = SessionLocal()
    try:
        if db.query(RegulatoryChunk).first() is None:
            return []
        [query_vec] = embed([query])
        rows = db.execute(
            select(
                RegulatoryChunk.content,
                RegulatoryChunk.source,
                RegulatoryChunk.chunk_index,
                RegulatoryChunk.embedding.cosine_distance(query_vec).label("distance"),
            )
            .order_by("distance")
            .limit(k)
        ).all()
        return [
            RetrievedChunk(text=r.content, source=r.source, chunk_index=r.chunk_index, distance=r.distance)
            for r in rows
        ]
    finally:
        db.close()


def format_for_prompt(chunks: list["RetrievedChunk"]) -> str:
    """Formats retrieved chunks for the agent's system prompt. Deliberately
    omits chunk_index from the visible label — it's an arbitrary slice
    position, not a meaningful citation, and including it invited the model
    to echo things like "(excerpt 91)" into user-facing rationale text."""
    if not chunks:
        return ""
    blocks = [f"[Source: {c.source}]\n{c.text.strip()}" for c in chunks]
    return "\n\n".join(blocks)