"""Semantic wiring tests — Task 4.1: semantic_resolver, Task 4.2: filter_extractor/plan_updater wiring,
Task 4.3: MetricFragment injection in sql_compiler.

All DB sessions are mocked — no real DB required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# TASK 4.1: semantic_resolver tests — glossary hints + value_map normalization
# ===========================================================================

class TestResolveGlossaryHints:
    """Test resolve_glossary_hints() returns field names from glossary terms."""

    @pytest.mark.asyncio
    async def test_resolve_glossary_hints_returns_field_names(self):
        """resolve_glossary_hints() returns available field names from glossary terms."""
        from app.llm.graph.nodes.semantic_resolver import resolve_glossary_hints
        from unittest.mock import AsyncMock, MagicMock

        # Mock DB returning two glossary terms with related_columns
        mock_db = MagicMock()
        mock_term1 = MagicMock()
        mock_term1.term = "Python Developer"
        mock_term1.definition = "A developer with Python skills"
        mock_term1.related_columns = ["skill", "designation"]

        mock_term2 = MagicMock()
        mock_term2.term = "Backend"
        mock_term2.definition = "Backend developer designation"
        mock_term2.related_columns = ["designation"]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_term1, mock_term2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        hints = await resolve_glossary_hints(mock_db, "conn-001", "resource")

        assert isinstance(hints, list)
        assert len(hints) > 0
        assert "skill" in hints or "designation" in hints

    @pytest.mark.asyncio
    async def test_resolve_glossary_hints_empty_on_no_terms(self):
        """resolve_glossary_hints() returns empty list when no glossary terms exist."""
        from app.llm.graph.nodes.semantic_resolver import resolve_glossary_hints

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        hints = await resolve_glossary_hints(mock_db, "conn-001", "resource")

        assert hints == []

    @pytest.mark.asyncio
    async def test_resolve_glossary_hints_degrades_on_db_error(self):
        """resolve_glossary_hints() returns empty list on DB exception (graceful degradation)."""
        from app.llm.graph.nodes.semantic_resolver import resolve_glossary_hints

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB unavailable"))

        hints = await resolve_glossary_hints(mock_db, "conn-001", "resource")

        assert hints == []


class TestLoadValueMap:
    """Test load_value_map() populates from DB dictionary entries."""

    @pytest.mark.asyncio
    async def test_load_value_map_returns_nested_dict(self):
        """load_value_map() returns {field_name: {user_value: db_value}} mapping."""
        from app.llm.graph.nodes.semantic_resolver import load_value_map

        # Mock DB returning dictionary entries with raw_value → display_value mappings
        mock_db = MagicMock()

        # Mock column object
        mock_col = MagicMock()
        mock_col.column_name = "Designation"

        mock_entry1 = MagicMock()
        mock_entry1.raw_value = "backend"
        mock_entry1.display_value = "Backend Developer"
        mock_entry1.column = mock_col

        mock_entry2 = MagicMock()
        mock_entry2.raw_value = "frontend"
        mock_entry2.display_value = "Frontend Developer"
        mock_entry2.column = mock_col

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry1, mock_entry2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        value_map = await load_value_map(mock_db)

        assert isinstance(value_map, dict)

    @pytest.mark.asyncio
    async def test_load_value_map_degrades_on_db_error(self):
        """load_value_map() returns empty dict on DB exception (graceful degradation)."""
        from app.llm.graph.nodes.semantic_resolver import load_value_map

        mock_db = MagicMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB unavailable"))

        value_map = await load_value_map(mock_db)

        assert value_map == {}


class TestNormalizeValue:
    """Test normalize_value() maps user values to DB values via value_map."""

    def test_normalize_value_maps_user_to_db_value(self):
        """normalize_value() returns the DB value when mapping exists."""
        from app.llm.graph.nodes.semantic_resolver import normalize_value

        value_map = {
            "designation": {"backend": "Backend Developer", "frontend": "Frontend Developer"},
        }
        result = normalize_value("backend", field="designation", value_map=value_map)
        assert result == "Backend Developer"

    def test_normalize_value_maps_active_status(self):
        """normalize_value() maps 'active' to 'Active' via value_map."""
        from app.llm.graph.nodes.semantic_resolver import normalize_value

        value_map = {
            "status": {"active": "Active", "inactive": "Inactive"},
        }
        result = normalize_value("active", field="status", value_map=value_map)
        assert result == "Active"

    def test_normalize_value_returns_unchanged_when_no_match(self):
        """normalize_value() returns value unchanged when no mapping found."""
        from app.llm.graph.nodes.semantic_resolver import normalize_value

        value_map = {
            "designation": {"backend": "Backend Developer"},
        }
        result = normalize_value("unknown_val", field="designation", value_map=value_map)
        assert result == "unknown_val"

    def test_normalize_value_case_insensitive(self):
        """normalize_value() performs case-insensitive matching."""
        from app.llm.graph.nodes.semantic_resolver import normalize_value

        value_map = {
            "designation": {"backend": "Backend Developer"},
        }
        result = normalize_value("BACKEND", field="designation", value_map=value_map)
        assert result == "Backend Developer"

    def test_normalize_value_returns_unchanged_for_unknown_field(self):
        """normalize_value() returns value unchanged when field not in value_map."""
        from app.llm.graph.nodes.semantic_resolver import normalize_value

        value_map = {}
        result = normalize_value("some_val", field="unknown_field", value_map=value_map)
        assert result == "some_val"


class TestNormalizeValuesBatch:
    """Test normalize_values_batch() normalizes a list of FilterClauses."""

    def test_normalize_values_batch_normalizes_text_filters(self):
        """normalize_values_batch() normalizes text field filter values."""
        from app.llm.graph.nodes.semantic_resolver import normalize_values_batch
        from app.llm.graph.query_plan import FilterClause

        value_map = {
            "designation": {"backend": "Backend Developer"},
        }
        filters = [
            FilterClause(field="designation", op="eq", values=["backend"]),
        ]
        result = normalize_values_batch(filters, value_map)

        assert len(result) == 1
        assert result[0].values == ["Backend Developer"]

    def test_normalize_values_batch_skips_date_fields(self):
        """normalize_values_batch() does not normalize date field values."""
        from app.llm.graph.nodes.semantic_resolver import normalize_values_batch
        from app.llm.graph.query_plan import FilterClause

        value_map = {
            "start_date": {"2024-01-01": "Something Else"},  # Should NOT apply to date fields
        }
        filters = [
            FilterClause(field="start_date", op="eq", values=["2024-01-01"]),
        ]
        result = normalize_values_batch(filters, value_map)

        # Date fields should pass through unchanged
        assert result[0].values == ["2024-01-01"]

    def test_normalize_values_batch_skips_numeric_fields(self):
        """normalize_values_batch() does not normalize numeric field values."""
        from app.llm.graph.nodes.semantic_resolver import normalize_values_batch
        from app.llm.graph.query_plan import FilterClause

        value_map = {
            "min_hours": {"8": "Eight"},  # Should NOT apply to numeric fields
        }
        filters = [
            FilterClause(field="min_hours", op="gt", values=["8"]),
        ]
        result = normalize_values_batch(filters, value_map)

        # Numeric fields should pass through unchanged
        assert result[0].values == ["8"]

    def test_normalize_values_batch_returns_unchanged_when_no_map(self):
        """normalize_values_batch() returns original filters when value_map is empty."""
        from app.llm.graph.nodes.semantic_resolver import normalize_values_batch
        from app.llm.graph.query_plan import FilterClause

        filters = [
            FilterClause(field="designation", op="eq", values=["some value"]),
        ]
        result = normalize_values_batch(filters, {})

        assert result[0].values == ["some value"]


# ===========================================================================
# TASK 4.2: filter_extractor and plan_updater wiring tests
# ===========================================================================

class TestFilterExtractorGlossaryHints:
    """Test filter_extractor uses glossary hints for disambiguation."""

    @pytest.mark.asyncio
    async def test_filter_extractor_works_without_glossary_hints(self):
        """filter_extractor degrades gracefully — falls back to regex when no glossary."""
        from app.llm.graph.nodes.filter_extractor import extract_filters

        mock_db = MagicMock()
        state = {
            "question": "resources with Python skill",
            "domain": "resource",
            "intent": "active_resources",
            "last_turn_context": None,
            "db": mock_db,
            "connection_id": "conn-001",
        }

        # Patch resolve_glossary_hints to return empty (DB unavailable scenario)
        with patch(
            "app.llm.graph.nodes.filter_extractor.resolve_glossary_hints",
            return_value=[],
        ):
            result = await extract_filters(state)

        # Regex should still extract the skill
        assert "filters" in result
        skill_filters = [f for f in result["filters"] if f.field == "skill"]
        assert len(skill_filters) >= 1

    @pytest.mark.asyncio
    async def test_filter_extractor_falls_back_when_glossary_fails(self):
        """filter_extractor continues with regex when glossary resolution throws."""
        from app.llm.graph.nodes.filter_extractor import extract_filters

        mock_db = MagicMock()
        state = {
            "question": "resources with Python skill",
            "domain": "resource",
            "intent": "active_resources",
            "last_turn_context": None,
            "db": mock_db,
            "connection_id": "conn-001",
        }

        # Patch resolve_glossary_hints to raise (DB error scenario)
        with patch(
            "app.llm.graph.nodes.filter_extractor.resolve_glossary_hints",
            side_effect=Exception("DB error"),
        ):
            # Should NOT raise — should degrade gracefully
            result = await extract_filters(state)

        assert "filters" in result
        # Regex still works
        skill_filters = [f for f in result["filters"] if f.field == "skill"]
        assert len(skill_filters) >= 1


class TestPlanUpdaterValueMapNormalization:
    """Test plan_updater normalizes filter values through value_map."""

    @pytest.mark.asyncio
    async def test_plan_updater_normalizes_filter_values(self):
        """plan_updater normalizes designation filter 'backend' → 'Backend Developer'."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        from app.llm.graph.query_plan import FilterClause

        # Set up cached value_map with designation mapping
        with patch(
            "app.llm.graph.nodes.plan_updater.get_cached_value_map",
            return_value={"designation": {"backend": "Backend Developer"}},
        ):
            state = {
                "domain": "resource",
                "intent": "active_resources",
                "query_plan": None,
                "filters": [
                    FilterClause(field="designation", op="eq", values=["backend"]),
                ],
                "params": {},
            }
            result = await update_query_plan(state)

        plan = result["query_plan"]
        assert plan is not None
        desig_filters = [f for f in plan["filters"] if f["field"] == "designation"]
        assert len(desig_filters) == 1
        # Value should be normalized
        assert desig_filters[0]["values"] == ["Backend Developer"]

    @pytest.mark.asyncio
    async def test_plan_updater_passes_unknown_values_unchanged(self):
        """plan_updater passes filter values unchanged when not in value_map."""
        from app.llm.graph.nodes.plan_updater import update_query_plan
        from app.llm.graph.query_plan import FilterClause

        with patch(
            "app.llm.graph.nodes.plan_updater.get_cached_value_map",
            return_value={},  # empty map → no normalization
        ):
            state = {
                "domain": "resource",
                "intent": "active_resources",
                "query_plan": None,
                "filters": [
                    FilterClause(field="designation", op="eq", values=["SomeValue"]),
                ],
                "params": {},
            }
            result = await update_query_plan(state)

        plan = result["query_plan"]
        assert plan is not None
        desig_filters = [f for f in plan["filters"] if f["field"] == "designation"]
        # Should be unchanged
        assert desig_filters[0]["values"] == ["SomeValue"]


