---
phase: 05-langgraph-domain-tool-pipeline
plan: 02
subsystem: api
tags: [langgraph, intent-classifier, cosine-similarity, regex, param-extractor, tdd, pytest]

# Dependency graph
requires:
  - phase: 05-01
    provides: GraphState TypedDict, INTENT_CATALOG (24 intents), ensure_catalog_embedded(), get_catalog_embeddings(), test scaffold files
provides:
  - classify_intent async node — embeds question, cosine similarity over 24-intent catalog, returns domain/intent/confidence
  - route_after_classify edge function — gates on TOOL_CONFIDENCE_THRESHOLD, returns "extract_params" or "llm_fallback"
  - extract_params async node — regex/keyword extractor for skill, start_date, end_date, resource_name (no LLM)
  - backend/app/llm/graph/nodes/ package with __init__.py
  - 8 fully passing tests replacing placeholder stub in test_intent_classifier.py
affects:
  - 05-03-domain-agents
  - 05-04-graph-nodes
  - 05-05-wire-query-service

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Patch ensure_catalog_embedded at usage site (not embed_text only) to prevent real Ollama calls when catalog has no embeddings
    - get_catalog_embeddings patched alongside embed_text for full isolation of cosine similarity tests
    - TDD RED-GREEN per node: test file updated before implementation file created

key-files:
  created:
    - backend/app/llm/graph/nodes/__init__.py
    - backend/app/llm/graph/nodes/intent_classifier.py
    - backend/app/llm/graph/nodes/param_extractor.py
  modified:
    - backend/tests/test_intent_classifier.py

key-decisions:
  - "Patch ensure_catalog_embedded (not just embed_text) in test mocks — classify_intent calls ensure_catalog_embedded() when any catalog entry has no embedding, which uses intent_catalog.embed_text (a different import path)"
  - "extract_params is async to conform to LangGraph node signature convention even though it makes no async calls"

patterns-established:
  - "Intent classifier test pattern: patch embed_text + ensure_catalog_embedded + get_catalog_embeddings all at intent_classifier usage site"
  - "Param extractor: pure regex, no LLM, no DB — fastest node in the pipeline"

requirements-completed: [LG-05, LG-06]

# Metrics
duration: 4min
completed: 2026-03-26
---

# Phase 5 Plan 02: Intent Classifier and Param Extractor Nodes Summary

**classify_intent (cosine similarity over 24-intent catalog) and extract_params (regex skill/date/name extractor) implemented with 8 passing TDD tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-26T07:54:22Z
- **Completed:** 2026-03-26T07:58:33Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `backend/app/llm/graph/nodes/` package with `__init__.py`
- Implemented `classify_intent`: embeds question, computes cosine similarity against all 24 catalog entries, returns best `domain`/`intent`/`confidence`; logs INFO for domain tool route and WARNING for fallback
- Implemented `route_after_classify`: reads `confidence` from state, returns `"extract_params"` if ≥ `TOOL_CONFIDENCE_THRESHOLD` (default 0.78), else `"llm_fallback"`
- Implemented `extract_params`: regex-only extractor for `skill`, `start_date`, `end_date`, `resource_name`; returns empty `params={}` when no match
- 8 tests pass (up from 1 placeholder stub) covering all routing branches and extractor patterns

## Task Commits

Each task was committed atomically (TDD produces 2 commits per task):

1. **Task 1 RED: Failing tests for classify_intent + route_after_classify** - `7c86925` (test)
2. **Task 1 GREEN: Implement classify_intent + route_after_classify** - `f20ba3b` (feat)
3. **Task 2 RED: Failing tests for extract_params** - `8c007db` (test)
4. **Task 2 GREEN: Implement extract_params** - `0dd3fc3` (feat)

**Plan metadata:** *(to be added)*

## Files Created/Modified
- `backend/app/llm/graph/nodes/__init__.py` - Package init (empty)
- `backend/app/llm/graph/nodes/intent_classifier.py` - classify_intent node + route_after_classify edge + _cosine helper
- `backend/app/llm/graph/nodes/param_extractor.py` - extract_params regex extractor (_SKILL_RE, _DATE_RE, _NAME_RE)
- `backend/tests/test_intent_classifier.py` - 8 real tests replacing placeholder stub

## Decisions Made
- Patched `ensure_catalog_embedded` in addition to `embed_text` and `get_catalog_embeddings` — `classify_intent` calls `ensure_catalog_embedded()` when catalog has empty embeddings, which goes through `intent_catalog.embed_text` (separate import path from `nodes.intent_classifier.embed_text`). Without patching ensure, the test triggered a real Ollama connection.
- `extract_params` is `async` to conform to LangGraph node convention even though it performs no I/O.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tests needed ensure_catalog_embedded patched to prevent real Ollama calls**
- **Found during:** Task 1 GREEN (first test run)
- **Issue:** Plan's test code only patched `embed_text` and `get_catalog_embeddings` at intent_classifier. `classify_intent` calls `ensure_catalog_embedded()` when any catalog entry has no embedding; that function internally calls `app.llm.graph.intent_catalog.embed_text` (a different binding). The unpatched path triggered a real Ollama HTTP call → `ConnectionError`.
- **Fix:** Added `patch("app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded", AsyncMock())` to both async test contexts.
- **Files modified:** `backend/tests/test_intent_classifier.py`
- **Verification:** All 8 tests pass with no network calls
- **Committed in:** `f20ba3b` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test isolation correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `classify_intent`, `route_after_classify`, and `extract_params` are importable and tested — Plan 03 (domain agents) can wire them in immediately
- Routing gate threshold (TOOL_CONFIDENCE_THRESHOLD=0.78) is env-var-configurable
- Test helpers (`_base_state()`) in test_intent_classifier.py can be reused or extended by Plan 04/05

---
*Phase: 05-langgraph-domain-tool-pipeline*
*Completed: 2026-03-26*

## Self-Check: PASSED

- `backend/app/llm/graph/nodes/__init__.py` found on disk ✅
- `backend/app/llm/graph/nodes/intent_classifier.py` found on disk ✅
- `backend/app/llm/graph/nodes/param_extractor.py` found on disk ✅
- `backend/tests/test_intent_classifier.py` found on disk ✅
- Commits `7c86925`, `f20ba3b`, `8c007db`, `0dd3fc3` verified in git log ✅
- All 8 pytest tests pass ✅
