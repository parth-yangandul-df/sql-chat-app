import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm.graph.graph import get_compiled_graph, _build_graph
from app.llm.graph.state import GraphState
from app.connectors.base_connector import QueryResult


def _full_state(domain="resource", intent="active_resources", confidence=0.95) -> GraphState:
    return {
        "question": "show active resources",
        "connection_id": "00000000-0000-0000-0000-000000000001",
        "connector_type": "sqlserver",
        "connection_string": "dsn=test",
        "timeout_seconds": 30,
        "max_rows": 100,
        "db": None,
        "domain": domain,
        "intent": intent,
        "confidence": confidence,
        "params": {},
        "sql": None,
        "result": None,
        "generated_sql": None,
        "retry_count": 0,
        "answer": None,
        "highlights": [],
        "suggested_followups": [],
        "explanation": None,
        "llm_provider": None,
        "llm_model": None,
        "execution_id": None,
        "execution_time_ms": None,
        "error": None,
    }


def test_get_compiled_graph_returns_same_instance():
    g1 = get_compiled_graph()
    g2 = get_compiled_graph()
    assert g1 is g2


def test_graph_compiles_without_error():
    g = _build_graph()
    assert g is not None


@pytest.mark.asyncio
async def test_graph_domain_tool_path(mock_db, mock_query_result):
    """Full graph invocation via domain tool path with all nodes mocked."""
    from app.llm.agents.result_interpreter import InterpretationOutput

    mock_interp = InterpretationOutput(
        summary="2 active resources found.",
        highlights=["Alice", "Bob"],
        suggested_followups=[],
    )

    with (
        patch("app.llm.graph.nodes.intent_classifier.embed_text",
              AsyncMock(return_value=[0.1, 0.9, 0.1])),
        patch("app.llm.graph.nodes.intent_classifier.get_catalog_embeddings",
              return_value=[[0.1, 0.9, 0.1]] * 24),
        patch("app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded",
              AsyncMock()),
        patch("app.llm.graph.domains.base_domain.get_or_create_connector",
              AsyncMock(return_value=MagicMock(
                  execute_query=AsyncMock(return_value=mock_query_result)
              ))),
        patch("app.llm.graph.nodes.result_interpreter.ResultInterpreterAgent") as MockInterp,
        patch("app.llm.graph.nodes.history_writer.QueryExecution"),
    ):
        mock_db_local = MagicMock()
        mock_db_local.add = MagicMock()
        mock_db_local.flush = AsyncMock()

        inst = AsyncMock()
        inst.interpret = AsyncMock(return_value=mock_interp)
        MockInterp.return_value = inst

        g = _build_graph()
        initial_state = _full_state()
        initial_state["db"] = mock_db_local

        final_state = await g.ainvoke(initial_state)

    assert final_state["llm_provider"] == "domain_tool"
    assert final_state["answer"] == "2 active resources found."
    assert final_state["error"] is None


@pytest.mark.asyncio
async def test_graph_0_row_routes_to_llm_fallback(mock_db):
    """0-row domain result with no fallback_intent routes to llm_fallback."""
    from app.llm.agents.result_interpreter import InterpretationOutput

    empty_result = QueryResult(
        columns=[], column_types=[], rows=[], row_count=0,
        execution_time_ms=5.0, truncated=False,
    )
    nonempty_result = QueryResult(
        columns=["Name"], column_types=["nvarchar"],
        rows=[["from LLM"]], row_count=1,
        execution_time_ms=50.0, truncated=False,
    )
    mock_interp = InterpretationOutput(summary="LLM answered.", highlights=[], suggested_followups=[])

    with (
        patch("app.llm.graph.nodes.intent_classifier.embed_text",
              AsyncMock(return_value=[0.1, 0.9, 0.1])),
        patch("app.llm.graph.nodes.intent_classifier.get_catalog_embeddings",
              return_value=[[0.1, 0.9, 0.1]] * 24),
        patch("app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded",
              AsyncMock()),
        patch("app.llm.graph.domains.base_domain.get_or_create_connector",
              AsyncMock(return_value=MagicMock(
                  execute_query=AsyncMock(return_value=empty_result)
              ))),
        # Ensure no fallback_intent on any catalog entry for this test
        patch("app.llm.graph.nodes.fallback_intent._get_fallback_intent_name",
              return_value=None),
        patch("app.llm.graph.graph.llm_fallback",
              AsyncMock(return_value={
                  "sql": "SELECT 1", "result": nonempty_result,
                  "generated_sql": "SELECT 1", "retry_count": 0,
                  "llm_provider": "anthropic", "llm_model": "claude-3",
                  "explanation": "fallback", "error": None,
              })),
        patch("app.llm.graph.nodes.result_interpreter.ResultInterpreterAgent") as MockInterp,
        patch("app.llm.graph.nodes.history_writer.QueryExecution"),
    ):
        mock_db_local = MagicMock()
        mock_db_local.add = MagicMock()
        mock_db_local.flush = AsyncMock()
        inst = AsyncMock()
        inst.interpret = AsyncMock(return_value=mock_interp)
        MockInterp.return_value = inst

        g = _build_graph()
        initial_state = _full_state()
        initial_state["db"] = mock_db_local
        final_state = await g.ainvoke(initial_state)

    assert final_state["answer"] == "LLM answered."


# ---------------------------------------------------------------------------
# execute_nl_query() integration tests (Plan 05)
# ---------------------------------------------------------------------------

