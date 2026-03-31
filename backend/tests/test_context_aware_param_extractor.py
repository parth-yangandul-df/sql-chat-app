"""Tests for context-aware extract_params: param inheritance + _refine_mode flag."""
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LAST_TURN = {
    "intent": "benched_resources",
    "domain": "resource",
    "params": {"project_name": "Alpha"},
    "columns": ["employeeid", "ResourceName", "EmailId", "TechCategoryName"],
    "sql": "SELECT DISTINCT r.employeeid FROM resources r WHERE r.IsActive = 0",
}


def _base_state(**overrides):
    state = {
        "question": "show active resources",
        "connection_id": "00000000-0000-0000-0000-000000000001",
        "connector_type": "sqlserver",
        "connection_string": "dsn=test",
        "timeout_seconds": 30,
        "max_rows": 100,
        "db": None,
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
        "conversation_history": [],
        "last_turn_context": None,
        "user_role": None,
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Param carry-forward tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_params_carry_forward_from_prior_turn():
    """Prior params {"project_name": "Alpha"} + question "Who knows Python?" → both present."""
    from app.llm.graph.nodes.param_extractor import extract_params

    state = _base_state(
        question="Who knows Python?",
        last_turn_context=_LAST_TURN,
        intent="benched_resources",  # same intent
    )
    result = await extract_params(state)
    params = result["params"]

    # Inherited from prior turn
    assert params.get("project_name") == "Alpha"
    # Extracted from current question
    assert params.get("skill") == "Python"


@pytest.mark.asyncio
async def test_new_params_override_prior():
    """Prior params {"skill": "Python"} + question "Filter by Java" → skill=Java (new wins)."""
    from app.llm.graph.nodes.param_extractor import extract_params

    prior = {**_LAST_TURN, "params": {"skill": "Python"}}
    state = _base_state(
        question="find resources with skill Java",
        last_turn_context=prior,
        intent="benched_resources",
    )
    result = await extract_params(state)
    params = result["params"]

    assert params.get("skill") == "Java"


@pytest.mark.asyncio
async def test_no_last_turn_context_unchanged_behavior():
    """No last_turn_context → existing behavior unchanged (params only from current question)."""
    from app.llm.graph.nodes.param_extractor import extract_params

    state = _base_state(
        question="find resources with skill Python",
        last_turn_context=None,
    )
    result = await extract_params(state)
    params = result["params"]

    assert params.get("skill") == "Python"
    assert "project_name" not in params


# ---------------------------------------------------------------------------
# _refine_mode flag tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refine_mode_set_when_same_intent_with_sql():
    """Prior context with sql + same intent → _refine_mode=True, _prior_sql set."""
    from app.llm.graph.nodes.param_extractor import extract_params

    state = _base_state(
        question="Which of these know Python?",
        last_turn_context=_LAST_TURN,
        intent="benched_resources",  # matches last_turn_context["intent"]
    )
    result = await extract_params(state)
    params = result["params"]

    assert params.get("_refine_mode") is True
    assert params.get("_prior_sql") == _LAST_TURN["sql"]
    assert params.get("_prior_columns") == _LAST_TURN["columns"]


@pytest.mark.asyncio
async def test_refine_mode_not_set_when_intent_differs():
    """Prior context with sql + DIFFERENT intent → _refine_mode NOT set."""
    from app.llm.graph.nodes.param_extractor import extract_params

    state = _base_state(
        question="Show active clients",
        last_turn_context=_LAST_TURN,
        intent="active_clients",  # different from last_turn_context["intent"] = "benched_resources"
    )
    result = await extract_params(state)
    params = result["params"]

    assert "_refine_mode" not in params
    assert "_prior_sql" not in params


@pytest.mark.asyncio
async def test_refine_mode_not_set_when_no_last_turn_context():
    """No last_turn_context → _refine_mode NOT set."""
    from app.llm.graph.nodes.param_extractor import extract_params

    state = _base_state(
        question="show active resources",
        last_turn_context=None,
        intent="active_resources",
    )
    result = await extract_params(state)
    params = result["params"]

    assert "_refine_mode" not in params
    assert "_prior_sql" not in params


@pytest.mark.asyncio
async def test_refine_mode_not_set_when_prior_sql_empty():
    """Prior context with empty sql → _refine_mode NOT set."""
    from app.llm.graph.nodes.param_extractor import extract_params

    no_sql_context = {**_LAST_TURN, "sql": ""}
    state = _base_state(
        question="Which of these know Python?",
        last_turn_context=no_sql_context,
        intent="benched_resources",
    )
    result = await extract_params(state)
    params = result["params"]

    assert "_refine_mode" not in params
    assert "_prior_sql" not in params


@pytest.mark.asyncio
async def test_internal_refine_keys_dont_leak_across_turns():
    """Internal _refine_mode, _prior_sql don't carry from one turn's inherited params to next."""
    from app.llm.graph.nodes.param_extractor import extract_params

    # Simulate a state where the inherited params (from a prior turn) already contain
    # _refine_mode keys — they should be stripped out before new extraction
    prior_with_refine_keys = {
        **_LAST_TURN,
        "params": {
            "skill": "Python",
            "_refine_mode": True,
            "_prior_sql": "SELECT old FROM table",
            "_prior_columns": ["col1"],
        },
    }
    state = _base_state(
        question="show active resources",
        last_turn_context=prior_with_refine_keys,
        intent="active_resources",  # different intent → no new _refine_mode
    )
    result = await extract_params(state)
    params = result["params"]

    # Inherited skill should still be there
    assert params.get("skill") == "Python"
    # But internal keys should NOT leak from prior turn's params
    assert "_refine_mode" not in params
    assert "_prior_sql" not in params
    assert "_prior_columns" not in params


@pytest.mark.asyncio
async def test_refine_mode_includes_columns():
    """_refine_mode=True also sets _prior_columns from last_turn_context."""
    from app.llm.graph.nodes.param_extractor import extract_params

    state = _base_state(
        question="Among them, who are billable?",
        last_turn_context=_LAST_TURN,
        intent="benched_resources",
    )
    result = await extract_params(state)
    params = result["params"]

    assert params.get("_refine_mode") is True
    assert params.get("_prior_columns") == ["employeeid", "ResourceName", "EmailId", "TechCategoryName"]
