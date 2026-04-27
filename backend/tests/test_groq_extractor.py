"""Tests for llm_groq_extractor — unified intent + filter extraction via Groq tool calling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helper — build mock Groq tool call result
# ---------------------------------------------------------------------------


def _mock_groq_result(
    intent: str,
    domain: str,
    confidence: float,
    filters: list[dict] | None = None,
    is_follow_up: bool = False,
    follow_up_type: str = "none",
    out_of_scope: bool = False,
) -> dict:
    return {
        "arguments": {
            "intent": intent,
            "domain": domain,
            "confidence": confidence,
            "filters": filters or [],
            "out_of_scope": out_of_scope,
            "is_follow_up": is_follow_up,
            "follow_up_type": follow_up_type,
        },
        "latency_ms": 10.0,
    }


def _make_mock_provider(groq_result: dict) -> MagicMock:
    provider = MagicMock()
    provider.complete_with_tools = AsyncMock(return_value=groq_result)
    return provider


# ---------------------------------------------------------------------------
# Test 1 — Basic intent extraction: benched resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_basic_intent_benched_resources():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="benched_resources",
        domain="resource",
        confidence=0.97,
    )
    mock_provider = _make_mock_provider(groq_result)

    state = {
        "question": "list all the benched resources",
        "user_role": "admin",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["intent"] == "benched_resources"
    assert result["domain"] == "resource"
    assert result["confidence"] >= 0.60
    assert result["filters"] == []


# ---------------------------------------------------------------------------
# Test 2 — Filter extraction: skill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_extraction_skill():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="resource_by_skill",
        domain="resource",
        confidence=0.97,
        filters=[{"field": "skill", "op": "eq", "values": ["Python"]}],
    )
    mock_provider = _make_mock_provider(groq_result)

    state = {
        "question": "python developers",
        "user_role": "admin",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["intent"] == "resource_by_skill"
    assert result["domain"] == "resource"
    assert len(result["filters"]) == 1
    assert result["filters"][0].field == "skill"


# ---------------------------------------------------------------------------
# Test 3 — Qualification rule: active projects for client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qualification_rule_project_by_client():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="project_by_client",
        domain="project",
        confidence=0.97,
        filters=[{"field": "client_name", "op": "eq", "values": ["Moon Gate Technology"]}],
    )
    mock_provider = _make_mock_provider(groq_result)

    state = {
        "question": "show active projects for moon gate technology",
        "user_role": "admin",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["intent"] == "project_by_client"
    assert result["domain"] == "project"


# ---------------------------------------------------------------------------
# Test 4 — Intent mutation: benched_resources + skill → benched_by_skill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intent_mutation_benched_resources_with_skill():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    # Groq returns benched_resources + skill filter — Python must mutate to benched_by_skill
    groq_result = _mock_groq_result(
        intent="benched_resources",
        domain="resource",
        confidence=0.90,
        filters=[{"field": "skill", "op": "eq", "values": ["SQL"]}],
    )
    mock_provider = _make_mock_provider(groq_result)

    state = {
        "question": "benched resources who know SQL",
        "user_role": "admin",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["intent"] == "benched_by_skill"


# ---------------------------------------------------------------------------
# Test 5 — Intent mutation: active_projects + client_name → project_by_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_intent_mutation_active_projects_with_client_name():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="active_projects",
        domain="project",
        confidence=0.90,
        filters=[{"field": "client_name", "op": "eq", "values": ["Acme Corp"]}],
    )
    mock_provider = _make_mock_provider(groq_result)

    state = {
        "question": "show active projects for Acme Corp",
        "user_role": "admin",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["intent"] == "project_by_client"


# ---------------------------------------------------------------------------
# Test 6 — Follow-up inheritance: filter_refinement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_followup_filter_refinement_inherits_prior_intent():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="benched_by_skill",
        domain="resource",
        confidence=0.95,
        filters=[{"field": "skill", "op": "eq", "values": ["SQL"]}],
        is_follow_up=True,
        follow_up_type="filter_refinement",
    )
    mock_provider = _make_mock_provider(groq_result)

    last_turn_context = {
        "intent": "benched_resources",
        "domain": "resource",
        "question": "list benched resources",
        "sql": "SELECT ...",
        "columns": [],
        "params": {},
    }
    state = {
        "question": "which of these know SQL",
        "user_role": "admin",
        "last_turn_context": last_turn_context,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    # filter_refinement inherits prior intent (benched_resources from last_turn_context),
    # then the mutation safety net fires because skill filter is present → benched_by_skill.
    assert result["intent"] == "benched_by_skill"
    assert result["domain"] == "resource"


# ---------------------------------------------------------------------------
# Test 7 — Topic switch: clears to new intent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_topic_switch_clears_to_new_intent():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="active_clients",
        domain="client",
        confidence=0.95,
        filters=[],
        is_follow_up=False,
        follow_up_type="topic_switch",
    )
    mock_provider = _make_mock_provider(groq_result)

    last_turn_context = {
        "intent": "benched_resources",
        "domain": "resource",
        "question": "list benched resources",
        "sql": "SELECT ...",
        "columns": [],
        "params": {},
    }
    state = {
        "question": "show all clients",
        "user_role": "admin",
        "last_turn_context": last_turn_context,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["intent"] == "active_clients"
    assert result["domain"] == "client"


# ---------------------------------------------------------------------------
# Test 8 — Low confidence returned as-is
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_returned_as_is():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="unknown",
        domain="unknown",
        confidence=0.0,
    )
    mock_provider = _make_mock_provider(groq_result)

    state = {
        "question": "resources joined last 6 months",
        "user_role": "admin",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    # unknown intent/domain normalised to None, confidence reflects 0.0
    assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Test 9 — RBAC gate: user role blocked from non-user_self domain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rbac_gate_user_role_non_user_self_domain():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    groq_result = _mock_groq_result(
        intent="benched_resources",
        domain="resource",
        confidence=0.97,
    )
    mock_provider = _make_mock_provider(groq_result)

    state = {
        "question": "list benched resources",
        "user_role": "user",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["confidence"] == 0.0
    assert result["domain"] is None


# ---------------------------------------------------------------------------
# Test 10 — Groq failure: graceful fallback to confidence=0.0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_groq_failure_graceful_fallback():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract

    mock_provider = MagicMock()
    mock_provider.complete_with_tools = AsyncMock(side_effect=Exception("Groq API error"))

    state = {
        "question": "list all the benched resources",
        "user_role": "admin",
        "last_turn_context": None,
    }

    with patch(
        "app.llm.graph.nodes.llm_groq_extractor._get_groq_provider",
        return_value=mock_provider,
    ):
        result = await groq_extract(state)

    assert result["confidence"] == 0.0
    assert result["intent"] is None


# ---------------------------------------------------------------------------
# Test 11 — route_after_groq routing logic
# ---------------------------------------------------------------------------


def test_route_after_groq_high_confidence_routes_to_domain_tool():
    from app.llm.graph.nodes.llm_groq_extractor import route_after_groq

    assert route_after_groq({"intent": "benched_resources", "confidence": 0.97}) == "run_domain_tool"


def test_route_after_groq_low_confidence_routes_to_llm_fallback():
    from app.llm.graph.nodes.llm_groq_extractor import route_after_groq

    assert route_after_groq({"intent": "benched_resources", "confidence": 0.5}) == "llm_fallback"


def test_route_after_groq_unknown_intent_routes_to_llm_fallback():
    from app.llm.graph.nodes.llm_groq_extractor import route_after_groq

    assert route_after_groq({"intent": "unknown", "confidence": 0.97}) == "llm_fallback"


def test_route_after_groq_exactly_at_threshold_routes_to_domain_tool():
    from app.llm.graph.nodes.llm_groq_extractor import route_after_groq

    # Confidence exactly at 0.60 must pass the >= check
    assert route_after_groq({"intent": "active_resources", "confidence": 0.60}) == "run_domain_tool"


def test_route_after_groq_none_intent_routes_to_llm_fallback():
    from app.llm.graph.nodes.llm_groq_extractor import route_after_groq

    # None intent → confidence gate decides (should fallback when 0.0)
    assert route_after_groq({"intent": None, "confidence": 0.0}) == "llm_fallback"
