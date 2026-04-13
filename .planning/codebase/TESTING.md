# Testing Patterns

**Analysis Date:** 2026-04-07

## Test Framework

**Runner:**
- Framework: pytest 8.0+
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
- Async mode: `asyncio_mode = "auto"` (automatic async support)

**Assertion Library:**
- pytest built-in (`assert`, `pytest.raises`, `pytest.approx`)
- unittest.mock for mocking

**Run Commands:**
```bash
pytest                           # Run all tests
pytest -m "not slow"             # Skip slow tests
pytest --cov=app                 # With coverage
pytest tests/                    # Specific directory
pytest tests/test_intent_classifier.py  # Specific file
```

## Test File Organization

**Location:**
- All tests in `backend/tests/` directory
- Co-located tests for semantic module in `backend/tests/semantic/`

**Naming:**
- Pattern: `test_*.py` (e.g., `test_intent_classifier.py`)
- Classes: `TestClassName` (e.g., `class TestFilterClause`)

**Structure:**
```
backend/tests/
├── conftest.py              # Shared fixtures
├── test_intent_classifier.py
├── test_query_plan_model.py
├── test_filter_extractor.py
├── test_graph_pipeline.py
├── test_semantic_wiring.py
├── test_domain_agents.py
└── semantic/
    ├── __init__.py
    ├── test_schema_linker_sqlserver.py
    └── test_relationship_inference.py
```

## Test Structure

**Suite Organization:**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _base_state(**overrides) -> GraphState:
    """Minimal GraphState factory for tests."""
    state = {
        "question": "show active resources",
        "connection_id": "00000000-0000-0000-0000-000000000001",
        "connector_type": "sqlserver",
        "connection_string": "dsn=test",
        "timeout_seconds": 30,
        "max_rows": 100,
        "db": None,
        # ... all required GraphState fields
    }
    state.update(overrides)
    return state


class TestFilterClause:
    """FilterClause validation and behavior tests."""

    def test_valid_filter_eq(self):
        """FilterClause with valid 'eq' op and values passes."""
        fc = FilterClause(field="status", op="eq", values=["active"])
        assert fc.field == "status"
        assert fc.op == "eq"
```

**Patterns:**
- Helper function `_base_state()` creates minimal GraphState for each test
- Use `@pytest.mark.asyncio` for async test functions
- Use descriptive docstrings for each test case

**Assertion Patterns:**
```python
# Exact equality
assert updates["confidence"] == pytest.approx(1.0, abs=1e-6)

# Exception testing
with pytest.raises(ValidationError):
    FilterClause(field="status", op="contains", values=["active"])

# Type checking
assert isinstance(hints, list)
assert plan.filters == []
```

## Mocking

**Framework:** unittest.mock (AsyncMock, MagicMock, patch)

**Patterns:**
```python
# Async function mocking
with patch("app.llm.graph.nodes.intent_classifier.embed_text",
           AsyncMock(return_value=[0.1, 0.9, 0.1])):
    state = _base_state()
    updates = await classify_intent(state)

# Module-level patching
with patch("app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded",
           AsyncMock()):
    pass

# Patch with return_value
with patch("app.llm.graph.nodes.intent_classifier.get_catalog_embeddings",
           return_value=[[1.0, 0.0, 0.0]] * 24):
    pass

# AsyncMock for connector
mock_conn = MagicMock()
mock_conn.execute_query = AsyncMock(return_value=mock_query_result)

# Patching at usage site (for already-imported references)
monkeypatch.setattr("app.llm.graph.intent_catalog.embed_text", _stub)
```

**What to Mock:**
- Database sessions (`mock_db`)
- LLM providers (embed_text, completions)
- Connectors (execute_query)
- External services

**What NOT to Mock:**
- Pydantic model validation (test with real data)
- QueryPlan, FilterClause (test actual behavior)
- Graph state TypedDict (test structure)

## Fixtures and Factories

**Test Data:**
```python
# In conftest.py
@pytest.fixture
def mock_db():
    """Mock AsyncSession with add/flush/execute stubs."""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_query_result():
    """A minimal QueryResult with two rows."""
    return QueryResult(
        columns=["Name", "IsActive"],
        column_types=["nvarchar", "bit"],
        rows=[["Alice", 1], ["Bob", 1]],
        row_count=2,
        execution_time_ms=12.5,
        truncated=False,
    )