EXPECTED_RESPONSE_KEYS = {
    "id", "question", "generated_sql", "final_sql", "explanation",
    "columns", "column_types", "rows", "row_count", "execution_time_ms",
    "truncated", "summary", "highlights", "suggested_followups",
    "llm_provider", "llm_model", "retry_count", "turn_context",
    "topic_switch_detected",
}


def _make_final_state(mock_query_result) -> dict:
    """Build a final GraphState-shaped dict as ainvoke() would return."""
    return {
        "question": "show active resources",
        "connection_id": "00000000-0000-0000-0000-000000000001",
        "connector_type": "sqlserver",
        "connection_string": "dsn=test",
        "timeout_seconds": 30,
        "max_rows": 100,
        "db": None,
        "domain": "resource",
        "intent": "active_resources",
        "confidence": 0.95,
        "params": {},
        "sql": "SELECT * FROM Resource WHERE IsActive = 1",
        "result": mock_query_result,
        "generated_sql": None,
        "retry_count": 0,
        "explanation": None,
        "llm_provider": "domain_tool",
        "llm_model": "active_resources",
        "answer": "2 active resources found.",
        "highlights": ["Alice", "Bob"],
        "suggested_followups": ["Show billing rate for Alice?"],
        "execution_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "execution_time_ms": 12.5,
        "error": None,
    }


@pytest.mark.asyncio
async def test_execute_nl_query_response_keys(mock_db, mock_query_result):
    """execute_nl_query() must return exactly the original 17-key response dict."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    final_state = _make_final_state(mock_query_result)
    mock_compiled = MagicMock()
    mock_compiled.ainvoke = AsyncMock(return_value=final_state)

    mock_conn = MagicMock()
    mock_conn.connector_type = "sqlserver"
    mock_conn.max_query_timeout_seconds = 30
    mock_conn.max_rows = 100

    with (
        patch("app.services.query_service.get_compiled_graph", return_value=mock_compiled),
        patch("app.services.query_service.get_connection", AsyncMock(return_value=mock_conn)),
        patch("app.services.query_service.get_decrypted_connection_string", return_value="dsn=test"),
    ):
        from app.services.query_service import execute_nl_query
        result = await execute_nl_query(
            db=mock_db,
            connection_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            question="show active resources",
        )

    assert set(result.keys()) == EXPECTED_RESPONSE_KEYS


@pytest.mark.asyncio
async def test_execute_nl_query_domain_tool_provider(mock_db, mock_query_result):
    """Domain tool path sets llm_provider='domain_tool' and llm_model=intent_name."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    final_state = _make_final_state(mock_query_result)
    mock_compiled = MagicMock()
    mock_compiled.ainvoke = AsyncMock(return_value=final_state)

    mock_conn = MagicMock()
    mock_conn.connector_type = "sqlserver"
    mock_conn.max_query_timeout_seconds = 30
    mock_conn.max_rows = 100

    with (
        patch("app.services.query_service.get_compiled_graph", return_value=mock_compiled),
        patch("app.services.query_service.get_connection", AsyncMock(return_value=mock_conn)),
        patch("app.services.query_service.get_decrypted_connection_string", return_value="dsn=test"),
    ):
        from app.services.query_service import execute_nl_query
        result = await execute_nl_query(
            db=mock_db,
            connection_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            question="show active resources",
        )

    assert result["llm_provider"] == "domain_tool"
    assert result["llm_model"] == "active_resources"
    assert result["generated_sql"] is None
    assert result["explanation"] is None


@pytest.mark.asyncio
async def test_execute_nl_query_persists_turn_context(mock_db, mock_query_result):
    """execute_nl_query() persists the final turn_context onto the saved execution row."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch

    final_state = _make_final_state(mock_query_result)
    mock_compiled = MagicMock()
    mock_compiled.ainvoke = AsyncMock(return_value=final_state)

    mock_conn = MagicMock()
    mock_conn.connector_type = "sqlserver"
    mock_conn.max_query_timeout_seconds = 30
    mock_conn.max_rows = 100

    execution = MagicMock()
    mock_db.get = AsyncMock(return_value=execution)

    with (
        patch("app.services.query_service.get_compiled_graph", return_value=mock_compiled),
        patch("app.services.query_service.get_connection", AsyncMock(return_value=mock_conn)),
        patch("app.services.query_service.get_decrypted_connection_string", return_value="dsn=test"),
    ):
        from app.services.query_service import execute_nl_query
        result = await execute_nl_query(
            db=mock_db,
            connection_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            question="show active resources",
        )

    assert execution.turn_context == result["turn_context"]
    assert execution.turn_context["question"] == "show active resources"


@pytest.mark.asyncio
async def test_execute_nl_query_error_raises(mock_db, mock_query_result):
    """execute_nl_query() raises AppError when graph returns error with no result."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.core.exceptions import AppError

    error_state = {
        **_make_final_state(mock_query_result),
        "result": None,
        "error": "LLM fallback failed to generate SQL",
    }

    mock_compiled = MagicMock()
    mock_compiled.ainvoke = AsyncMock(return_value=error_state)

    mock_conn = MagicMock()
    mock_conn.connector_type = "sqlserver"
    mock_conn.max_query_timeout_seconds = 30
    mock_conn.max_rows = 100

    with (
        patch("app.services.query_service.get_compiled_graph", return_value=mock_compiled),
        patch("app.services.query_service.get_connection", AsyncMock(return_value=mock_conn)),
        patch("app.services.query_service.get_decrypted_connection_string", return_value="dsn=test"),
    ):
        from app.services.query_service import execute_nl_query
        with pytest.raises(AppError):
            await execute_nl_query(
                db=mock_db,
                connection_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                question="show active resources",
            )
