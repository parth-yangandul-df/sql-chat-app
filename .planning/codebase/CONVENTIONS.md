# Coding Conventions

**Analysis Date:** 2026-04-07

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `query_service.py`, `schema_linker.py`)
- Test files: `test_*.py` (e.g., `test_intent_classifier.py`)
- Configuration: `config.py`

**Functions:**
- Async functions: `async def` prefix (e.g., `async def execute_query()`)
- Regular functions: `snake_case`
- Graph nodes: descriptive verbs (e.g., `classify_intent`, `extract_params`)

**Variables:**
- snake_case (e.g., `connection_id`, `max_rows`)
- Private: underscore prefix (e.g., `_ensure_catalog_embedded()`)
- Constants: UPPER_SNAKE_CASE for true constants

**Types:**
- Pydantic models: PascalCase (e.g., `QueryPlan`, `FilterClause`)
- TypedDict: PascalCase (e.g., `GraphState`)
- Dataclasses: PascalCase

## Code Style

**Formatting:**
- Tool: Ruff
- Line length: 100 characters
- Target: Python 3.11

**Linting:**
- Tool: Ruff
- Rules enabled: E, F, I, N, UP, B
- E: pycodestyle errors
- F: pyflakes
- I: isort
- N: pep8 naming
- UP: pyupgrade
- B: flake8-bugbear

**Type Hints:**
- Use Python 3.11+ syntax (e.g., `list[str]` not `List[str]`)
- All async functions have `async def`
- Use `|` union syntax (e.g., `str | None`)

## Import Organization

**Order (per file):**
1. Standard library (`logging`, `uuid`, `datetime`)
2. Third-party (`fastapi`, `sqlalchemy`, `pytest`)
3. Local application (`app.core`, `app.llm`, `app.services`)

**Path Aliases:**
- Not used — relative imports within `app/` package

**Example:**
```python
import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base_connector import QueryResult
from app.core.exceptions import AppError
from app.services.query_service import execute_nl_query
```

## Error Handling

**Patterns:**
- Custom exceptions inherit from `AppError` (`app/core/exceptions.py`)
- Each exception has explicit `status_code` for HTTP mapping
- Use `try/except` with specific exception types

**Exception Classes:**
```python
class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(f"{resource} not found: {resource_id}", status_code=404)

class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)

class SQLSafetyError(AppError):
    def __init__(self, message: str):
        super().__init__(f"SQL safety violation: {message}", status_code=403)
```

**Handler Registration:**
- Registered in `app/core/exception_handlers.py`
- Registered via `register_exception_handlers(app)` in `main.py`

## Logging

**Framework:** loguru

**Configuration:**
- Set in `app/core/logging_config.py` (centralized setup_logging function)
- Called in `main.py` lifespan during startup
- Idempotent — safe to call in --reload mode

**Patterns:**
```python
from app.core.logging_config import setup_logging

setup_logging(
    app_name=settings.app_name.lower(),
    level="DEBUG" if settings.debug else settings.log_level,
    file_enabled=settings.log_file_enabled,
    rotation=settings.log_rotation,
    retention=settings.log_retention,
)
```

**Usage:**
- Use logger instance per module: `logger = logging.getLogger(__name__)`
- Structured logging with loguru: `logger.info("message %s", arg)`
- Error logging with exc_info: `logger.warning("failed", exc_info=True)`

## Comments

**When to Comment:**
- Explain WHY not WHAT
- Document non-obvious workarounds or decisions
- Use docstrings for public API functions

**Inline:**
```python
# Honor explicit clear_context flag
effective_context = None if clear_context else last_turn_context
```

**Docstrings (Google style):**
```python
async def execute_nl_query(
    db: AsyncSession,
    connection_id: uuid.UUID,
    question: str,
) -> dict:
    """Full pipeline: NL question → LangGraph → domain tool or LLM fallback → results.

    Delegates to the compiled LangGraph pipeline. Returns the same response
    dict shape as the original pipeline for API compatibility.

    Args:
        db: Database session.
        connection_id: Target database connection UUID.
        question: Natural language question.

    Returns:
        Dict with answer, highlights, suggested_followups, etc.
    """
```

## Function Design

**Size:** Small, focused functions preferred. Graph nodes in `app/llm/graph/nodes/` are typically 30-80 lines.

**Parameters:**
- Use TypedDict for graph state (`GraphState` in `app/llm/graph/state.py`)
- Explicit parameter names, no positional-only for public APIs

**Return Values:**
- Always return dict for graph nodes
- Graph node signature: `async def node_name(state: GraphState) -> dict[str, Any]`

## Module Design

**Exports:**
- Define `__all__` for public APIs (e.g., services, graph nodes)
- Pydantic models exported from `app/llm/graph/query_plan.py`

**Barrel Files:**
- Use `__init__.py` for public exports in each module
- Example: `app/llm/providers/__init__.py` exports provider registry

---

*Convention analysis: 2026-04-07*