from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import store
from app.agent import run_agent_turn
from app.db import init_db
from app.document_extraction import extract_text_from_upload
from app.models import ChatRequest, ChatResponse, ChatTurn, ComplaintForm, RiskAssessment, SessionState
from app.completeness import check_completeness


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="AIVOA Copilot - Pharma Complaint QMS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _finalize_turn(
    session: SessionState,
    user_message: str,
    reply: str,
    form_dict: dict,
    risk_dict: dict,
    tool_calls: list[str],
) -> ChatResponse:
    """Shared tail-end for /api/chat and /api/upload: compute completeness,
    check for possible duplicate complaints, append a "still missing" note,
    persist the session, and build the response. Keeping this in one place
    avoids the two routes drifting out of sync with each other."""
    completeness = check_completeness(form_dict)

    duplicates = store.find_possible_duplicates(
        form_dict, exclude_complaint_id=form_dict.get("complaint_id")
    )

    if completeness["missing_fields"] and "view_complaint" not in tool_calls:
        missing_readable = ", ".join(f.replace("_", " ") for f in completeness["missing_fields"])
        reply += f"\n\nStill missing: {missing_readable}."

    session.form = ComplaintForm(**form_dict)
    session.risk = RiskAssessment(**risk_dict)
    session.history.append(ChatTurn(role="user", content=user_message))
    session.history.append(ChatTurn(role="assistant", content=reply))
    store.save_session(session)

    return ChatResponse(
        reply=reply,
        form=session.form,
        risk=session.risk,
        tool_calls=tool_calls,
        completeness=completeness,
        duplicates=duplicates,
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/state/{session_id}")
def get_state(session_id: str):
    session = store.get_or_create_session(session_id)
    return {"form": session.form, "risk": session.risk, "history": session.history}


@app.get("/api/complaint/{complaint_id}")
def get_complaint(complaint_id: str):
    session = store.get_complaint_by_id(complaint_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return {
        "session_id": session.session_id,
        "form": session.form,
        "risk": session.risk,
        "completeness": check_completeness(session.form.model_dump()),
    }


@app.post("/api/reset/{session_id}")
def reset(session_id: str):
    session = store.reset_session(session_id)
    return {"form": session.form, "risk": session.risk, "history": session.history}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session = store.get_or_create_session(req.session_id)

    try:
        reply, form_dict, risk_dict, tool_calls = run_agent_turn(session, req.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    return _finalize_turn(session, req.message, reply, form_dict, risk_dict, tool_calls)


@app.post("/api/upload/{session_id}", response_model=ChatResponse)
async def upload_document(session_id: str, file: UploadFile = File(...)):
    session = store.get_or_create_session(session_id)
    content = await file.read()

    try:
        extracted_text = extract_text_from_upload(file.filename, content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read document: {exc}") from exc

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in that document.")

    prompt = (
        "The following text was extracted from an uploaded customer complaint document "
        f"(file: {file.filename}). Read it and log the complaint:\n\n---\n{extracted_text}\n---"
    )

    try:
        reply, form_dict, risk_dict, tool_calls = run_agent_turn(session, prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    user_history_note = f"[Uploaded document: {file.filename}]"
    return _finalize_turn(session, user_history_note, reply, form_dict, risk_dict, tool_calls)