import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.connectors.base_connector import QueryResult
from app.llm.graph.state import GraphState


def _base_state(**overrides) -> GraphState:
    state = {
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
        "result": None,
        "generated_sql": None,
        "retry_count": 0,
        "answer": None,
        "highlights": [],
        "suggested_followups": [],
        "explanation": None,
        "llm_provider": "domain_tool",
        "llm_model": "active_resources",
        "execution_id": None,
        "execution_time_ms": None,
        "error": None,
    }
    state.update(overrides)
    return state


@pytest.mark.asyncio
async def test_interpret_result_no_rows():
    from app.llm.graph.nodes.result_interpreter import interpret_result
    result = QueryResult(columns=[], column_types=[], rows=[], row_count=0,
                         execution_time_ms=5.0, truncated=False)
    state = _base_state(result=result)
    updates = await interpret_result(state)
    assert updates["answer"] is None
    assert updates["highlights"] == []


@pytest.mark.asyncio
async def test_interpret_result_with_rows():
    from app.llm.graph.nodes.result_interpreter import interpret_result
    from app.llm.agents.result_interpreter import InterpretationOutput
    result = QueryResult(
        columns=["Name"], column_types=["nvarchar"],
        rows=[["Alice"]], row_count=1,
        execution_time_ms=10.0, truncated=False,
    )
    mock_interp = InterpretationOutput(
        summary="1 active resource found.",
        highlights=["Alice"],
        suggested_followups=[],
    )
    state = _base_state(result=result)
    with patch("app.llm.graph.nodes.result_interpreter.ResultInterpreterAgent") as MockAgent:
        instance = AsyncMock()
        instance.interpret = AsyncMock(return_value=mock_interp)
        MockAgent.return_value = instance
        updates = await interpret_result(state)

    assert updates["answer"] == "1 active resource found."
    assert updates["highlights"] == ["Alice"]


@pytest.mark.asyncio
async def test_write_history_success(mock_db):
    from app.llm.graph.nodes.history_writer import write_history
    result = QueryResult(columns=["Name"], column_types=["nvarchar"],
                         rows=[["Alice"]], row_count=1,
                         execution_time_ms=12.0, truncated=False)
    state = _base_state(result=result, db=mock_db, answer="1 result found.")
    updates = await write_history(state)
    assert mock_db.add.called
    assert mock_db.flush.called


@pytest.mark.asyncio
async def test_write_history_error(mock_db):
    from app.llm.graph.nodes.history_writer import write_history
    state = _base_state(db=mock_db, result=None, error="Connection failed")
    updates = await write_history(state)
    assert mock_db.add.called
    call_arg = mock_db.add.call_args[0][0]
    assert call_arg.execution_status == "error"
    assert call_arg.error_message == "Connection failed"
