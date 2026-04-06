"""Query Service — orchestrates the full NL → SQL → results pipeline."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base_connector import QueryResult
from app.connectors.connector_registry import get_or_create_connector
from app.core.exceptions import AppError, SQLSafetyError
from app.db.models.chat_session import ChatSession
from app.db.models.query_history import QueryExecution
from app.db.models.user import User
from app.llm.agents.error_handler import ErrorHandlerAgent
from app.llm.agents.query_composer import QueryComposerAgent
from app.llm.agents.result_interpreter import ResultInterpreterAgent
from app.llm.agents.sql_validator import SQLValidatorAgent, ValidationStatus
from app.llm.graph.graph import get_compiled_graph
from app.llm.graph.nodes.intent_classifier import _is_topic_switch
from app.llm.graph.query_plan import QueryPlan
from app.llm.graph.state import GraphState
from app.llm.router import route
from app.semantic.context_builder import build_context
from app.services.connection_service import get_connection, get_decrypted_connection_string
from app.utils.sql_sanitizer import check_sql_safety

logger = logging.getLogger(__name__)


async def execute_nl_query(
    db: AsyncSession,
    connection_id: uuid.UUID,
    question: str,
    session_id: uuid.UUID | None = None,
    conversation_history: list[dict] | None = None,
    current_user: User | None = None,
    last_turn_context: dict | None = None,
    clear_context: bool = False,
) -> dict:
    """Full pipeline: NL question → LangGraph → domain tool or LLM fallback → results.

    Delegates to the compiled LangGraph pipeline. Returns the same response
    dict shape as the original pipeline for API compatibility.

    current_user is optional to preserve backward compatibility with unauthenticated
    calls. When provided, user_id, user_role, and resource_id are threaded into
    GraphState for RBAC enforcement within the pipeline.
    """
    conn = await get_connection(db, connection_id)
    connection_string = get_decrypted_connection_string(conn)

    # Honor explicit clear_context flag
    effective_context = None if clear_context else last_turn_context

    initial_state: GraphState = {
        "question": question,
        "connection_id": str(connection_id),
        "connector_type": conn.connector_type,
        "connection_string": connection_string,
        "timeout_seconds": conn.max_query_timeout_seconds,
        "max_rows": conn.max_rows,
        "db": db,
        "session_id": str(session_id) if session_id else None,
        "conversation_history": conversation_history or [],
        "last_turn_context": effective_context,
        # Auth / RBAC — populated from the authenticated user when available
        "user_id": str(current_user.id) if current_user else None,
        "user_role": current_user.role if current_user else None,
        "resource_id": current_user.resource_id if current_user else None,
        # Classification defaults
        "domain": None,
        "intent": None,
        "confidence": 0.0,
        "params": {},
        # Execution defaults
        "sql": None,
        "result": None,
        "generated_sql": None,
        "retry_count": 0,
        "explanation": None,
        "llm_provider": None,
        "llm_model": None,
        # Interpretation defaults
        "answer": None,
        "highlights": [],
        "suggested_followups": [],
        # History defaults
        "execution_id": None,
        "execution_time_ms": None,
        # Error propagation
        "error": None,
        # QueryPlan compiler
        "filters": [],
        "query_plan": None,
    }

    final_state = await get_compiled_graph().ainvoke(initial_state)

    # Topic switch detection: clear context when user changes subject
    topic_switch_detected = False
    if effective_context and not clear_context:
        current_domain = final_state.get("domain")
        current_intent = final_state.get("intent")
        if _is_topic_switch(current_domain, current_intent, effective_context):
            topic_switch_detected = True
            logger.info(
                "query: topic switch detected — domain %s→%s, intent %s→%s",
                effective_context.get("domain"), current_domain,
                effective_context.get("intent"), current_intent,
            )

    if final_state.get("error") and final_state.get("result") is None:
        raise AppError(final_state["error"], status_code=422)

    # Auto-set session title from first question (if session has default title)
    if session_id:
        session = await db.get(ChatSession, session_id)
        if session and session.title == "New Chat":
            session.title = question[:100].strip()
            session.updated_at = datetime.now(timezone.utc)
            await db.flush()
        elif session:
            session.updated_at = datetime.now(timezone.utc)
            await db.flush()

    result: QueryResult = final_state["result"]

    # Determine turn_context: None if topic switch or no valid result
    if topic_switch_detected:
        turn_context = None
    elif final_state.get("intent") and final_state.get("domain"):
        final_params = final_state.get("params") or {}
        # Always store the base (original) SQL, not the refinement-wrapped SQL.
        # When _prior_sql is present, final_state["sql"] holds the refinement
        # wrapper (e.g. "SELECT prev.* FROM (base) AS prev JOIN ... WHERE ... LIKE ?")
        # which accumulates parameter markers on chained refinements.
        # Storing the base SQL ensures subsequent refinements always start clean.
        query_plan_dict = final_state.get("query_plan")
        if query_plan_dict:
            try:
                plan = QueryPlan.from_untrusted_dict(query_plan_dict)
                base_sql = plan.base_intent_sql
            except Exception:
                base_sql = final_params.get("_prior_sql") or final_state.get("sql") or ""
        else:
            base_sql = final_params.get("_prior_sql") or final_state.get("sql") or ""
        turn_context = {
            "intent": final_state.get("intent"),
            "domain": final_state.get("domain"),
            "params": final_params,
            "columns": final_state["result"].columns if final_state.get("result") else [],
            "sql": base_sql,
            "query_plan": final_state.get("query_plan"),
            "question": question,  # Store for semantic follow-up detection
        }
    else:
        turn_context = None

    return {
        "id": final_state.get("execution_id"),
        "question": question,
        "generated_sql": final_state.get("generated_sql"),
        "final_sql": final_state.get("sql"),
        "explanation": final_state.get("explanation"),
        "columns": result.columns,
        "column_types": result.column_types,
        "rows": _serialize_rows(result.rows),
        "row_count": result.row_count,
        "execution_time_ms": result.execution_time_ms,
        "truncated": result.truncated,
        "summary": final_state.get("answer"),
        "highlights": final_state.get("highlights", []),
        "suggested_followups": final_state.get("suggested_followups", []),
        "llm_provider": final_state.get("llm_provider"),
        "llm_model": final_state.get("llm_model"),
        "retry_count": final_state.get("retry_count", 0),
        "turn_context": turn_context,
        "topic_switch_detected": topic_switch_detected,
    }


async def generate_sql_only(
    db: AsyncSession,
    connection_id: uuid.UUID,
    question: str,
) -> dict:
    """Generate SQL without executing it."""
    conn = await get_connection(db, connection_id)
    context = await build_context(db, connection_id, question, dialect=conn.connector_type)
    provider, llm_config = route(question)
    composer = QueryComposerAgent(provider, llm_config)
    output = await composer.compose(question, context.prompt_context)

    return {
        "generated_sql": output.generated_sql,
        "explanation": output.explanation,
        "confidence": output.confidence,
        "tables_used": output.tables_used,
        "assumptions": output.assumptions,
    }


async def execute_raw_sql(
    db: AsyncSession,
    connection_id: uuid.UUID,
    sql: str,
    original_question: str | None = None,
) -> dict:
    """Execute user-provided SQL directly (no LLM generation).

    Steps:
    1. Safety check (block DDL/DML)
    2. Execute query via connector
    3. Save to history

    No LLM retry on error — the user can fix the SQL manually.
    """
    # Step 1: Safety check
    safety_issues = check_sql_safety(sql)
    if safety_issues:
        raise SQLSafetyError("; ".join(safety_issues))

    conn = await get_connection(db, connection_id)
    connection_string = get_decrypted_connection_string(conn)

    # Step 2: Execute query
    connector = await get_or_create_connector(
        str(connection_id), conn.connector_type, connection_string
    )

    try:
        result = await connector.execute_query(
            sql,
            timeout_seconds=conn.max_query_timeout_seconds,
            max_rows=conn.max_rows,
        )
    except Exception as e:
        # Save failed execution to history
        execution = QueryExecution(
            connection_id=connection_id,
            natural_language=original_question or "(manual SQL)",
            generated_sql=None,
            final_sql=sql,
            execution_status="error",
            error_message=str(e),
            retry_count=0,
        )
        db.add(execution)
        await db.flush()
        raise AppError(f"Query execution failed: {e}") from e

    # Step 3: Interpret results (LLM summary + follow-ups)
    summary = None
    highlights = []
    followups = []
    llm_provider_name = "manual"
    llm_model_name = "manual"

    question_text = original_question or "(manual SQL)"

    if result.rows:
        try:
            provider, llm_config = route(question_text)
            interpreter = ResultInterpreterAgent(provider, llm_config)
            interpretation = await interpreter.interpret(
                question=question_text,
                sql=sql,
                columns=result.columns,
                rows=result.rows,
                row_count=result.row_count,
            )
            summary = interpretation.summary
            highlights = interpretation.highlights
            followups = interpretation.suggested_followups
            llm_provider_name = provider.provider_type.value
            llm_model_name = llm_config.model
        except Exception:
            pass  # Interpretation is best-effort; don't fail the query

    # Step 4: Save to history
    execution = QueryExecution(
        connection_id=connection_id,
        natural_language=question_text,
        generated_sql=None,
        final_sql=sql,
        execution_status="success",
        row_count=result.row_count,
        execution_time_ms=result.execution_time_ms,
        retry_count=0,
        result_summary=summary,
        llm_provider=llm_provider_name,
        llm_model=llm_model_name,
    )
    db.add(execution)
    await db.flush()

    return {
        "id": execution.id,
        "question": question_text,
        "generated_sql": sql,
        "final_sql": sql,
        "explanation": "User-provided SQL executed directly.",
        "columns": result.columns,
        "column_types": result.column_types,
        "rows": _serialize_rows(result.rows),
        "row_count": result.row_count,
        "execution_time_ms": result.execution_time_ms,
        "truncated": result.truncated,
        "summary": summary,
        "highlights": highlights,
        "suggested_followups": followups,
        "llm_provider": llm_provider_name,
        "llm_model": llm_model_name,
        "retry_count": 0,
    }


def _serialize_rows(rows: list[list]) -> list[list]:
    """Ensure all row values are JSON-serializable."""
    serialized = []
    for row in rows:
        serialized_row = []
        for val in row:
            if hasattr(val, "isoformat"):
                serialized_row.append(val.isoformat())
            elif isinstance(val, bytes):
                serialized_row.append(val.hex())
            else:
                serialized_row.append(val)
        serialized.append(serialized_row)
    return serialized