@pytest.fixture
def mock_embed_text(monkeypatch):
    """Replace embed_text with a deterministic stub."""
    async def _stub(text: str) -> list[float]:
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr("app.llm.graph.intent_catalog.embed_text", _stub)
    return _stub
```

**Location:**
- Shared fixtures: `backend/tests/conftest.py`
- Test-specific fixtures: defined within test file

## Coverage

**Requirements:** Not currently enforced (no coverage target set)

**View Coverage:**
```bash
pytest --cov=app --cov-report=term-missing
```

**Key directories to cover:**
- `app/llm/graph/nodes/` — graph node logic
- `app/llm/graph/query_plan.py` — QueryPlan/FilterClause models
- `app/semantic/` — semantic resolvers
- `app/connectors/` — database connectors

## Test Types

**Unit Tests:**
- Focus: Pydantic models, graph nodes, filter extraction logic
- Example: `test_query_plan_model.py` tests QueryPlan validation
- Mock: Database, LLM, connectors

**Integration Tests:**
- Focus: Full graph execution, semantic wiring
- Example: `test_graph_pipeline.py` tests full graph with mocked external services
- Mock: LLM providers, connectors

**Test Examples:**

```python
# Unit test — Pydantic validation
def test_from_untrusted_dict_rejects_unknown_keys(self):
    """QueryPlan.from_untrusted_dict() rejects unknown keys (extra='forbid')."""
    data = {
        "domain": "resource",
        "intent": "active_resources",
        "unknown_field": "should be rejected",
    }
    with pytest.raises(ValidationError):
        QueryPlan.from_untrusted_dict(data)


# Unit test — Graph node
@pytest.mark.asyncio
async def test_skill_keyword_trigger_extracts_filter_clause(self):
    """'active resources with Python skill' → FilterClause(field='skill', op='eq', values=['Python'])"""
    from app.llm.graph.nodes.filter_extractor import extract_filters
    state = _base_state(
        question="active resources with Python skill",
        domain="resource",
        intent="active_resources",
    )
    updates = await extract_filters(state)
    assert updates["query_plan"] is not None


# Integration test — Full graph
@pytest.mark.asyncio
async def test_graph_domain_tool_path(mock_db, mock_query_result):
    """Full graph invocation via domain tool path with all nodes mocked."""
    with (
        patch("app.llm.graph.nodes.intent_classifier.embed_text", ...),
        patch("app.llm.graph.domains.base_domain.get_or_create_connector", ...),
    ):
        result = await get_compiled_graph().ainvoke(initial_state)
        assert result["answer"] is not None
```

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_classify_intent_high_confidence():
    """When question embedding matches first catalog entry exactly."""
    from app.llm.graph.nodes.intent_classifier import classify_intent
    
    with patch("app.llm.graph.nodes.intent_classifier.embed_text",
               AsyncMock(return_value=[1.0, 0.0, 0.0])):
        state = _base_state()
        updates = await classify_intent(state)
    
    assert updates["confidence"] == pytest.approx(1.0, abs=1e-6)
```

**Error Testing:**
```python
@pytest.mark.asyncio
async def test_resolve_glossary_hints_degrades_on_db_error(self):
    """Returns empty list on DB exception (graceful degradation)."""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=Exception("DB unavailable"))
    
    hints = await resolve_glossary_hints(mock_db, "conn-001", "resource")
    
    assert hints == []  # Graceful degradation
```

**State Construction:**
```python
def _full_state(domain="resource", intent="active_resources", confidence=0.95) -> GraphState:
    return {
        "question": "show active resources",
        "connection_id": "00000000-0000-0000-0000-000000000001",
        "connector_type": "sqlserver",
        # ... all required fields from GraphState TypedDict
    }
```

---

*Testing analysis: 2026-04-07*