# ===========================================================================
# TASK 4.3: MetricFragment injection in sql_compiler tests
# ===========================================================================

class TestMetricFragment:
    """Test MetricFragment dataclass exists with correct fields."""

    def test_metric_fragment_dataclass_exists(self):
        """MetricFragment is a dataclass with select_expr, join_clause, requires_group_by."""
        from app.llm.graph.nodes.sql_compiler import MetricFragment

        mf = MetricFragment(
            select_expr="SUM(Hours) AS total_hours",
            join_clause="JOIN timesheets ON resources.id = timesheets.resource_id",
            requires_group_by=True,
        )
        assert mf.select_expr == "SUM(Hours) AS total_hours"
        assert mf.join_clause == "JOIN timesheets ON resources.id = timesheets.resource_id"
        assert mf.requires_group_by is True


class TestCompileQueryWithMetrics:
    """Test compile_query() injecting MetricFragment into SQL templates."""

    def test_compile_query_with_metric_injects_select_expr(self):
        """compile_query() replaces {select_extras} with metric select_expr."""
        from app.llm.graph.nodes.sql_compiler import compile_query, MetricFragment
        from app.llm.graph.query_plan import QueryPlan

        plan = QueryPlan(
            domain="resource",
            intent="active_resources",
            filters=[],
            base_intent_sql="",
            schema_version=1,
        )
        metric = MetricFragment(
            select_expr="SUM(Hours) AS total_hours",
            join_clause="",
            requires_group_by=False,
        )

        sql, params = compile_query(plan, metrics=[metric])

        assert "SUM(Hours) AS total_hours" in sql

    def test_compile_query_with_metric_requiring_group_by_adds_group_by(self):
        """compile_query() adds GROUP BY when MetricFragment.requires_group_by=True."""
        from app.llm.graph.nodes.sql_compiler import compile_query, MetricFragment
        from app.llm.graph.query_plan import QueryPlan

        plan = QueryPlan(
            domain="resource",
            intent="active_resources",
            filters=[],
            base_intent_sql="",
            schema_version=1,
        )
        metric = MetricFragment(
            select_expr="SUM(Hours) AS total_hours",
            join_clause="",
            requires_group_by=True,
        )

        sql, params = compile_query(plan, metrics=[metric])

        assert "GROUP BY" in sql

    def test_compile_query_with_metric_injects_join_clause(self):
        """compile_query() replaces {join_extras} with metric join_clause."""
        from app.llm.graph.nodes.sql_compiler import compile_query, MetricFragment
        from app.llm.graph.query_plan import QueryPlan

        plan = QueryPlan(
            domain="timesheet",
            intent="approved_timesheets",
            filters=[],
            base_intent_sql="",
            schema_version=1,
        )
        join_clause = "JOIN Project p ON ts.ProjectId = p.ProjectId"
        metric = MetricFragment(
            select_expr="",
            join_clause=join_clause,
            requires_group_by=False,
        )

        sql, params = compile_query(plan, metrics=[metric])

        assert join_clause in sql

    def test_compile_query_without_metrics_defaults_to_empty_tokens(self):
        """compile_query() without metrics replaces {select_extras}/{join_extras} with empty."""
        from app.llm.graph.nodes.sql_compiler import compile_query
        from app.llm.graph.query_plan import QueryPlan

        plan = QueryPlan(
            domain="resource",
            intent="active_resources",
            filters=[],
            base_intent_sql="",
            schema_version=1,
        )

        sql, params = compile_query(plan)

        assert "{select_extras}" not in sql
        assert "{join_extras}" not in sql

    def test_compile_query_without_group_by_metric_no_group_by(self):
        """compile_query() with MetricFragment.requires_group_by=False → no extra GROUP BY."""
        from app.llm.graph.nodes.sql_compiler import compile_query, MetricFragment
        from app.llm.graph.query_plan import QueryPlan

        plan = QueryPlan(
            domain="resource",
            intent="resource_skills_list",  # No base GROUP BY
            filters=[],
            base_intent_sql="",
            schema_version=1,
        )
        metric = MetricFragment(
            select_expr="COUNT(*) AS total",
            join_clause="",
            requires_group_by=False,  # No GROUP BY required
        )

        sql, params = compile_query(plan, metrics=[metric])

        # Should NOT have GROUP BY injected
        assert "GROUP BY" not in sql

    def test_compile_query_metric_does_not_conflict_with_where_clauses(self):
        """compile_query() with metrics + filters — both WHERE and metric injection work."""
        from app.llm.graph.nodes.sql_compiler import compile_query, MetricFragment
        from app.llm.graph.query_plan import QueryPlan, FilterClause

        plan = QueryPlan(
            domain="resource",
            intent="active_resources",
            filters=[
                FilterClause(field="resource_name", op="eq", values=["Alice"]),
            ],
            base_intent_sql="",
            schema_version=1,
        )
        metric = MetricFragment(
            select_expr="SUM(Hours) AS total_hours",
            join_clause="",
            requires_group_by=True,
        )

        sql, params = compile_query(plan, metrics=[metric])

        # Both metric and filter should appear
        assert "SUM(Hours) AS total_hours" in sql
        assert "Alice" in str(params) or "%Alice%" in str(params)
        assert "WHERE" in sql


class TestDetectMetrics:
    """Test detect_metrics() keyword-matching stub."""

    def test_detect_metrics_returns_list(self):
        """detect_metrics() returns a list (possibly empty)."""
        from app.llm.graph.nodes.sql_compiler import detect_metrics

        result = detect_metrics("what are active resources", [])
        assert isinstance(result, list)

    def test_detect_metrics_returns_empty_for_no_match(self):
        """detect_metrics() returns empty list when no metric keywords match."""
        from app.llm.graph.nodes.sql_compiler import detect_metrics

        result = detect_metrics("show me active resources", [])
        assert result == []
