"""GraphState — the single shared state dict threaded through the LangGraph pipeline."""

from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict, Literal

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
    last_turn_context: dict | None  # Structured context from prior turn (TurnContext as dict)

    # ── Hybrid Mode (Phase 8) ─────────────────────────────────────────────
    last_query: str | None                  # Previous user question for similarity comparison
    last_query_embedding: list[float] | None  # Embedding of previous question
    current_query_embedding: list[float] | None  # Embedding of current question
    semantic_similarity: float | None       # Cosine similarity between current and last query
    follow_up_type: Literal["refine", "replace", "new"] | None  # Classification result
    confidence_breakdown: dict | None       # {valid_json, valid_fields, matches_schema} scores

    # ── Auth / RBAC (set by query_service from current_user) ─────────────
    user_id: str | None          # UUID as str — authenticated user's ID; None if unauthenticated
    user_role: str | None        # "admin" | "manager" | "user"; None if unauthenticated
    resource_id: int | None      # Only set for "user" role; None for admin/manager/unauthenticated

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

    # ── QueryPlan Compiler (set by update_query_plan node) ─────────────
    filters: list  # FilterClause objects extracted by filter_extractor node
    query_plan: dict | None  # QueryPlan serialized as dict (follows Phase 6 pattern)
