"""
Data models for the QMS Complaint form and the AI Copilot risk assessment.

These are the API/agent-facing Pydantic schemas. The DB-facing shape (JSON
columns on complaint_sessions/complaint_records) is in db_models.py;
store.py converts between the two.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ComplaintForm(BaseModel):
    """The left-hand 'Log Customer Complaint' form."""

    complaint_id: Optional[str] = None
    status: str = "New"
    date_received: Optional[str] = None

    customer_name: Optional[str] = None
    contact_info: Optional[str] = None

    product_name: Optional[str] = None
    product_strength: Optional[str] = None
    batch_number: Optional[str] = None
    manufacturing_date: Optional[str] = None
    expiry_date: Optional[str] = None

    defect_type: Optional[str] = None
    complaint_description: Optional[str] = None
    affected_quantity: Optional[str] = None
    unit: Optional[str] = None

    reported_by: Optional[str] = None

    class Config:
        extra = "allow"


class RiskAssessment(BaseModel):
    """The right-hand 'AI Copilot Risk Assessment' panel."""

    severity: Optional[str] = None  # Minor / Major / Critical
    regulatory_reportable: Optional[str] = None  # Yes / No / Uncertain
    next_action: Optional[str] = None
    root_cause_hint: Optional[str] = None
    capa_suggestion: Optional[str] = None
    rationale: Optional[str] = None
    regulatory_basis: Optional[str] = None  # e.g. "ICH Q9(R1)", "21 CFR 211.198" — set when RAG grounding was used

    class Config:
        extra = "allow"


class ChatTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    form: ComplaintForm
    risk: RiskAssessment
    tool_calls: list[str] = Field(default_factory=list)
    completeness: dict | None = None
    duplicates: list[dict] = Field(default_factory=list)

class SessionState(BaseModel):
    session_id: str
    history: list[ChatTurn] = Field(default_factory=list)
    form: ComplaintForm = Field(default_factory=ComplaintForm)
    risk: RiskAssessment = Field(default_factory=RiskAssessment)