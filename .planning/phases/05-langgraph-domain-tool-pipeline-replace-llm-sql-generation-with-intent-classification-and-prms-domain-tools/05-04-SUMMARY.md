---
phase: 05-langgraph-domain-tool-pipeline
plan: 04
subsystem: api
tags: [langgraph, graph-assembly, result-interpreter, llm-fallback, write-history, fallback-intent, tdd, pytest]

# Dependency graph
requires:
  - phase: 05-01
    provides: GraphState TypedDict and 24-intent PRMS catalog
  - phase: 05-02
    provides: classify_intent, route_after_classify, extract_params nodes
  - phase: 05-03
    provides: BaseDomainAgent, 4 domain agents, DOMAIN_REGISTRY, run_domain_tool node
provides:
  - interpret_result node — wraps ResultInterpreterAgent, skips LLM when no rows returned
  - llm_fallback node — full LLM SQL generation pipeline (context → compose → validate → retry → execute)
  - write_history node — persists QueryExecution to app database with success/error status
  - run_fallback_intent node — re-runs sibling intent's SQL on 0-row result (1 hop max)
  - route_after_domain_tool + route_after_fallback_intent conditional edge functions
  - graph.py — compiled 7-node LangGraph StateGraph with get_compiled_graph() singleton accessor
  - 8 fully passing tests in test_graph_nodes.py and test_graph_pipeline.py
affects:
  - 05-05-wire-query-service

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD RED-GREEN cycle: test file written before implementation file created
    - Patch llm_fallback at graph.py usage site (app.llm.graph.graph.llm_fallback) not module definition site
    - get_compiled_graph() singleton — build once, reuse across requests
    - 0-row fallback chain: run_domain_tool → run_fallback_intent (1 hop) → llm_fallback

key-files:
  created:
    - backend/app/llm/graph/nodes/result_interpreter.py
    - backend/app/llm/graph/nodes/llm_fallback.py
    - backend/app/llm/graph/nodes/history_writer.py
    - backend/app/llm/graph/nodes/fallback_intent.py
    - backend/app/llm/graph/graph.py
  modified:
    - backend/tests/test_graph_nodes.py
    - backend/tests/test_graph_pipeline.py

key-decisions:
  - "Patch llm_fallback at app.llm.graph.graph.llm_fallback (usage site in graph.py) not app.llm.graph.nodes.llm_fallback.llm_fallback (definition site) — graph.py imports the function reference directly, so the patch must be at the consuming module"
  - "result_interpreter.py uses typed annotation sql: str = state.get('sql') or '' to satisfy type checker for str | None -> str coercion"

patterns-established:
  - "LangGraph node patch pattern: always patch at the consuming module (graph.py imports) not the defining module"
  - "0-row fallback chain: route_after_domain_tool checks fallback_intent presence, route_after_fallback_intent always bottoms out at llm_fallback (no chaining)"
  - "write_history uses execution_status='error' if error else 'success' — simple boolean on error field presence"

requirements-completed: [LG-11, LG-12, LG-13, LG-14]

# Metrics
duration: 5min
completed: 2026-03-26
---

# Phase 5 Plan 04: result_interpreter, llm_fallback, write_history Nodes + Complete Graph Assembly Summary

**Complete 7-node LangGraph StateGraph assembled and tested with interpret_result (LLM-skip on 0 rows), llm_fallback (full LLM pipeline), write_history (QueryExecution persistence), and run_fallback_intent (1-hop 0-row chain)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-26T08:02:45Z
- **Completed:** 2026-03-26T08:07:38Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Implemented `interpret_result`: calls `ResultInterpreterAgent.interpret()` when rows present, returns `answer=None, highlights=[]` when 0 rows — no LLM call
- Implemented `llm_fallback`: mirrors `query_service.execute_nl_query()` exactly — context build → compose → validate → retry loop → execute query
- Implemented `write_history`: saves `QueryExecution` with `execution_status="error"` or `"success"` based on error field; db.flush() for immediate ID assignment
- Implemented `run_fallback_intent`: looks up `fallback_intent` from INTENT_CATALOG, re-runs sibling intent's SQL via same domain agent (1 hop max, never chains)
- Assembled `graph.py` with `_build_graph()` and `get_compiled_graph()` singleton — all 7 nodes correctly wired with conditional edges
- 8 tests pass across two test files (GREEN phase)

