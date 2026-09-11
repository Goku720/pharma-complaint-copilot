"""
The AIVOA Copilot agent.

Implements the three mandatory tools as native Anthropic tool-calling
functions, orchestrated by a small LangGraph graph:

  1. log_complaint   -> creates a brand-new complaint record
  2. edit_complaint  -> patches specific fields on the in-progress complaint
  3. assess_risk     -> fills/updates the AI Copilot risk-assessment panel

Document extraction (PDF/email) is handled upstream in main.py: the raw
extracted text is fed into this same graph as a user turn, so the model
naturally calls log_complaint (or edit_complaint, on a follow-up) exactly as
it would for a typed prompt. That's what lets "even after extraction, you
can still modify the complaint using natural language" work for free.

RAG grounding: before every LLM call, app/rag.py retrieves the most relevant
regulatory clauses (ICH Q9(R1), ICH Q10, ICH Q7, 21 CFR 211, WHO GMP — see
regulatory_docs/) for the complaint at hand from Postgres/pgvector and
injects them into the system prompt, so severity/CAPA/root-cause reasoning
in assess_risk is grounded in actual regulatory text instead of the model's
own recall. If the corpus hasn't been ingested yet (or DATABASE_URL isn't
Postgres), retrieval just returns nothing and the agent falls back to its
own reasoning — nothing breaks.

Duplicate detection: when log_complaint is called for a genuinely new
complaint (no complaint_id on the form yet), we check
store.find_possible_duplicates() against batch_number (and, if present,
product_name) of every other complaint on file. This is a simple exact-match
heuristic, not fuzzy/semantic matching — see store.py.

If a possible duplicate is found, NO complaint_id is minted and NOTHING is
persisted as a new ComplaintRecord — the form is held in a "Pending Review -
Possible Duplicate" state and the model is instructed to ask the user to
confirm. Only when the model calls log_complaint again with
duplicate_confirmed=true does an ID get minted and the record become
durable. This prevents the record from being saved to the database even
though the user was told it was being held for confirmation.
"""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Annotated, TypedDict

from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app import store, rag
from app.models import ChatTurn, SessionState

MODEL_NAME = "openai/gpt-oss-120b"

_COMPLAINT_FIELD_PROPS = {
    "customer_name": {"type": "string", "description": "Reporting customer / pharmacy / distributor name"},
    "contact_info": {"type": "string", "description": "Phone, email, or address if given"},
    "product_name": {"type": "string"},
    "product_strength": {"type": "string", "description": "e.g. '500 mg', 'IP/BP grade'"},
    "batch_number": {"type": "string"},
    "manufacturing_date": {"type": "string", "description": "As stated, or ISO date if unambiguous"},
    "expiry_date": {"type": "string"},
    "defect_type": {"type": "string", "description": "e.g. discoloration, contamination, packaging defect, short-fill"},
    "complaint_description": {"type": "string", "description": "1-3 sentence plain description of what was reported"},
    "affected_quantity": {"type": "string", "description": "Numeric quantity, e.g. '48' or '50'"},
    "unit": {"type": "string", "description": "e.g. capsules, kg, HDPE drums"},
    "reported_by": {"type": "string"},
    "date_received": {"type": "string"},
}

LOG_COMPLAINT_TOOL = {
    "name": "log_complaint",
    "description": (
        "Create a brand-new complaint record, filling every field you can confidently extract or "
        "infer from the user's message or an extracted document. Use this when there is no complaint "
        "in progress yet, or the user is clearly starting a new, unrelated complaint. Do not invent "
        "values you were not given — omit a field rather than guess. If a prior call to this tool "
        "reported a possible duplicate and the user has now confirmed this is a distinct issue, call "
        "it again with the same fields plus duplicate_confirmed=true."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            **_COMPLAINT_FIELD_PROPS,
            "duplicate_confirmed": {
                "type": "boolean",
                "description": (
                    "Set to true ONLY when the user has explicitly confirmed, after being warned "
                    "about a possible duplicate, that this is a distinct issue and should be logged "
                    "as a new complaint anyway. Omit or leave false on the first attempt."
                ),
            },
        },
    },
}

