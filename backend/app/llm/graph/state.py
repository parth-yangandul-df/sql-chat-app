"""GraphState — the single shared state dict threaded through the LangGraph pipeline."""

from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base_connector import QueryResult


class GraphState(TypedDict):
    # ── Inputs ──────────────────────────────────────────────────────────────
    question: str
    connection_id: str           # UUID as str
    connector_type: str
    connection_string: str
    timeout_seconds: int
    max_rows: int
    db: AsyncSession             # SQLAlchemy async session (not serialized)
    session_id: str | None       # UUID as str — chat thread identifier
    conversation_history: list[dict]  # [{role: "user"|"assistant", content: str}, ...]

    # ── Classification (set by classify_intent) ──────────────────────────
    domain: str | None           # "resource" | "client" | "project" | "timesheet"
    intent: str | None           # e.g. "active_resources"
    confidence: float
    params: dict[str, Any]       # extracted parameters (skill, dates, names)

    # ── Execution (set by run_domain_tool or llm_fallback) ───────────────
    sql: str | None              # final executed SQL
    result: QueryResult | None
    generated_sql: str | None    # LLM path only; None for domain tool path
    retry_count: int
    explanation: str | None      # LLM path only; None for domain tool path
    llm_provider: str | None     # "domain_tool" for domain path
    llm_model: str | None        # intent_name for domain path

    # ── Interpretation (set by interpret_result) ─────────────────────────
    answer: str | None
    highlights: list[str]
    suggested_followups: list[str]

    # ── History (set by write_history) ───────────────────────────────────
    execution_id: Any            # UUID of saved QueryExecution record
    execution_time_ms: float | None

    # ── Error propagation ────────────────────────────────────────────────
    error: str | None
