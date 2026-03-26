---
phase: 05-langgraph-domain-tool-pipeline
plan: 05
subsystem: api
tags: [langgraph, query-service, integration, startup-hook, tdd, pytest]

# Dependency graph
requires:
  - phase: 05-04
    provides: compiled 7-node LangGraph StateGraph via get_compiled_graph()
  - phase: 05-01
    provides: GraphState TypedDict, ensure_catalog_embedded()
provides:
  - execute_nl_query() delegating entirely to get_compiled_graph().ainvoke()
  - main.py lifespan calling ensure_catalog_embedded() before first request
  - 3 new integration tests verifying response shape, domain_tool provider, and error propagation
affects:
  - All NL query requests through the running FastAPI app

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD RED-GREEN cycle: 3 failing tests committed before implementation
    - Patch at usage site (app.services.query_service.get_compiled_graph) not definition site

# Files tracking
key-files:
  modified:
    - path: backend/app/services/query_service.py
      role: execute_nl_query() replaced with LangGraph invocation; generate_sql_only and execute_raw_sql untouched
    - path: backend/app/main.py
      role: lifespan hook adds ensure_catalog_embedded() after ensure_embedding_dimensions()
    - path: backend/tests/test_graph_pipeline.py
      role: 3 new integration tests appended (response keys, domain_tool provider, error raises)

# Decisions
decisions:
  - "Kept all old imports (QueryComposerAgent, SQLValidatorAgent, etc.) in query_service.py — they are still used by generate_sql_only() and execute_raw_sql()"
  - "ensure_catalog_embedded() placed between ensure_embedding_dimensions() and auto_setup_sample_db() — embeddings must be ready before any seeded data could trigger a query"

# Metrics
metrics:
  duration: ~8 minutes
  completed: 2026-03-26
  tasks_completed: 2
  commits: 2
  files_changed: 3
---

# Phase 05 Plan 05: Wire Query Service + Startup Hook Summary

**One-liner:** `execute_nl_query()` now delegates entirely to LangGraph's compiled StateGraph, with intent catalog pre-embedded at startup before the first request.

## What Was Built

### Task 1 — Replace `execute_nl_query()` with LangGraph invocation + startup hook

**RED commit** (`60a63b9`): Three failing tests added to `test_graph_pipeline.py`:
- `test_execute_nl_query_response_keys` — patched `get_compiled_graph` raises `AttributeError` (attribute didn't exist yet)
- `test_execute_nl_query_domain_tool_provider` — same failure
- `test_execute_nl_query_error_raises` — same failure

**GREEN commit** (`65d1c08`):

`backend/app/services/query_service.py`:
- Added `from app.llm.graph.graph import get_compiled_graph` and `from app.llm.graph.state import GraphState`
- Replaced 180-line `execute_nl_query()` body with a clean 50-line LangGraph delegation:
  - Builds `GraphState` initial dict with all required fields
  - Calls `await get_compiled_graph().ainvoke(initial_state)`
  - Maps `final_state` → identical 17-key response dict as original pipeline
  - Raises `AppError` when `final_state["error"]` is set and `result` is `None`
- `generate_sql_only()`, `execute_raw_sql()`, `_serialize_rows()` — **completely untouched**

`backend/app/main.py`:
- Added `ensure_catalog_embedded()` call in lifespan between `ensure_embedding_dimensions()` and `auto_setup_sample_db()`
- Intent catalog pre-embedded at startup → first NL query pays no embedding cost

### Task 2 — Full pipeline integration tests

Three new tests in `test_graph_pipeline.py`, all passing:

| Test | What It Verifies |
|------|-----------------|
| `test_execute_nl_query_response_keys` | All 17 original response dict keys present |
| `test_execute_nl_query_domain_tool_provider` | `llm_provider="domain_tool"`, `llm_model=intent_name`, `generated_sql=None`, `explanation=None` |
| `test_execute_nl_query_error_raises` | `AppError` raised when graph returns error with no result |

## Test Results

```
92 passed in 2.87s
```

All Phase 5 tests green. No regressions.

## Response Dict Shape (preserved exactly)

```python
{
    "id": final_state.get("execution_id"),
    "question": question,
    "generated_sql": final_state.get("generated_sql"),   # None for domain tool path
    "final_sql": final_state.get("sql"),
    "explanation": final_state.get("explanation"),        # None for domain tool path
    "columns": result.columns,
    "column_types": result.column_types,
    "rows": _serialize_rows(result.rows),
    "row_count": result.row_count,
    "execution_time_ms": result.execution_time_ms,
    "truncated": result.truncated,
    "summary": final_state.get("answer"),
    "highlights": final_state.get("highlights", []),
    "suggested_followups": final_state.get("suggested_followups", []),
    "llm_provider": final_state.get("llm_provider"),     # "domain_tool" or provider name
    "llm_model": final_state.get("llm_model"),           # intent_name or model name
    "retry_count": final_state.get("retry_count", 0),
}
```

## Startup Lifespan Order (main.py)

```
1. ensure_embedding_dimensions()   → resize vector columns if provider switched
2. ensure_catalog_embedded()       → pre-embed 24 intent catalog entries (idempotent)
3. auto_setup_sample_db()          → seed IFRS9 sample DB (if AUTO_SETUP_SAMPLE_DB=true)
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `backend/app/services/query_service.py` | FOUND |
| `backend/app/main.py` | FOUND |
| `backend/tests/test_graph_pipeline.py` | FOUND |
| `05-05-SUMMARY.md` | FOUND |
| Commit `60a63b9` (RED tests) | FOUND |
| Commit `65d1c08` (GREEN impl) | FOUND |
| 92 tests pass | ✅ |