EDIT_COMPLAINT_TOOL = {
    "name": "edit_complaint",
    "description": (
        "Patch one or more fields on the complaint that is already in progress, leaving every other "
        "field exactly as it is. Use this whenever the user corrects or adds a detail to an existing "
        "complaint (e.g. 'sorry, the batch number is X and affected quantity is Y'). Only include the "
        "fields that changed."
    ),
    "input_schema": {"type": "object", "properties": _COMPLAINT_FIELD_PROPS},
}

ASSESS_RISK_TOOL = {
    "name": "assess_risk",
    "description": (
        "Set or update the AI Copilot's risk assessment for the current complaint. Ground your "
        "reasoning in the retrieved regulatory guidance provided in the prompt when it's relevant — "
        "cite the source document in regulatory_basis when you rely on it directly. Call this right "
        "after log_complaint whenever you create a new complaint, and again after edit_complaint "
        "whenever a change could plausibly affect severity, reportability, or next action."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": ["Minor", "Major", "Critical"]},
            "regulatory_reportable": {"type": "string", "enum": ["Yes", "No", "Uncertain"]},
            "next_action": {"type": "string", "description": "e.g. 'Route to QA investigation and issue replacement'"},
            "root_cause_hint": {"type": "string", "description": "Most likely root-cause category, briefly"},
            "capa_suggestion": {"type": "string", "description": "Short CAPA (corrective/preventive action) suggestion"},
            "rationale": {"type": "string", "description": "1-2 sentence reasoning behind the severity/action chosen"},
            "regulatory_basis": {
                "type": "string",
                "description": "Which retrieved guidance document/clause this is grounded in, if any (e.g. 'ICH Q9(R1)', '21 CFR 211.198'). Omit if you didn't rely on the retrieved context.",
            },
        },
    },
}

VIEW_COMPLAINT_TOOL = {
    "name": "view_complaint",
    "description": (
        "Fetch an earlier complaint record from the database by complaint_id and load its "
        "stored form and risk fields into the current session for follow-up editing or review."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "complaint_id": {"type": "string", "description": "The complaint ID that was previously assigned to the complaint record."},
        },
        "required": ["complaint_id"],
    },
}

TOOLS = [LOG_COMPLAINT_TOOL, EDIT_COMPLAINT_TOOL, ASSESS_RISK_TOOL, VIEW_COMPLAINT_TOOL]

SYSTEM_PROMPT = """You are AIVOA Copilot, an AI assistant embedded next to a pharmaceutical Quality \
Management System's "Log Customer Complaint" form. A human quality officer talks to you in plain \
language; you fill in and correct the form on their behalf, and you independently assess quality risk.

Rules:
- If the current form is empty (or the user is clearly describing a brand-new, unrelated complaint), \
call log_complaint with every field you can confidently extract, then call assess_risk with your \
own reasoning about severity, regulatory reportability, next action, likely root cause, and a CAPA \
suggestion.
- If the user asks to view or load an existing complaint record by complaint_id, call view_complaint \
with the supplied complaint_id before continuing the conversation, and then optionally call \
edit_complaint or assess_risk if the user asks to revise or reassess that loaded complaint.
- If a complaint is already in progress and the user is correcting or adding a detail, call \
edit_complaint with ONLY the fields that changed. Then call assess_risk again ONLY if the change \
could plausibly affect severity, reportability, or next action (e.g. a much larger affected \
quantity, a different defect type) — trivial edits like a contact number don't need a new risk call.
-  When calling assess_risk, ground your severity/next-action/CAPA reasoning in the "Relevant \
regulatory guidance" section below if it's relevant to this complaint, and name the source document \
in regulatory_basis (e.g. "ICH Q7", "21 CFR 211.198") — a short document name only, never the \
internal "[source — excerpt N]" labels those passages are tagged with in the prompt below; those \
labels are for your reference only and must never appear in rationale or regulatory_basis. If \
nothing retrieved is relevant, reason from general GMP principles instead and leave regulatory_basis \
out.
- If log_complaint reports a possible duplicate, no ID has been assigned and nothing has been saved \
as a new complaint yet — ask the user to confirm whether this is a distinct issue. If they confirm \
it is distinct, call log_complaint again with the same fields plus duplicate_confirmed=true to \
finalize and get a complaint ID. If they say it's the same issue, do not log a new complaint — offer \
to view_complaint the existing record instead.
- Never fabricate a batch number, date, or quantity you were not given.
- After your tool calls are done, reply to the user in ONE short, natural sentence confirming what \
you filled in or changed. Do not restate the entire form back to them.
- If the user's message doesn't describe a complaint or a correction at all (e.g. a greeting or a \
question about the tool), just reply conversationally without calling any tools.

Current form state (JSON): {form_json}
Current risk assessment (JSON): {risk_json}

Relevant regulatory guidance (retrieved for this complaint, may be empty):
{regulatory_context}
"""


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    form: dict
    risk: dict
    tool_calls_made: list[str]


