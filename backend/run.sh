#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -r requirements.txt
# Loads GROQ_API_KEY / QMS_MODEL / DATABASE_URL from .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
uvicorn app.main:app --reload --port 8000
