"""write_history node — saves QueryExecution record to the app database."""

import uuid
from typing import Any

from app.db.models.query_history import QueryExecution
from app.llm.graph.state import GraphState


async def write_history(state: GraphState) -> dict[str, Any]:
    """Persist the query execution record to the app database."""
    db = state["db"]
    result = state.get("result")
    error = state.get("error")

    execution = QueryExecution(
        connection_id=uuid.UUID(state["connection_id"]),
        natural_language=state["question"],
        generated_sql=state.get("generated_sql"),
        final_sql=state.get("sql"),
        execution_status="error" if error else "success",
        error_message=error,
        row_count=result.row_count if result else None,
        execution_time_ms=result.execution_time_ms if result else None,
        retry_count=state.get("retry_count", 0),
        result_summary=state.get("answer"),
        llm_provider=state.get("llm_provider"),
        llm_model=state.get("llm_model"),
    )
    db.add(execution)
    await db.flush()

    return {
        "execution_id": execution.id,
        "execution_time_ms": result.execution_time_ms if result else None,
    }