def _llm():
    return ChatGroq(
        model=MODEL_NAME,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
    ).bind_tools(TOOLS)


def _retrieval_query(state: GraphState, latest_user_text: str) -> str:
    """Builds the RAG query from whatever we already know about the
    complaint plus the newest message, so retrieval improves as the form
    fills in."""
    form = state["form"]
    parts = [
        form.get("product_name", ""),
        form.get("defect_type", ""),
        form.get("complaint_description", ""),
        latest_user_text,
    ]
    return " ".join(p for p in parts if p).strip()


def _agent_node(state: GraphState):
    latest_user_text = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            latest_user_text = msg.content
            break

    query = _retrieval_query(state, latest_user_text)
    retrieved = rag.retrieve(query, k=4) if query else []
    regulatory_context = rag.format_for_prompt(retrieved) or "(none retrieved — corpus may be empty, or nothing relevant matched)"

    system = SystemMessage(
        content=SYSTEM_PROMPT.format(
            form_json=json.dumps(state["form"], ensure_ascii=False),
            risk_json=json.dumps(state["risk"], ensure_ascii=False),
            regulatory_context=regulatory_context,
        )
    )
    response = _llm().invoke([system] + state["messages"])
    return {"messages": [response]}


def _clean(args: dict) -> dict:
    return {k: v for k, v in args.items() if v not in (None, "")}


