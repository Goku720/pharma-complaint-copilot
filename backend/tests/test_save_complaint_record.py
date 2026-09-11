from app.models import SessionState, ComplaintForm, RiskAssessment
from app.store import save_session
from app.db import SessionLocal
from app.db_models import ComplaintRecord


def test_save_session_persists_complaint_record_by_complaint_id():
    state = SessionState(
        session_id="test-session-unique-001",
        form=ComplaintForm(
            complaint_id="CMP-TEST-999",
            reported_by="QA Tester",
            customer_name="Test Customer",
            product_name="Test Product",
            defect_type="Discoloration",
            complaint_description="Sample complaint description",
            status="New",
            date_received="2026-09-10",
        ),
        risk=RiskAssessment(
            severity="Minor",
            regulatory_reportable="No",
            next_action="Route to QA",
            root_cause_hint="Packaging",
            capa_suggestion="Investigate",
            rationale="Reasoning",
        ),
        history=[],
    )

    save_session(state)

    db = SessionLocal()
    try:
        row = db.get(ComplaintRecord, "CMP-TEST-999")
        assert row is not None
        assert row.form["reported_by"] == "QA Tester"
    finally:
        db.close()
