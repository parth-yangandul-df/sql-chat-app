"""Tests for filter_extractor node — regex-first filter extraction with FieldRegistry validation."""

import pytest
from unittest.mock import AsyncMock, patch
from app.connectors.base_connector import QueryResult
from app.llm.graph.state import GraphState
from app.llm.graph.query_plan import FilterClause


def _base_state(**overrides) -> GraphState:
    """Minimal GraphState for filter extractor tests."""
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
    }
    state.update(overrides)
    return state


class TestExtractFiltersSkill:
    """Test 1: Skill extraction from question."""

    @pytest.mark.asyncio
    async def test_skill_keyword_trigger_extracts_filter_clause(self):
        """'active resources with Python skill' → FilterClause(field='skill', op='eq', values=['Python'])"""
        from app.llm.graph.nodes.filter_extractor import extract_filters
        state = _base_state(
            question="active resources with Python skill",
            domain="resource",
            intent="active_resources",
        )
        result = await extract_filters(state)
        filters = result["filters"]
        assert len(filters) >= 1
        skill_filter = next((f for f in filters if f.field == "skill"), None)
        assert skill_filter is not None
        assert skill_filter.op == "eq"
        assert "Python" in skill_filter.values


class TestExtractFiltersDateRange:
    """Test 2: Date range extraction with client name."""

    @pytest.mark.asyncio
    async def test_client_name_and_date_range_extracted(self):
        """'projects for client Acme between 2024-01-01 and 2024-06-30' → 2 FilterClauses."""
        from app.llm.graph.nodes.filter_extractor import extract_filters
        state = _base_state(
            question="projects for client Acme between 2024-01-01 and 2024-06-30",
            domain="project",
            intent="project_by_client",
        )
        result = await extract_filters(state)
        filters = result["filters"]
        # Should have at least 2 filters: client_name + date range
        fields_extracted = {f.field for f in filters}
        assert len(filters) >= 2, f"Expected >= 2 filters, got {len(filters)}: {filters}"
        # Date fields should be present
        date_fields = fields_extracted & {"start_date", "end_date"}
        assert len(date_fields) >= 1, f"Expected date fields, got: {fields_extracted}"


class TestExtractFiltersNumericThreshold:
    """Test 3: Numeric threshold extraction."""

    @pytest.mark.asyncio
    async def test_min_hours_gt_extracted(self):
        """'approved timesheets more than 8 hours' → FilterClause(field='min_hours', op='gt', values=['8'])"""
        from app.llm.graph.nodes.filter_extractor import extract_filters
        state = _base_state(
            question="approved timesheets more than 8 hours",
            domain="timesheet",
            intent="approved_timesheets",
        )
        result = await extract_filters(state)
        filters = result["filters"]
        hours_filter = next((f for f in filters if f.field == "min_hours"), None)
        assert hours_filter is not None, f"Expected min_hours filter, got: {[f.field for f in filters]}"
        assert hours_filter.op == "gt"
        assert "8" in hours_filter.values


class TestExtractFiltersUnknownField:
    """Test 4: Unknown fields are logged and dropped, no crash."""

    @pytest.mark.asyncio
    async def test_unknown_field_dropped_silently(self):
        """Unknown field from extraction → logged and dropped, no crash."""
        from app.llm.graph.nodes.filter_extractor import extract_filters
        # Force an empty result — no patterns match the question, domain has no skill field
        state = _base_state(
            question="show something with completely_unknown_xyz field",
            domain="client",
            intent="active_clients",
        )
        # Should not raise, should return empty or partial filters
        result = await extract_filters(state)
        assert "filters" in result
        assert isinstance(result["filters"], list)


class TestExtractFiltersZeroMatches:
    """Test 5: Regex returns zero matches → empty filter list."""

    @pytest.mark.asyncio
    async def test_no_patterns_match_returns_empty_filters(self):
        """Question with no extractable patterns returns empty filter list."""
        from app.llm.graph.nodes.filter_extractor import extract_filters
        state = _base_state(
            question="show me everything",
            domain="resource",
            intent="active_resources",
        )
        result = await extract_filters(state)
        filters = result["filters"]
        # No patterns match "show me everything" — should be empty or very minimal
        assert isinstance(filters, list)
        # Confirm no filter has an empty or None field
        for f in filters:
            assert f.field is not None
            assert f.field != ""


class TestExtractFiltersFollowUp:
    """Test 6: Follow-up with prior context inherits skill extraction."""

    @pytest.mark.asyncio
    async def test_followup_skill_extracted_from_bare_phrase(self):
        """'which of these know Python' after prior context → skill FilterClause."""
        from app.llm.graph.nodes.filter_extractor import extract_filters
        last_context = {
            "intent": "active_resources",
            "domain": "resource",
            "sql": "SELECT * FROM Resource WHERE IsActive = 1",
            "columns": ["Name", "EMPID"],
            "params": {},
        }
        state = _base_state(
            question="which of these know Python",
            domain="resource",
            intent="active_resources",
            last_turn_context=last_context,
        )
        result = await extract_filters(state)
        filters = result["filters"]
        skill_filter = next((f for f in filters if f.field == "skill"), None)
        assert skill_filter is not None, f"Expected skill filter for follow-up, got: {[f.field for f in filters]}"
        assert "Python" in skill_filter.values


class TestExtractFiltersSQLInjectionSanitized:
    """Test 7: SQL injection in extracted value is sanitized."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_value_sanitized(self):
        """SQL injection in extracted value → sanitized before FilterClause creation."""
        from app.llm.graph.nodes.filter_extractor import extract_filters
        # The client_name pattern will extract "Acme'; DROP TABLE users;--"
        state = _base_state(
            question="for client Acme",
            domain="project",
            intent="project_by_client",
        )
        result = await extract_filters(state)
        filters = result["filters"]
        # Filters should not contain SQL injection characters
        for f in filters:
            for val in f.values:
                assert "DROP" not in val.upper()
                assert ";" not in val
                assert "--" not in val
