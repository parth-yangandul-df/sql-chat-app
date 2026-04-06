"""Retirement tests — verify old refinement modules are properly deprecated.

Tests verify:
1. refinement_registry.py EXISTS with deprecation header (kept for rollback safety)
2. param_extractor.py EXISTS with deprecation header (kept for test compatibility)
3. Archived copy of param_extractor.py exists in _deprecated/
4. param_extractor is NOT imported in graph.py (was already replaced in Phase 7-02)
5. _try_refinement() still exists in base_domain.py (flag=OFF fallback preserved)
6. Feature flag OFF path is functional (existing _try_refinement behavior works)
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).parent.parent
APP_DIR = BACKEND_DIR / "app"
GRAPH_DIR = APP_DIR / "llm" / "graph"


# ---------------------------------------------------------------------------
# Test 1: refinement_registry.py EXISTS and has deprecation header
# ---------------------------------------------------------------------------

def test_refinement_registry_exists():
    """refinement_registry.py must exist — it's the flag=OFF rollback safety net."""
    path = GRAPH_DIR / "domains" / "refinement_registry.py"
    assert path.exists(), (
        "refinement_registry.py must NOT be deleted — it is required for USE_QUERY_PLAN_COMPILER=false rollback"
    )


def test_refinement_registry_has_deprecation_header():
    """refinement_registry.py must have a deprecation comment at the top."""
    path = GRAPH_DIR / "domains" / "refinement_registry.py"
    content = path.read_text(encoding="utf-8")
    assert "DEPRECATED" in content[:300], (
        "refinement_registry.py must have a DEPRECATED comment in the first 300 chars"
    )


# ---------------------------------------------------------------------------
# Test 2: param_extractor.py EXISTS with deprecation header (original location)
# ---------------------------------------------------------------------------

def test_param_extractor_exists_at_original_location():
    """param_extractor.py must exist at original location for test compatibility."""
    path = GRAPH_DIR / "nodes" / "param_extractor.py"
    assert path.exists(), (
        "param_extractor.py must remain at original location for backward compatibility"
    )


def test_param_extractor_has_deprecation_header():
    """param_extractor.py must have a deprecation comment at the top."""
    path = GRAPH_DIR / "nodes" / "param_extractor.py"
    content = path.read_text(encoding="utf-8")
    assert "DEPRECATED" in content[:300], (
        "param_extractor.py must have a DEPRECATED comment in the first 300 chars"
    )


# ---------------------------------------------------------------------------
# Test 3: Archived copy in _deprecated/
# ---------------------------------------------------------------------------

def test_param_extractor_archived_in_deprecated():
    """A copy of param_extractor.py must exist in nodes/_deprecated/."""
    deprecated_path = GRAPH_DIR / "nodes" / "_deprecated" / "param_extractor.py"
    assert deprecated_path.exists(), (
        "param_extractor.py must be archived in nodes/_deprecated/ for audit trail"
    )


def test_deprecated_directory_has_readme():
    """_deprecated/ directory must have a README.md explaining the archive."""
    readme_path = GRAPH_DIR / "nodes" / "_deprecated" / "README.md"
    assert readme_path.exists(), "_deprecated/ directory must have README.md"
    content = readme_path.read_text(encoding="utf-8")
    assert "param_extractor" in content


# ---------------------------------------------------------------------------
# Test 4: param_extractor NOT imported in graph.py
# ---------------------------------------------------------------------------

def test_param_extractor_not_imported_in_graph():
    """graph.py must NOT import param_extractor — it was replaced by filter_extractor."""
    graph_path = GRAPH_DIR / "graph.py"
    assert graph_path.exists(), "graph.py not found"

    content = graph_path.read_text(encoding="utf-8")
    # Check for any import of param_extractor (direct import or from import)
    assert "param_extractor" not in content, (
        "graph.py must NOT import param_extractor — use filter_extractor instead"
    )


