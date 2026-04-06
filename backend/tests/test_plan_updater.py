"""Tests for plan_updater node — filter accumulation rules across turns."""

import pytest
from app.llm.graph.query_plan import FilterClause, QueryPlan
from app.llm.graph.state import GraphState


def _base_state(**overrides) -> GraphState:
    """Minimal GraphState for plan_updater tests."""
    state = {
        "question": "show active resources",
        "connection_id": "00000000-0000-0000-0000-000000000001",
        "connector_type": "sqlserver",
        "connection_string": "dsn=test",
        "timeout_seconds": 30,
        "max_rows": 100,
        "db": None,
        "session_id": None,
        "conversation_history": [],
        "last_turn_context": None,
        "user_id": None,
        "user_role": None,
        "resource_id": None,
        "domain": "resource",
        "intent": "active_resources",
        "confidence": 0.95,
        "params": {},
        "sql": None,
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
        "query_plan": None,
        "filters": [],
    }
    state.update(overrides)
    return state


def _make_filter(field: str, op: str, values: list[str]) -> FilterClause:
    return FilterClause(field=field, op=op, values=values)


def _make_plan(domain: str, intent: str, filters: list[FilterClause], base_sql: str = "") -> dict:
    plan = QueryPlan(
        domain=domain,
        intent=intent,
        filters=filters,
        base_intent_sql=base_sql,
        schema_version=1,
    )
    return plan.to_api_dict()


class TestPlanUpdaterInitialPlan:
    """Test 1: No existing plan + domain/intent → fresh QueryPlan with empty filters."""

    @pytest.mark.asyncio
    async def test_fresh_plan_created_when_no_existing_plan(self):
        """No existing query_plan → fresh QueryPlan with empty filters created."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        state = _base_state(
            domain="resource",
            intent="active_resources",
            query_plan=None,
            filters=[],
        )
        result = await update_query_plan(state)
        assert result["query_plan"] is not None
        plan = result["query_plan"]
        assert plan["domain"] == "resource"
        assert plan["intent"] == "active_resources"
        assert plan["filters"] == []
        assert plan["schema_version"] == 1


class TestPlanUpdaterFilterAppend:
    """Test 2: Same domain/intent + new filters → filters appended to existing plan."""

    @pytest.mark.asyncio
    async def test_new_filters_appended_to_existing_plan(self):
        """Same domain/intent + new non-overlapping filter → appended to existing."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        existing_plan = _make_plan(
            "resource", "active_resources",
            [_make_filter("skill", "eq", ["Python"])],
        )
        state = _base_state(
            domain="resource",
            intent="active_resources",
            query_plan=existing_plan,
            filters=[_make_filter("designation", "eq", ["Senior"])],
        )
        result = await update_query_plan(state)
        plan = result["query_plan"]
        fields = {f["field"] for f in plan["filters"]}
        assert "skill" in fields, "Existing skill filter should be preserved"
        assert "designation" in fields, "New designation filter should be appended"


class TestPlanUpdaterMultiValueAppend:
    """Test 3: Multi-value field (skill) → new values appended to existing list."""

    @pytest.mark.asyncio
    async def test_multi_value_skill_values_appended(self):
        """skill field is multi_value=True → new values appended to existing list."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        existing_plan = _make_plan(
            "resource", "active_resources",
            [_make_filter("skill", "eq", ["Python"])],
        )
        state = _base_state(
            domain="resource",
            intent="active_resources",
            query_plan=existing_plan,
            filters=[_make_filter("skill", "eq", ["Java"])],
        )
        result = await update_query_plan(state)
        plan = result["query_plan"]
        skill_filters = [f for f in plan["filters"] if f["field"] == "skill"]
        # Combined values should include both Python and Java
        all_values = [v for f in skill_filters for v in f["values"]]
        assert "Python" in all_values, f"Python should be retained: {all_values}"
        assert "Java" in all_values, f"Java should be appended: {all_values}"


class TestPlanUpdaterDateLastWins:
    """Test 4: Date range field → new dates replace old dates (last-wins)."""

    @pytest.mark.asyncio
    async def test_date_range_replaced_last_wins(self):
        """start_date is multi_value=False → new date replaces old date."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        existing_plan = _make_plan(
            "project", "project_by_client",
            [_make_filter("start_date", "between", ["2024-01-01", "2024-06-30"])],
        )
        state = _base_state(
            domain="project",
            intent="project_by_client",
            query_plan=existing_plan,
            filters=[_make_filter("start_date", "between", ["2025-01-01", "2025-12-31"])],
        )
        result = await update_query_plan(state)
        plan = result["query_plan"]
        date_filters = [f for f in plan["filters"] if f["field"] == "start_date"]
        assert len(date_filters) == 1, f"Should have exactly 1 date filter: {date_filters}"
        assert "2025-01-01" in date_filters[0]["values"], "New date should win"
        assert "2024-01-01" not in date_filters[0]["values"], "Old date should be replaced"