def _apply_tools_node(state: GraphState):
    last = state["messages"][-1]
    form_updates: dict = {}
    risk_updates: dict = {}
    tool_msgs = []
    names_called: list[str] = []

    for call in last.tool_calls:
        name, args, call_id = call["name"], call["args"], call["id"]
        names_called.append(name)

        if name == "log_complaint":
            args = dict(args or {})
            duplicate_confirmed = bool(args.pop("duplicate_confirmed", False))
            new_form = _clean(args)

            existing_id = state["form"].get("complaint_id")
            # Only check for duplicates when this is a genuinely new complaint
            # (no ID assigned yet on the in-progress form).
            duplicates = [] if existing_id else store.find_possible_duplicates(new_form)

            if duplicates and not duplicate_confirmed:
                # Hold off: do NOT mint an ID and do NOT let this become a
                # persisted ComplaintRecord (store.save_session only mirrors
                # into ComplaintRecord when complaint_id is set) until the
                # user explicitly confirms it's a distinct issue.
                new_form["complaint_id"] = None
                new_form["status"] = "Pending Review - Possible Duplicate"
                new_form.setdefault("date_received", date.today().isoformat())
                form_updates = new_form

                dup_summary = "; ".join(
                    f"{d['complaint_id']} ({d['product_name']}, batch {d['batch_number']}, status {d['status']})"
                    for d in duplicates
                )
                tool_msgs.append(ToolMessage(
                    content=(
                        f"Held off — possible duplicate(s) found for this batch: {dup_summary}. "
                        f"No complaint ID has been assigned and nothing has been saved as a new "
                        f"record yet. Ask the user to confirm whether this is a distinct issue; if "
                        f"they confirm, call log_complaint again with duplicate_confirmed=true to "
                        f"finalize."
                    ),
                    tool_call_id=call_id,
                ))
            else:
                new_form["complaint_id"] = existing_id or store.next_complaint_id()
                new_form["status"] = state["form"].get("status") or "New"
                new_form.setdefault("date_received", date.today().isoformat())
                form_updates = new_form
                tool_msgs.append(ToolMessage(content="Logged new complaint into the form.", tool_call_id=call_id))

        elif name == "edit_complaint":
            form_updates.update(_clean(args))
            tool_msgs.append(ToolMessage(content="Updated the specified complaint fields.", tool_call_id=call_id))

        elif name == "assess_risk":
            risk_updates.update(_clean(args))
            tool_msgs.append(ToolMessage(content="Updated the AI risk assessment.", tool_call_id=call_id))

        elif name == "view_complaint":
            complaint_id = (args or {}).get("complaint_id")
            if not complaint_id:
                tool_msgs.append(ToolMessage(content="Missing complaint_id for view_complaint.", tool_call_id=call_id))
                continue

            fetched = store.get_complaint_by_id(complaint_id)
            if fetched is None:
                # Do not mutate the active form/risk state if the complaint is missing.
                tool_msgs.append(ToolMessage(content=f"Complaint {complaint_id} was not found.", tool_call_id=call_id))
                continue

            # Load the stored form and risk payloads into the active state so the
            # graph can continue editing, assessing or replying from the prior
            # record rather than only the current in-memory session.
            form_updates = fetched.form.model_dump(exclude_none=True)
            risk_updates = fetched.risk.model_dump(exclude_none=True)
            tool_msgs.append(
                ToolMessage(
                    content=f"Loaded complaint {complaint_id} from storage for review/editing.",
                    tool_call_id=call_id,
                )
            )

        else:
            tool_msgs.append(ToolMessage(content=f"Unknown tool {name}", tool_call_id=call_id))

    return {
        "messages": tool_msgs,
        "form": {**state["form"], **form_updates},
        "risk": {**state["risk"], **risk_updates},
        "tool_calls_made": state.get("tool_calls_made", []) + names_called,
    }


def _route(state: GraphState):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "apply_tools"
    return END


def _build_graph():
    g = StateGraph(GraphState)
    g.add_node("agent", _agent_node)
    g.add_node("apply_tools", _apply_tools_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", _route, {"apply_tools": "apply_tools", END: END})
    g.add_edge("apply_tools", "agent")
    return g.compile()


_GRAPH = _build_graph()


def _history_messages(history: list[ChatTurn], limit: int = 8):
    msgs = []
    for turn in history[-limit:]:
        if turn.role == "user":
            msgs.append(HumanMessage(content=turn.content))
        else:
            msgs.append(AIMessage(content=turn.content))
    return msgs


def run_agent_turn(state: SessionState, user_text: str):
    """Runs one full agent turn (may involve several tool calls) and returns
    (reply_text, updated_form_dict, updated_risk_dict, tool_names_called)."""
    initial: GraphState = {
        "messages": _history_messages(state.history) + [HumanMessage(content=user_text)],
        "form": state.form.model_dump(exclude_none=True),
        "risk": state.risk.model_dump(exclude_none=True),
        "tool_calls_made": [],
    }
    result = _GRAPH.invoke(initial, config={"recursion_limit": 10})

    final_reply = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
            final_reply = msg.content.strip()
            break

    return final_reply, result["form"], result["risk"], result["tool_calls_made"]