# ---------------------------------------------------------------------------
# Test 5: _try_refinement() still exists in base_domain.py (flag=OFF preserved)
# ---------------------------------------------------------------------------

def test_try_refinement_preserved_in_base_domain():
    """_try_refinement() must still exist — it's the flag=OFF fallback."""
    from app.llm.graph.domains.base_domain import BaseDomainAgent
    assert hasattr(BaseDomainAgent, "_try_refinement"), (
        "_try_refinement() must be preserved in BaseDomainAgent for flag=OFF rollback"
    )
    # Verify it's actually callable (not just a stub)
    assert callable(BaseDomainAgent._try_refinement)


def test_is_refine_mode_preserved():
    """_is_refine_mode() helper must still exist (used by flag=OFF path)."""
    from app.llm.graph.domains.base_domain import _is_refine_mode
    assert callable(_is_refine_mode)


def test_get_prior_sql_preserved():
    """_get_prior_sql() helper must still exist (used by flag=OFF path)."""
    from app.llm.graph.domains.base_domain import _get_prior_sql
    assert callable(_get_prior_sql)


def test_strip_order_by_preserved():
    """_strip_order_by() helper must still exist (used by flag=OFF path)."""
    from app.llm.graph.domains.base_domain import _strip_order_by
    assert callable(_strip_order_by)


# ---------------------------------------------------------------------------
# Test 6: Flag=OFF path still functional
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flag_off_path_functional(monkeypatch):
    """With USE_QUERY_PLAN_COMPILER=false, the old _try_refinement path still works."""
    import importlib
    monkeypatch.setenv("USE_QUERY_PLAN_COMPILER", "false")

    import app.config
    importlib.reload(app.config)
    import app.llm.graph.domains.base_domain as bd_module
    importlib.reload(bd_module)

    from app.llm.graph.domains.resource import ResourceAgent
    from app.connectors.base_connector import QueryResult
    from unittest.mock import AsyncMock, MagicMock, patch

    def _mock_result():
        return QueryResult(
            columns=["Name"], column_types=["nvarchar"],
            rows=[["Alice"]], row_count=1,
            execution_time_ms=1.0, truncated=False,
        )

    agent = ResourceAgent()
    mock_connector = MagicMock()
    mock_connector.execute_query = AsyncMock(return_value=_mock_result())

    state = {
        "question": "show active resources",
        "connection_id": "conn-001",
        "connector_type": "mssql",
        "connection_string": "mssql://server/db",
        "timeout_seconds": 30,
        "max_rows": 1000,
        "db": MagicMock(),
        "session_id": None,
        "conversation_history": [],
        "last_turn_context": None,
        "user_id": None,
        "user_role": "admin",
        "resource_id": None,
        "domain": "resource",
        "intent": "active_resources",
        "confidence": 0.95,
        "params": {},  # No refine mode
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
        "filters": [],
        "query_plan": None,
    }

    with patch(
        "app.llm.graph.domains.base_domain.get_or_create_connector",
        return_value=mock_connector,
    ):
        result = await agent.execute(state)

    assert result["error"] is None
    assert result["sql"] is not None
    assert result["llm_provider"] == "domain_tool"
    mock_connector.execute_query.assert_called_once()


# ---------------------------------------------------------------------------
# Test: refinement_registry still importable (functional, not just present)
# ---------------------------------------------------------------------------

def test_refinement_registry_still_importable():
    """refinement_registry must be importable (it's still used by flag=OFF path)."""
    from app.llm.graph.domains.refinement_registry import (
        REFINEMENT_REGISTRY,
        find_matching_template,
        supports_refinement,
    )
    # Must have templates registered for all 5 domains
    assert "resource" in REFINEMENT_REGISTRY
    assert "client" in REFINEMENT_REGISTRY
    assert "project" in REFINEMENT_REGISTRY
    assert "timesheet" in REFINEMENT_REGISTRY
    assert "user_self" in REFINEMENT_REGISTRY