class TestPlanUpdaterBooleanLastWins:
    """Test 5: Boolean/scalar field → last-wins replacement."""

    @pytest.mark.asyncio
    async def test_boolean_field_replaced_last_wins(self):
        """billable is multi_value=False → new value replaces old (last-wins)."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        existing_plan = _make_plan(
            "resource", "resource_project_assignments",
            [_make_filter("billable", "eq", ["1"])],
        )
        state = _base_state(
            domain="resource",
            intent="resource_project_assignments",
            query_plan=existing_plan,
            filters=[_make_filter("billable", "eq", ["0"])],
        )
        result = await update_query_plan(state)
        plan = result["query_plan"]
        billable_filters = [f for f in plan["filters"] if f["field"] == "billable"]
        assert len(billable_filters) == 1
        assert billable_filters[0]["values"] == ["0"], "Last value should win"


class TestPlanUpdaterTopicSwitch:
    """Test 6: Domain/intent switch → fresh QueryPlan (old discarded)."""

    @pytest.mark.asyncio
    async def test_domain_switch_creates_fresh_plan(self):
        """Switching domain creates a fresh QueryPlan discarding old filters."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        existing_plan = _make_plan(
            "resource", "active_resources",
            [_make_filter("skill", "eq", ["Python"])],
        )
        state = _base_state(
            domain="project",
            intent="active_projects",
            query_plan=existing_plan,
            filters=[],
        )
        result = await update_query_plan(state)
        plan = result["query_plan"]
        assert plan["domain"] == "project"
        assert plan["intent"] == "active_projects"
        # Old resource skill filter should be gone
        skill_filters = [f for f in plan["filters"] if f["field"] == "skill"]
        assert len(skill_filters) == 0, "Old filters from different domain should be discarded"

    @pytest.mark.asyncio
    async def test_intent_switch_same_domain_creates_fresh_plan(self):
        """Switching intent within same domain creates a fresh QueryPlan."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        existing_plan = _make_plan(
            "resource", "active_resources",
            [_make_filter("skill", "eq", ["Python"])],
        )
        state = _base_state(
            domain="resource",
            intent="benched_resources",
            query_plan=existing_plan,
            filters=[],
        )
        result = await update_query_plan(state)
        plan = result["query_plan"]
        assert plan["intent"] == "benched_resources"
        # Old filters should be gone
        assert plan["filters"] == []


class TestPlanUpdaterEmptyFilters:
    """Test 7: Empty filter list → plan.filters stays unchanged."""

    @pytest.mark.asyncio
    async def test_empty_filters_leaves_existing_plan_unchanged(self):
        """Empty filter list → existing plan preserved without modification."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        existing_plan = _make_plan(
            "resource", "active_resources",
            [_make_filter("skill", "eq", ["Python"])],
        )
        state = _base_state(
            domain="resource",
            intent="active_resources",
            query_plan=existing_plan,
            filters=[],  # Empty filters this turn
        )
        result = await update_query_plan(state)
        plan = result["query_plan"]
        # Existing Python skill filter should be preserved
        skill_filters = [f for f in plan["filters"] if f["field"] == "skill"]
        assert len(skill_filters) == 1
        assert "Python" in skill_filters[0]["values"]


class TestPlanUpdaterNoDomainIntent:
    """Test 8: LLM fallback turn (no domain/intent) → query_plan remains None."""

    @pytest.mark.asyncio
    async def test_no_domain_returns_none_plan(self):
        """No domain (LLM fallback path) → query_plan remains None."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        state = _base_state(
            domain=None,
            intent=None,
            query_plan=None,
            filters=[],
        )
        result = await update_query_plan(state)
        assert result["query_plan"] is None
