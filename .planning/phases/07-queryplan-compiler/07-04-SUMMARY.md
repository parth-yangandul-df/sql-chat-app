---
phase: 07-queryplan-compiler
plan: "04"
subsystem: api
tags: [semantic-layer, glossary, dictionary, value_map, metrics, sql-compiler, langraph, python]

# Dependency graph
requires:
  - phase: 07-queryplan-compiler
    provides: filter_extractor, plan_updater, sql_compiler, QueryPlan, FieldRegistry (Plans 01-03)
provides:
  - semantic_resolver.py with resolve_glossary_hints(), load_value_map(), normalize_value(), normalize_values_batch()
  - MetricFragment dataclass in sql_compiler.py with select_expr, join_clause, requires_group_by
  - detect_metrics() keyword-matching stub in sql_compiler.py
  - filter_extractor.py wired to call resolve_glossary_hints() with graceful degradation
  - plan_updater.py wired to normalize filter values through get_cached_value_map()
  - 27 semantic wiring unit tests in test_semantic_wiring.py
  - 4 end-to-end integration tests in test_queryplan_integration.py (total: 13)
affects: [07-queryplan-compiler, future-llm-metric-detection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level value_map cache: load_value_map() populates _value_map_cache, get_cached_value_map() returns it — zero per-query DB hits"
    - "Lazy try/import pattern for cross-node dependencies: avoids circular imports, enables test isolation via patch"
    - "Type-aware normalization: normalize_values_batch() skips date/numeric/boolean fields, only normalizes text fields"
    - "GROUP BY injection via _inject_group_by(): parses SELECT list, strips aggregation functions and aliases, appends GROUP BY"
    - "Graceful degradation everywhere: DB unavailability returns empty hints/map, never raises"

key-files:
  created:
    - backend/app/llm/graph/nodes/semantic_resolver.py
    - backend/tests/test_semantic_wiring.py
  modified:
    - backend/app/llm/graph/nodes/filter_extractor.py
    - backend/app/llm/graph/nodes/plan_updater.py
    - backend/app/llm/graph/nodes/sql_compiler.py
    - backend/tests/test_queryplan_integration.py

key-decisions:
  - "semantic_resolver uses lazy import of GlossaryTerm/DictionaryEntry inside functions — keeps import at usage site, avoids circular import with graph nodes"
  - "value_map cache keyed by column_name.lower() not field_name — dictionary entries are column-centric, not field-centric"
  - "normalize_values_batch skips non-text fields by checking FIELD_REGISTRY sql_type — prevents date/numeric fields being misinterpreted as human vocabulary"
  - "MetricFragment is a @dataclass not Pydantic model — pure data container, not user-facing API"
  - "_inject_group_by() parses SELECT list naively by comma split, strips aliases — sufficient for structured BASE_QUERIES templates"
  - "detect_metrics() returns [] stub — full LLM detection deferred; structure ready for future implementation"
  - "filter_extractor imports resolve_glossary_hints via try/except at module level — patch target is filter_extractor.resolve_glossary_hints (not semantic_resolver.resolve_glossary_hints)"

patterns-established:
  - "Semantic layer wiring: resolve at node-level, degrade to empty/unchanged on error, log WARNING not raise"
  - "Module-level cache pattern for startup-loaded data: populate once via async load_*(), access synchronously via get_cached_*()"

requirements-completed:
  - QP-04

# Metrics
duration: 45min
completed: 2026-04-06
---

# Phase 7 Plan 04: Semantic Resolver + MetricFragment Injection Summary

**semantic_resolver.py bridges glossary/dictionary/metric semantic layer into QueryPlan compiler pipeline via glossary field hints, value_map normalization cache, and MetricFragment injection with GROUP BY support**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-04-06T08:00:00Z
- **Completed:** 2026-04-06T08:45:00Z
- **Tasks:** 4 (TDD for 4.1, 4.2, 4.3; standard for 4.4)
- **Files modified:** 6

## Accomplishments

- Created `semantic_resolver.py` with 5 functions: resolve_glossary_hints(), load_value_map(), get_cached_value_map(), normalize_value(), normalize_values_batch()
- Wired glossary hints into filter_extractor.py (called before regex extraction, degrades gracefully)
- Wired value_map normalization into plan_updater.py (after LLM-fallback check, before accumulation)
- Added MetricFragment @dataclass + detect_metrics() stub + _inject_group_by() to sql_compiler.py
- 27 semantic wiring unit tests + 4 integration tests all pass; zero regressions in 274-test suite

## Task Commits

Each task was committed atomically:

1. **Task 4.1 (RED):** `06ee493` (test) — 538-line failing test file for semantic_resolver, metrics, wiring
2. **Task 4.1 (GREEN):** `dd04aa3` (feat) — semantic_resolver.py with all 5 functions
3. **Task 4.2:** `e298470` (feat) — wire glossary hints into filter_extractor, value_map into plan_updater
4. **Task 4.3:** `dff9f1c` (feat) — MetricFragment, detect_metrics(), _inject_group_by() in sql_compiler
5. **Task 4.4:** `269a094` (feat) — 4 end-to-end integration tests in test_queryplan_integration.py

**Plan metadata:** `(docs commit — see below)`

## Files Created/Modified

- `backend/app/llm/graph/nodes/semantic_resolver.py` — New: resolve_glossary_hints(), load_value_map(), get_cached_value_map(), normalize_value(), normalize_values_batch()
- `backend/app/llm/graph/nodes/filter_extractor.py` — Modified: lazy import + glossary hint resolution call in extract_filters()
- `backend/app/llm/graph/nodes/plan_updater.py` — Modified: lazy import + value_map normalization in update_query_plan()
- `backend/app/llm/graph/nodes/sql_compiler.py` — Modified: MetricFragment dataclass, detect_metrics() stub, updated compile_query() with metric injection, _inject_group_by() helper
- `backend/tests/test_semantic_wiring.py` — New: 27 unit tests covering all semantic_resolver functions + filter_extractor/plan_updater wiring + MetricFragment
- `backend/tests/test_queryplan_integration.py` — Modified: 4 new end-to-end integration tests (total 13)

## Decisions Made

1. **value_map cache keyed by column_name.lower()** — dictionary entries are column-centric (DictionaryEntry→CachedColumn.column_name), not field-centric. normalize_value() uses field as secondary key but looks up via column name
2. **normalize_values_batch skips non-text fields** — checks FIELD_REGISTRY sql_type; date/numeric/boolean fields pass through unchanged preventing misinterpretation
3. **Lazy try/import in filter_extractor and plan_updater** — enables test isolation via `patch("app.llm.graph.nodes.filter_extractor.resolve_glossary_hints", ...)` at usage-site rather than definition-site
4. **detect_metrics() returns [] stub** — keyword detection structure in place for future LLM-based detection; not blocking on unimplemented detection
5. **{select_extras} uses comma prefix** — fixed token replacement to use `", {expr}"` format so metric expressions cleanly append to existing SELECT columns

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed {select_extras} token replacement to use comma prefix**
- **Found during:** Task 4.3 (MetricFragment injection)
- **Issue:** Original sql_compiler replaced `{select_extras}` with raw string; needed comma prefix (", expr") to cleanly separate from base SELECT columns
- **Fix:** Changed replacement logic to `select_token = f", {select_extras}" if select_extras else ""`
- **Files modified:** backend/app/llm/graph/nodes/sql_compiler.py
- **Verification:** All sql_compiler tests pass (30 tests), metric injection tests pass
- **Committed in:** dff9f1c (Task 4.3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Comma prefix fix necessary for correct SQL generation. No scope creep.

## Issues Encountered

None — plan executed cleanly. All 4 tasks completed, 274 tests passing (31 new tests added).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Semantic layer fully wired into QueryPlan compiler pipeline
- semantic_resolver.py ready; load_value_map() should be called from main.py lifespan on startup to pre-warm cache
- Phase 07 complete — all 4 plans (07-01 through 07-04) executed successfully
- QueryPlan compiler pipeline fully operational: filter extraction → plan accumulation with value_map normalization → SQL compilation with metric injection

---
*Phase: 07-queryplan-compiler*
*Completed: 2026-04-06*

## Self-Check: PASSED

- ✅ `backend/app/llm/graph/nodes/semantic_resolver.py` — FOUND
- ✅ `backend/tests/test_semantic_wiring.py` — FOUND
- ✅ `.planning/phases/07-queryplan-compiler/07-04-SUMMARY.md` — FOUND
- ✅ Commits `06ee493`, `dd04aa3`, `e298470`, `dff9f1c`, `269a094` — all verified
- ✅ 274 tests pass (243 original + 27 semantic wiring + 4 integration = 274)