## Task Commits

Each task was committed atomically (TDD produces 2 commits per task):

1. **Task 1 RED: Failing tests for result_interpreter, write_history** - `52eb4b4` (test)
2. **Task 1 GREEN: Implement result_interpreter, llm_fallback, write_history** - `3f0840b` (feat)
3. **Task 2 RED: Failing tests for graph pipeline** - `aa1c2c4` (test)
4. **Task 2 GREEN: Implement fallback_intent + graph.py** - `f0ba722` (feat)

**Plan metadata:** *(to be added)*

## Files Created/Modified
- `backend/app/llm/graph/nodes/result_interpreter.py` - interpret_result node wrapping ResultInterpreterAgent
- `backend/app/llm/graph/nodes/llm_fallback.py` - full LLM pipeline node (context → compose → validate → execute)
- `backend/app/llm/graph/nodes/history_writer.py` - write_history node persisting QueryExecution
- `backend/app/llm/graph/nodes/fallback_intent.py` - run_fallback_intent + route_after_domain_tool + route_after_fallback_intent
- `backend/app/llm/graph/graph.py` - complete 7-node StateGraph + get_compiled_graph() singleton
- `backend/tests/test_graph_nodes.py` - 4 tests replacing placeholder stub (interpret_result no-rows, with-rows, write_history success/error)
- `backend/tests/test_graph_pipeline.py` - 4 tests replacing placeholder stub (compiles, singleton, domain-tool path, 0-row→llm_fallback routing)

## Decisions Made
- Patched `llm_fallback` at `app.llm.graph.graph.llm_fallback` (usage site) instead of `app.llm.graph.nodes.llm_fallback.llm_fallback` (definition site). When `graph.py` imports `from app.llm.graph.nodes.llm_fallback import llm_fallback`, the reference is bound in graph.py's namespace. Patching the definition site after import has no effect — must patch where the reference lives.
- Used typed annotation `sql: str = state.get("sql") or ""` in result_interpreter.py to satisfy type checker — `TypedDict.get()` returns `T | None` even with a default value.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed llm_fallback test patch path to usage site in graph.py**
- **Found during:** Task 2 GREEN (first test run after creating graph.py)
- **Issue:** Plan's test patched `app.llm.graph.nodes.llm_fallback.llm_fallback` (definition site). However, `graph.py` does `from app.llm.graph.nodes.llm_fallback import llm_fallback`, binding the function to `graph.py`'s namespace. The mock had no effect — real `llm_fallback` was called, failing on MagicMock db session.
- **Fix:** Changed patch target to `app.llm.graph.graph.llm_fallback` (the binding in the consuming module)
- **Files modified:** `backend/tests/test_graph_pipeline.py`
- **Verification:** All 4 pipeline tests pass with mock in effect
- **Committed in:** `f0ba722` (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test isolation correctness. Same pattern as Plans 01 and 02 (patch at usage site, not definition site). No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 7 LangGraph nodes implemented and tested — Plan 05 can wire `get_compiled_graph().ainvoke(state)` into `query_service.py`
- `get_compiled_graph()` singleton ready for startup hook registration
- Full graph topology confirmed: classify_intent → [domain path with 0-row fallback chain] | [llm_fallback] → interpret_result → write_history → END

---
*Phase: 05-langgraph-domain-tool-pipeline*
*Completed: 2026-03-26*

## Self-Check: PASSED

- `backend/app/llm/graph/nodes/result_interpreter.py` found on disk ✅
- `backend/app/llm/graph/nodes/llm_fallback.py` found on disk ✅
- `backend/app/llm/graph/nodes/history_writer.py` found on disk ✅
- `backend/app/llm/graph/nodes/fallback_intent.py` found on disk ✅
- `backend/app/llm/graph/graph.py` found on disk ✅
- `backend/tests/test_graph_nodes.py` found on disk ✅
- `backend/tests/test_graph_pipeline.py` found on disk ✅
- Commits `52eb4b4`, `3f0840b`, `aa1c2c4`, `f0ba722` verified in git log ✅
- All 8 pytest tests pass ✅
- Graph has 7 nodes confirmed ✅
