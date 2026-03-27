---
created: 2026-03-27T06:49:27.340Z
title: Harden global exception handling and normalize error response shape
area: api
files:
  - backend/app/core/exception_handlers.py
  - backend/app/core/exceptions.py
  - backend/app/main.py
  - backend/app/llm/provider_registry.py
  - backend/app/connectors/connector_registry.py
  - backend/app/llm/graph/nodes/history_writer.py
  - backend/app/llm/graph/nodes/result_interpreter.py
  - backend/app/llm/graph/domains/registry.py
---

## Problem

The backend has a partial global exception handler (`core/exception_handlers.py`) that only catches `AppError` subclasses and returns `{"error": "..."}`. Two concrete gaps produce inconsistent API behaviour:

**1. No catch-all handler.**
Bare `ValueError`, `AssertionError`, and unguarded driver exceptions bubble up to FastAPI's default handler, which returns `{"detail": "Internal Server Error"}` — a different shape from the app's `{"error": "..."}` format. Clients must handle two response shapes.

**2. Specific unguarded paths that produce raw 500s with the wrong shape:**
- `connector_registry.get_connector_class()` raises `ValueError` for unknown connector types — not caught at the call site in `connection_service`
- `llm/provider_registry.get_provider()` raises `ValueError` for unknown providers — called from the full query pipeline with no wrapper
- `assert self._pool is not None` in all connectors raises `AssertionError` if the connector is used before `connect()`
- BigQuery non-timeout query errors are bare re-raises (not wrapped in `AppError`)
- LangGraph `history_writer` and `result_interpreter` nodes have no try/except — LLM/DB failures propagate out of `execute_nl_query` unhandled
- Several endpoints (`knowledge.py`, `schemas.py`) use `HTTPException` directly, producing `{"detail":...}` instead of `{"error":...}`

**3. Startup risk.**
`ensure_embedding_dimensions()` in the lifespan is a bare `await` — if the DB is unreachable at startup, the server aborts with no graceful error message.

## Solution

- Add a catch-all `Exception` handler in `exception_handlers.py` that normalizes all unhandled exceptions to `{"error": "An unexpected error occurred"}` (500), ensuring consistent response shape across all error paths
- Replace direct `HTTPException` usage in endpoints with `AppError` subclasses (or add an `HTTPException` handler that rewrites `{"detail":...}` to `{"error":...}`)
- Wrap `get_connector_class()` and `get_provider()` call sites to convert `ValueError` → `ValidationError` (422) with a user-readable message
- Add try/except around `ensure_embedding_dimensions()` in the lifespan with a startup warning log instead of a hard crash
- Add error isolation (try/except) to `history_writer` and `result_interpreter` LangGraph nodes so a failed history write or LLM interpretation doesn't abort the entire query response
- Replace `assert self._pool is not None` guards in connectors with explicit `if not self._pool: raise ConnectionError(...)` for consistent error type
