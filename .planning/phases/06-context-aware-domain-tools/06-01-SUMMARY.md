---
phase: 06-context-aware-domain-tools
plan: "01"
subsystem: api
tags: [pydantic, graphstate, turn-context, query-pipeline, backward-compat]

# Dependency graph
requires: []
provides:
  - "TurnContext Pydantic model in backend/app/api/v1/schemas/query.py"
  - "last_turn_context field in GraphState TypedDict"
  - "turn_context returned in query_service response dict"
  - "Endpoint wired to pass last_turn_context through pipeline"
affects:
  - 06-context-aware-domain-tools

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TurnContext as the shared data contract for inter-turn context passing"
    - "dict | None in GraphState for TurnContext (avoids circular import at graph layer)"
    - "Conditional turn_context construction: only populated when intent + domain both resolved"

key-files:
  created:
    - backend/tests/test_turn_context_schema.py
  modified:
    - backend/app/api/v1/schemas/query.py
    - backend/app/llm/graph/state.py
    - backend/app/services/query_service.py
    - backend/app/api/v1/endpoints/query.py
    - backend/tests/test_graph_state.py
    - backend/tests/test_graph_pipeline.py

key-decisions:
  - "GraphState stores last_turn_context as dict | None (not TurnContext) to avoid importing Pydantic models into the graph layer — schemas layer serializes to dict before handing off"
  - "turn_context in response dict is conditionally populated: None when neither intent nor domain are resolved (i.e., LLM fallback path with no classification)"

patterns-established:
  - "TurnContext fields: intent (str), domain (str), params (dict), columns (list[str]), sql (str)"
  - "Endpoint serializes: body.last_turn_context.model_dump() if body.last_turn_context else None"

requirements-completed:
  - CTX-01
  - CTX-05

# Metrics
duration: 6min
completed: "2026-03-31"
---

# Phase 6 Plan 01: TurnContext Data Contract Summary

**TurnContext Pydantic model added to schemas with last_turn_context flowing API→GraphState→pipeline and turn_context returned in query response**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-31T12:20:24Z
- **Completed:** 2026-03-31T12:26:27Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `TurnContext` Pydantic model (intent, domain, params, columns, sql) to `schemas/query.py`
- Extended `QueryRequest` with `last_turn_context: TurnContext | None = None` (backward compatible — existing callers unaffected)
- Extended `QueryResponse` with `turn_context: TurnContext | None = None`
- Added `last_turn_context: dict | None` to `GraphState` TypedDict
- Extended `execute_nl_query()` to accept, pass through, and return `last_turn_context`/`turn_context`
- Wired endpoint to serialize `body.last_turn_context.model_dump()` before passing to service
- 5 new schema tests + updated 2 existing tests to match new contract

## Task Commits

1. **Task 1: Add TurnContext model + extend QueryRequest/QueryResponse** - `eb4ac9b` (feat)
2. **Task 2: Wire last_turn_context through GraphState, query_service, endpoint** - `797ce5b` (feat)

## Files Created/Modified

- `backend/app/api/v1/schemas/query.py` — TurnContext model; last_turn_context on QueryRequest; turn_context on QueryResponse
- `backend/app/llm/graph/state.py` — last_turn_context: dict | None field added to GraphState
- `backend/app/services/query_service.py` — last_turn_context param; initial_state entry; turn_context in return dict
- `backend/app/api/v1/endpoints/query.py` — pass last_turn_context.model_dump() through to execute_nl_query()
- `backend/tests/test_turn_context_schema.py` — 5 new tests for TurnContext schema contract
- `backend/tests/test_graph_state.py` — added last_turn_context to required key set
- `backend/tests/test_graph_pipeline.py` — added turn_context to EXPECTED_RESPONSE_KEYS

## Decisions Made

- **GraphState uses `dict | None`** — not `TurnContext` — to avoid importing Pydantic models into the graph layer. The endpoint converts `TurnContext` to dict via `.model_dump()` before entry.
- **Conditional turn_context**: only populated in the response when both `intent` and `domain` are resolved in final_state. If the LLM fallback path runs (no classification), `turn_context` is `None`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated EXPECTED_RESPONSE_KEYS in test_graph_pipeline.py**
- **Found during:** Task 2 verification (pytest run)
- **Issue:** `test_execute_nl_query_response_keys` asserted exact key set of response dict; our new `turn_context` key caused mismatch
- **Fix:** Added `"turn_context"` to `EXPECTED_RESPONSE_KEYS` set
- **Files modified:** `backend/tests/test_graph_pipeline.py`
- **Verification:** All 100 tests pass
- **Committed in:** `797ce5b` (Task 2 commit)

**2. [Rule 1 - Bug] Updated test_graph_state_keys in test_graph_state.py**
- **Found during:** Task 2 verification (pytest run)
- **Issue:** `test_graph_state_keys` asserted exact annotation key set of GraphState; our new `last_turn_context` field caused mismatch
- **Fix:** Added `"last_turn_context"` to required set (with comment "# Phase 6 context passing")
- **Files modified:** `backend/tests/test_graph_state.py`
- **Verification:** All 100 tests pass
- **Committed in:** `797ce5b` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 - Bug)
**Impact on plan:** Both auto-fixes were necessary to keep test suite green after adding new fields to GraphState and response dict. No scope creep.

## Issues Encountered

None — plan executed with only minor test update deviations as expected when adding new contract fields.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TurnContext contract is fully established and tested
- Plans 02-04 can now read `state["last_turn_context"]` from GraphState in any pipeline node
- Plan 05 (frontend) can read `turn_context` from the query API response
- `generate_sql_only()` and `execute_raw_sql()` remain untouched as specified

---
*Phase: 06-context-aware-domain-tools*
*Completed: 2026-03-31*
