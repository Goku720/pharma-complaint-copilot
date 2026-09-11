"""
Extracts raw text from an uploaded complaint document (PDF, or plain-text
email export) so it can be handed to the LangGraph agent as if the user had
pasted/typed it. The agent itself (via the log_complaint / edit_complaint
tools) does the actual field extraction and reasoning — this module just
gets clean text out of the file.
"""
from __future__ import annotations

import io
from pypdf import PdfReader


def extract_text_from_upload(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(content)
    if lower.endswith((".txt", ".eml", ".md")):
        return content.decode("utf-8", errors="ignore")
    # Fallback: try PDF magic bytes, else decode as text
    if content[:4] == b"%PDF":
        return _extract_pdf(content)
    return content.decode("utf-8", errors="ignore")


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages).strip()
