#!/usr/bin/env python3
"""
Ingests every PDF/.txt file in backend/regulatory_docs/ into the
regulatory_chunks table (Postgres + pgvector) used by app/rag.py for
grounded risk-assessment reasoning.

Usage:
    cd backend
    python3 scripts/ingest_docs.py

Requires DATABASE_URL to point at Postgres — this is pgvector-backed, see
app/rag.py for why. Re-run any time you add/replace a file in
regulatory_docs/ — ingestion is idempotent (upsert on source + chunk_index).

Recommended starter corpus (see README for why these and not e.g. ICH Q12 or
EU GMP):
  - ICH Q9(R1)   — Quality Risk Management
  - ICH Q10      — Pharmaceutical Quality System (complaint handling)
  - ICH Q7       — GMP for Active Pharmaceutical Ingredients
  - 21 CFR 211 Subpart J (211.192, 211.198) — public domain, complaint files
  - WHO GMP      — complaints & product recall chapter
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pypdf import PdfReader  # noqa: E402
from app import rag  # noqa: E402

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "regulatory_docs")
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


def extract_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = " ".join(text.split())  # normalize whitespace so chunk boundaries land on real content
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def main():
    if not rag.is_postgres():
        print("DATABASE_URL is not Postgres — regulatory RAG ingestion requires pgvector. Aborting.")
        return

    if not os.path.isdir(DOCS_DIR):
        print(f"No {DOCS_DIR} directory found — nothing to ingest.")
        return

    files = [f for f in sorted(os.listdir(DOCS_DIR)) if f.lower().endswith((".pdf", ".txt"))]
    if not files:
        print(f"No .pdf/.txt files found in {DOCS_DIR}. Drop your regulatory PDFs there first.")
        return

    total_chunks = 0
    for fname in files:
        path = os.path.join(DOCS_DIR, fname)
        text = extract_text(path)
        if not text.strip():
            print(f"  ! {fname}: no extractable text, skipping")
            continue
        pieces = chunk_text(text)
        n = rag.upsert_chunks(fname, pieces)
        total_chunks += n
        print(f"  ✓ {fname}: {n} chunks")

    print(f"\nDone. {total_chunks} chunks ingested/updated in regulatory_chunks.")


if __name__ == "__main__":
    main()