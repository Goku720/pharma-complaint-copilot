"""
Session store, backed by Postgres or MySQL (see app/db.py for the connection
string). Each session_id maps to exactly one row holding the current form,
the current AI risk assessment, and the chat history — all as JSON.

The public functions here (get_or_create_session, save_session,
next_complaint_id, reset_session) are the same shape as the original
in-memory version, so app/main.py and app/agent.py don't need to know
persistence changed.
"""
from __future__ import annotations

from app.db import SessionLocal
from app.db_models import ComplaintIdCounter, ComplaintRecord, ComplaintSession
from app.models import ChatTurn, ComplaintForm, RiskAssessment, SessionState


def migrate_records_from_sessions() -> None:
    """Backfill ComplaintRecord rows from legacy ComplaintSession rows that
    already carry a complaint_id inside their JSON form payload."""
    db = SessionLocal()
    try:
        for row in db.query(ComplaintSession).all():
            complaint_id = (row.form or {}).get("complaint_id")
            if not complaint_id:
                continue

            record = db.get(ComplaintRecord, complaint_id)
            if record is None:
                record = ComplaintRecord(
                    complaint_id=complaint_id,
                    session_id=row.session_id,
                    form={},
                    risk={},
                    history=[],
                )
                db.add(record)

            record.session_id = row.session_id
            record.form = row.form or {}
            record.risk = row.risk or {}
            record.history = row.history or []
        db.commit()
    finally:
        db.close()


def _to_state(row: ComplaintSession | ComplaintRecord) -> SessionState:
    """Shared converter: both ComplaintSession and ComplaintRecord expose the
    same session_id/form/risk/history shape, so one function covers both."""
    return SessionState(
        session_id=row.session_id,
        form=ComplaintForm(**(row.form or {})),
        risk=RiskAssessment(**(row.risk or {})),
        history=[ChatTurn(**turn) for turn in (row.history or [])],
    )


def get_or_create_session(session_id: str) -> SessionState:
    db = SessionLocal()
    try:
        row = db.get(ComplaintSession, session_id)
        if row is None:
            row = ComplaintSession(session_id=session_id, form={}, risk={}, history=[])
            db.add(row)
            db.commit()
            db.refresh(row)
        return _to_state(row)
    finally:
        db.close()


def save_session(state: SessionState) -> None:
    """Persist the (possibly agent-updated) form/risk/history back to the DB
    and mirror the complaint payload into a durable complaint record."""
    db = SessionLocal()
    try:
        row = db.get(ComplaintSession, state.session_id)
        if row is None:
            row = ComplaintSession(session_id=state.session_id)
            db.add(row)
        row.form = state.form.model_dump(exclude_none=True)
        row.risk = state.risk.model_dump(exclude_none=True)
        row.history = [turn.model_dump() for turn in state.history]
        db.commit()

        complaint_id = state.form.complaint_id
        if complaint_id:
            record = db.get(ComplaintRecord, complaint_id)
            if record is None:
                record = ComplaintRecord(
                    complaint_id=complaint_id,
                    session_id=state.session_id,
                    form={},
                    risk={},
                    history=[],
                )
                db.add(record)
            record.session_id = state.session_id
            record.form = state.form.model_dump(exclude_none=True)
            record.risk = state.risk.model_dump(exclude_none=True)
            record.history = [turn.model_dump() for turn in state.history]
            db.commit()
    finally:
        db.close()


def next_complaint_id() -> str:
    """Atomically mint a new, globally unique complaint ID via an
    auto-increment row insert — works the same way on Postgres and MySQL."""
    db = SessionLocal()
    try:
        counter_row = ComplaintIdCounter()
        db.add(counter_row)
        db.commit()
        db.refresh(counter_row)
        return f"CMP-{1000 + counter_row.id}"
    finally:
        db.close()


def reset_session(session_id: str) -> SessionState:
    db = SessionLocal()
    try:
        row = db.get(ComplaintSession, session_id)
        if row is None:
            row = ComplaintSession(session_id=session_id)
            db.add(row)
        row.form = {}
        row.risk = {}
        row.history = []
        db.commit()
        db.refresh(row)
        return _to_state(row)
    finally:
        db.close()


def get_complaint_by_id(complaint_id: str) -> SessionState | None:
    """Fetch a durable complaint record by complaint_id, with a legacy
    session-row fallback so deployed data is not lost during the migration."""
    db = SessionLocal()
    try:
        row = db.get(ComplaintRecord, complaint_id)
        if row is not None:
            return _to_state(row)

        # Backward-compatibility fallback for older session rows that already
        # contain complaint_id in their JSON form payload.
        for session_row in db.query(ComplaintSession).all():
            if (session_row.form or {}).get("complaint_id") == complaint_id:
                return _to_state(session_row)

        return None
    finally:
        db.close()

def find_possible_duplicates(form: dict, exclude_complaint_id: str | None = None) -> list[dict]:
    """Look for existing complaint records that plausibly describe the same
    incident as `form`. Match on batch_number + product_name when both are
    present (strong signal); otherwise fall back to batch_number alone.
    Returns a list of lightweight dicts (not full SessionState) so callers
    don't need to know the ComplaintRecord shape."""
    batch = (form.get("batch_number") or "").strip()
    product = (form.get("product_name") or "").strip()

    if not batch:
        return []

    db = SessionLocal()
    try:
        query = db.query(ComplaintRecord)
        if exclude_complaint_id:
            query = query.filter(ComplaintRecord.complaint_id != exclude_complaint_id)

        matches = []
        for row in query.all():
            row_batch = (row.form or {}).get("batch_number", "")
            row_product = (row.form or {}).get("product_name", "")

            if row_batch.strip().lower() != batch.lower():
                continue
            if product and row_product and row_product.strip().lower() != product.lower():
                continue

            matches.append({
                "complaint_id": row.complaint_id,
                "product_name": row_product,
                "batch_number": row_batch,
                "defect_type": (row.form or {}).get("defect_type"),
                "status": (row.form or {}).get("status"),
            })
        return matches
    finally:
        db.close()