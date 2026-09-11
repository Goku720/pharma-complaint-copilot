# AIVOA Copilot — Pharma Complaint QMS

An AI assistant embedded next to a pharmaceutical Quality Management System's "Log Customer Complaint" form. A quality officer describes a complaint in plain language (typed, or as an uploaded PDF/email/text document), and the agent fills in the structured complaint form and independently produces a risk assessment — grounded in real regulatory guidance rather than its own recall.

## What it does

- **Conversational complaint logging** — describe a complaint in natural language and the agent extracts customer, product, batch, defect, and quantity details into a structured form.
- **Follow-up edits** — correct or add details ("actually the batch number is X") and the agent patches only the changed fields, leaving the rest of the form untouched.
- **Document upload** — upload a PDF, `.eml`, or `.txt` complaint document; the extracted text is fed to the same agent so it logs (or edits) the complaint exactly as it would from typed input.
- **AI risk assessment** — the agent sets severity, regulatory reportability, next action, a likely root-cause hint, and a CAPA (corrective/preventive action) suggestion, with a short rationale.
- **RAG-grounded reasoning** — before each risk assessment, relevant clauses from ICH Q9(R1), ICH Q10, ICH Q7, 21 CFR 211 Subpart J, and WHO GMP are retrieved from Postgres/pgvector and injected into the prompt, so the agent cites (`regulatory_basis`) the guidance it relied on instead of inventing it. If the corpus hasn't been ingested, or the database isn't Postgres, retrieval quietly returns nothing and the agent falls back to its own reasoning.
- **Duplicate detection** — when logging a new complaint, the backend checks existing records for a matching batch number (and product name, if given). If a possible duplicate is found, no complaint ID is minted and nothing is persisted until the user explicitly confirms it's a distinct issue.
- **Completeness tracking** — every response reports which required fields are still missing and an overall completeness percentage.
- **Record lookup** — reload a previously logged complaint by ID to review or continue editing it.

## Architecture

```
frontend/  React 19 + Redux Toolkit (Vite) — complaint form, risk panel, chat assistant
backend/   FastAPI + LangGraph agent (Groq-hosted LLM) — tool-calling orchestration
           Postgres or MySQL for session/complaint storage
           Postgres + pgvector for regulatory-guidance RAG
```

**Agent loop (`backend/app/agent.py`).** A small LangGraph graph alternates between an `agent` node (calls the LLM with the current form/risk state and retrieved regulatory context) and an `apply_tools` node, until the model responds with no further tool calls. Four tools are exposed to the model:

| Tool | Purpose |
|---|---|
| `log_complaint` | Create a brand-new complaint record from confidently extracted fields |
| `edit_complaint` | Patch specific fields on the complaint already in progress |
| `assess_risk` | Set/update severity, reportability, next action, root cause, CAPA, and rationale |
| `view_complaint` | Load a previously saved complaint record by ID for review/editing |

Document extraction (`app/document_extraction.py`) happens upstream in `main.py`: raw text pulled from an uploaded file is handed to the agent as a normal user turn, so the same tool-calling logic handles it.

## Tech stack

**Backend:** FastAPI, LangGraph, LangChain (`langchain-groq`), Groq-hosted `openai/gpt-oss-120b`, SQLAlchemy, pgvector, chromadb (local ONNX MiniLM-L6-v2 embeddings only — no Chroma server), pypdf, Pydantic.

**Frontend:** React 19, Redux Toolkit, Vite.

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Postgres database with the `vector` extension available (recommended — enables RAG grounding and duplicate detection across the full feature set). MySQL is supported for core session/complaint storage, but the regulatory RAG feature is Postgres-only (see `backend/app/db.py`).
- A [Groq](https://console.groq.com/) API key

### Backend

```bash
cd backend
cat > .env <<'EOF'
GROQ_API_KEY=your-groq-api-key
DATABASE_URL=postgresql+psycopg2://qms_user:qms_pass@localhost:5432/qms_pharma
EOF
./run.sh
```

`run.sh` creates a virtualenv, installs `requirements.txt`, loads `.env`, and starts `uvicorn app.main:app --reload --port 8000`. Tables (and the `vector` extension, on Postgres) are created automatically on startup.

Environment variables:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Used by `ChatGroq` for the agent LLM |
| `DATABASE_URL` | No | `postgresql+psycopg2://qms_user:qms_pass@localhost:5432/qms_pharma` | `postgresql+psycopg2://...` or `mysql+pymysql://...` |

### (Optional) Ingest the regulatory corpus for RAG grounding

```bash
cd backend
mkdir -p regulatory_docs   # drop in ICH Q9(R1), ICH Q10, ICH Q7, 21 CFR 211 Subpart J, WHO GMP as PDF/.txt
python3 scripts/ingest_docs.py
```

Requires `DATABASE_URL` to point at Postgres (pgvector-backed). Ingestion is idempotent — re-run any time you add or replace a file. Without this step, `assess_risk` still works, just without citations to specific regulatory text.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173` with `/api` proxied to the backend on `http://localhost:8000` (see `vite.config.js`).

## API overview

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Send a chat message for a session; returns the agent's reply plus updated form, risk assessment, completeness, and any detected duplicates |
| `/api/upload/{session_id}` | POST | Upload a complaint document (PDF/.eml/.txt); extracted text is run through the same agent turn |
| `/api/state/{session_id}` | GET | Fetch the current form, risk assessment, and chat history for a session |
| `/api/complaint/{complaint_id}` | GET | Fetch a persisted complaint record by its assigned ID |
| `/api/reset/{session_id}` | POST | Reset a session's form/risk/history |
| `/api/health` | GET | Health check |

## Tests

```bash
cd backend
pytest
```

## Project layout

```
backend/
  app/
    agent.py               LangGraph agent, tool definitions, system prompt
    completeness.py         Required-field completeness check
    db.py / db_models.py    SQLAlchemy engine + models (Postgres/MySQL)
    document_extraction.py  PDF/text extraction from uploads
    main.py                 FastAPI routes
    models.py                Pydantic schemas (ComplaintForm, RiskAssessment, etc.)
    rag.py                  Regulatory-guidance retrieval (pgvector)
    store.py                Session/complaint persistence, duplicate lookup
  scripts/ingest_docs.py    Chunk + embed regulatory_docs/ into pgvector
  sample_docs/               Example complaint PDF for testing upload
  tests/
frontend/
  src/
    api/client.js           Backend API client
    components/              ComplaintForm, RiskAssessmentPanel, ChatAssistant
    store/                   Redux slices and thunks
```

## Notes

- Duplicate detection is a simple exact-match heuristic (batch number, optionally plus product name) — not fuzzy or semantic matching.
- The regulatory RAG layer stores embeddings in the same Postgres database as application state (via pgvector) rather than a separate vector store, so there's nothing extra to deploy or back up.
