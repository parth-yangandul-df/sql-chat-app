"""Tests for TurnContext schema and its integration with QueryRequest/QueryResponse."""

import uuid

import pytest

from app.api.v1.schemas.query import QueryRequest, QueryResponse, TurnContext


# ── TurnContext instantiation ────────────────────────────────────────────────


def test_turn_context_with_all_fields():
    """TurnContext can be instantiated with all fields explicitly set."""
    ctx = TurnContext(
        intent="active_resources",
        domain="resource",
        params={"skill": "Python", "limit": 10},
        columns=["Name", "Role"],
        sql="SELECT Name, Role FROM Resources WHERE IsActive=1",
    )
    assert ctx.intent == "active_resources"
    assert ctx.domain == "resource"
    assert ctx.params == {"skill": "Python", "limit": 10}
    assert ctx.columns == ["Name", "Role"]
    assert ctx.sql == "SELECT Name, Role FROM Resources WHERE IsActive=1"


def test_turn_context_defaults():
    """TurnContext defaults: params={}, columns=[], sql=''."""
    ctx = TurnContext(intent="active_resources", domain="resource")
    assert ctx.params == {}
    assert ctx.columns == []
    assert ctx.sql == ""


# ── QueryRequest backward compatibility ─────────────────────────────────────


def test_query_request_accepts_no_last_turn_context():
    """QueryRequest without last_turn_context field is backward-compatible (defaults to None)."""
    req = QueryRequest(
        connection_id=uuid.uuid4(),
        question="How many active resources do we have?",
    )
    assert req.last_turn_context is None


def test_query_request_accepts_turn_context_object():
    """QueryRequest accepts a TurnContext object in last_turn_context."""
    ctx = TurnContext(intent="active_resources", domain="resource")
    req = QueryRequest(
        connection_id=uuid.uuid4(),
        question="Who are they?",
        last_turn_context=ctx,
    )
    assert req.last_turn_context is not None
    assert req.last_turn_context.intent == "active_resources"
    assert req.last_turn_context.domain == "resource"


# ── QueryResponse turn_context field ────────────────────────────────────────


def test_query_response_turn_context_defaults_to_none():
    """QueryResponse has turn_context field defaulting to None."""
    resp = QueryResponse(
        id=uuid.uuid4(),
        question="Test?",
        generated_sql="SELECT 1",
        explanation="Explanation",
        columns=["col"],
        column_types=["int"],
        rows=[[1]],
        row_count=1,
        execution_time_ms=5.0,
        truncated=False,
        summary=None,
        suggested_followups=[],
        llm_provider="anthropic",
        llm_model="claude-3-5-sonnet",
    )
    assert resp.turn_context is None
