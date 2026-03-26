"""llm_fallback node — reuses existing LLM pipeline agents unchanged.

Called when intent classifier confidence < threshold.
Mirrors the logic in query_service.execute_nl_query() exactly.
"""

import uuid
from typing import Any

from app.connectors.connector_registry import get_or_create_connector
from app.llm.agents.error_handler import ErrorHandlerAgent
from app.llm.agents.query_composer import QueryComposerAgent
from app.llm.agents.sql_validator import SQLValidatorAgent, ValidationStatus
from app.llm.graph.state import GraphState
from app.llm.router import route
from app.semantic.context_builder import build_context


async def llm_fallback(state: GraphState) -> dict[str, Any]:
    """Full LLM SQL generation pipeline as a LangGraph node."""
    question = state["question"]
    connection_id = uuid.UUID(state["connection_id"])
    db = state["db"]

    from app.services.connection_service import get_connection
    conn = await get_connection(db, connection_id)

    context = await build_context(db, connection_id, question, dialect=conn.connector_type)
    provider, llm_config = route(question)

    composer = QueryComposerAgent(provider, llm_config)
    composer_output = await composer.compose(question, context.prompt_context)
    generated_sql = composer_output.generated_sql

    if not generated_sql:
        return {
            "error": "LLM fallback failed to generate SQL",
            "llm_provider": provider.provider_type.value,
            "llm_model": llm_config.model,
        }

    schema_tables = {
        lt.table.table_name.upper(): [c.column_name.upper() for c in lt.columns]
        for lt in context.tables
    }
    validator = SQLValidatorAgent()
    validation = await validator.validate(generated_sql, schema_tables)

    final_sql = generated_sql
    retry_count = 0

    if validation.status != ValidationStatus.VALID:
        error_handler = ErrorHandlerAgent(provider, llm_config)
        previous_attempts = [generated_sql]
        while validation.status != ValidationStatus.VALID and retry_count < 3:
            retry_count += 1
            resolution = await error_handler.handle_error(
                question=question,
                failed_sql=final_sql,
                error_message="; ".join(validation.issues),
                schema_context=context.prompt_context,
                attempt_number=retry_count,
                previous_attempts=previous_attempts,
            )
            if not resolution.should_retry or not resolution.corrected_sql:
                return {
                    "error": f"SQL validation failed: {'; '.join(validation.issues)}",
                    "llm_provider": provider.provider_type.value,
                    "llm_model": llm_config.model,
                    "generated_sql": generated_sql,
                    "retry_count": retry_count,
                }
            final_sql = resolution.corrected_sql
            previous_attempts.append(final_sql)
            validation = await validator.validate(final_sql, schema_tables)

    from app.services.connection_service import get_decrypted_connection_string
    connection_string = get_decrypted_connection_string(conn)
    connector = await get_or_create_connector(
        state["connection_id"], conn.connector_type, connection_string
    )
    try:
        result = await connector.execute_query(
            final_sql,
            timeout_seconds=state.get("timeout_seconds", 30),
            max_rows=state.get("max_rows", 1000),
        )
    except Exception as e:
        return {
            "sql": final_sql,
            "generated_sql": generated_sql,
            "retry_count": retry_count,
            "result": None,
            "error": str(e),
            "llm_provider": provider.provider_type.value,
            "llm_model": llm_config.model,
            "explanation": composer_output.explanation,
        }

    return {
        "sql": final_sql,
        "generated_sql": generated_sql,
        "result": result,
        "retry_count": retry_count,
        "error": None,
        "llm_provider": provider.provider_type.value,
        "llm_model": llm_config.model,
        "explanation": composer_output.explanation,
    }
