---
phase: 05-langgraph-domain-tool-pipeline
plan: 01
subsystem: api
tags: [langgraph, langchain-core, graphstate, intent-catalog, embedding, testing]

# Dependency graph
requires: []
provides:
  - GraphState TypedDict with 24 annotated keys (inputs, classification, execution, interpretation, history, error)
  - INTENT_CATALOG with 24 intents across 4 domains (Resource×9, Client×5, Project×6, Timesheet×4)
  - IntentEntry dataclass with sql_fallback_template and fallback_intent placeholder fields
  - ensure_catalog_embedded() idempotent pre-embedding function
  - get_catalog_embeddings() accessor
  - 7 test scaffold files: conftest, graph_state, intent_catalog, intent_classifier, domain_agents, graph_nodes, graph_pipeline
affects:
  - 05-02-intent-classifier
  - 05-03-domain-agents
  - 05-04-graph-nodes
  - 05-05-wire-query-service

# Tech tracking
tech-stack:
  added:
    - langgraph>=0.2
    - langchain-core>=0.3
  patterns:
    - GraphState TypedDict as single shared state threaded through LangGraph pipeline
    - Static intent catalog with pre-embedding at startup (idempotent)
    - Monkeypatch embed_text at usage site (not definition site) for reliable test isolation

key-files:
  created:
    - backend/app/llm/graph/__init__.py
    - backend/app/llm/graph/state.py
    - backend/app/llm/graph/intent_catalog.py
    - backend/tests/conftest.py
    - backend/tests/test_graph_state.py
    - backend/tests/test_intent_catalog.py
    - backend/tests/test_intent_classifier.py
    - backend/tests/test_domain_agents.py
    - backend/tests/test_graph_nodes.py
    - backend/tests/test_graph_pipeline.py
  modified:
    - backend/pyproject.toml

key-decisions:
  - "Patching embed_text at app.llm.graph.intent_catalog.embed_text (usage site) not app.services.embedding_service.embed_text (definition site) to correctly mock already-imported references"
  - "Test for ensure_catalog_embedded idempotency resets _catalog_embedded global and clears embeddings to ensure test is deterministic regardless of run order"

patterns-established:
  - "GraphState TypedDict: 24 keys grouped by pipeline phase (inputs, classification, execution, interpretation, history, error)"
  - "Intent catalog: static list of IntentEntry dataclasses, pre-embedded at startup"
  - "Test scaffold pattern: placeholder stub tests in files that will be filled by future plans"

requirements-completed: [LG-01, LG-02, LG-03, LG-04]

# Metrics
duration: 4min
completed: 2026-03-26
---

# Phase 5 Plan 01: Feature Branch, GraphState, 24-Intent Catalog, and Test Scaffolding Summary

**LangGraph package dependencies added, GraphState TypedDict (24 keys) and 24-intent PRMS catalog defined, plus 7 test scaffold files with 10 passing tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-26T07:46:53Z
- **Completed:** 2026-03-26T07:51:15Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Added `langgraph>=0.2` and `langchain-core>=0.3` to `pyproject.toml` under `llm` extras
- Created `backend/app/llm/graph/` package with `GraphState` TypedDict (24 annotated keys covering inputs, classification, execution, interpretation, history, and error propagation)
- Built `INTENT_CATALOG` with exactly 24 intents across 4 domains (Resource×9, Client×5, Project×6, Timesheet×4) with `ensure_catalog_embedded()` and `get_catalog_embeddings()` helpers
- Scaffolded 7 test files; `test_graph_state.py` and `test_intent_catalog.py` have 9 real passing tests; 4 stub files provide placeholders for Plans 02-05

## Task Commits

Each task was committed atomically:

1. **Task 1: Create feature branch, add dependencies, define GraphState and intent catalog** - `0526a3e` (feat)
2. **Task 2: Create test scaffolding (7 test files with passing stubs)** - `1c51ff1` (feat)

**Plan metadata:** *(to be added)*

## Files Created/Modified
- `backend/pyproject.toml` - Added langgraph>=0.2 and langchain-core>=0.3 to llm extras
- `backend/app/llm/graph/__init__.py` - Package init (empty)
- `backend/app/llm/graph/state.py` - GraphState TypedDict with 24 annotated keys
- `backend/app/llm/graph/intent_catalog.py` - 24-entry INTENT_CATALOG, IntentEntry dataclass, ensure_catalog_embedded(), get_catalog_embeddings()
- `backend/tests/conftest.py` - Fixtures: mock_db, mock_query_result, mock_embed_text (with correct usage-site patch path)
- `backend/tests/test_graph_state.py` - Tests all 24 GraphState annotation keys are present
- `backend/tests/test_intent_catalog.py` - Tests catalog count, domain counts, unique names, valid domains, and idempotent embedding
- `backend/tests/test_intent_classifier.py` - Placeholder stub for Plan 02
- `backend/tests/test_domain_agents.py` - Placeholder stub for Plan 03
- `backend/tests/test_graph_nodes.py` - Placeholder stub for Plan 04
- `backend/tests/test_graph_pipeline.py` - Placeholder stub for Plans 04/05

## Decisions Made
- Patched `embed_text` at the usage site (`app.llm.graph.intent_catalog.embed_text`) rather than the definition site, since `intent_catalog.py` imports the function directly (`from app.services.embedding_service import embed_text`). Patching the definition site after the import has no effect.
- The idempotency test resets `_catalog_embedded` module global and clears all embeddings before each test run to ensure deterministic behavior regardless of test ordering.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed monkeypatch target path for embed_text fixture**
- **Found during:** Task 2 (test scaffolding verification run)
- **Issue:** `mock_embed_text` fixture patched `app.services.embedding_service.embed_text` but `intent_catalog.py` already imported `embed_text` directly, so the mock had no effect — the real Ollama endpoint was called and failed with ConnectionError
- **Fix:** Changed monkeypatch target to `app.llm.graph.intent_catalog.embed_text` (where the reference lives after import). Also added `_catalog_embedded` global reset and embedding list clear in the idempotency test for deterministic ordering.
- **Files modified:** `backend/tests/conftest.py`, `backend/tests/test_intent_catalog.py`
- **Verification:** `pytest tests/test_intent_catalog.py -x -q` → 5 passed
- **Committed in:** `1c51ff1` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- GraphState contract locked — Plan 02 can write classifier against it immediately
- INTENT_CATALOG locked — Plan 02 can use it for cosine similarity routing
- Test stub files in place — Plans 02-05 can fill them out without file creation overhead
- `ensure_catalog_embedded()` designed to be called from startup hook (Plan 05)

---
*Phase: 05-langgraph-domain-tool-pipeline*
*Completed: 2026-03-26*

## Self-Check: PASSED

- All 10 key files found on disk ✅
- Commits `0526a3e` and `1c51ff1` verified in git log ✅
- All 10 pytest tests pass ✅
