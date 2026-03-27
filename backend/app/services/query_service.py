"""Query Service — orchestrates the full NL → SQL → results pipeline."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base_connector import QueryResult
from app.connectors.connector_registry import get_or_create_connector
from app.core.exceptions import AppError, SQLSafetyError
from app.db.models.chat_session import ChatSession
from app.db.models.query_history import QueryExecution
from app.llm.agents.error_handler import ErrorHandlerAgent
from app.llm.agents.query_composer import QueryComposerAgent
from app.llm.agents.result_interpreter import ResultInterpreterAgent
from app.llm.agents.sql_validator import SQLValidatorAgent, ValidationStatus
from app.llm.graph.graph import get_compiled_graph
from app.llm.graph.state import GraphState
from app.llm.router import route
from app.semantic.context_builder import build_context
from app.services.connection_service import get_connection, get_decrypted_connection_string
from app.utils.sql_sanitizer import check_sql_safety


async def execute_nl_query(
    db: AsyncSession,
    connection_id: uuid.UUID,
    question: str,
    session_id: uuid.UUID | None = None,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Full pipeline: NL question → LangGraph → domain tool or LLM fallback → results.

    Delegates to the compiled LangGraph pipeline. Returns the same response
    dict shape as the original pipeline for API compatibility.
    """
    conn = await get_connection(db, connection_id)
    connection_string = get_decrypted_connection_string(conn)

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
        "domain": None,
        "intent": None,
        "confidence": 0.0,
        "params": {},
        "sql": None,
        "result": None,
        "generated_sql": None,
        "retry_count": 0,
        "explanation": None,
        "llm_provider": None,
        "llm_model": None,
        "answer": None,
        "highlights": [],
        "suggested_followups": [],
        "execution_id": None,
        "execution_time_ms": None,
        "error": None,
    }

    final_state = await get_compiled_graph().ainvoke(initial_state)

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
