---
phase: 07-queryplan-compiler
plan: 01
subsystem: api
tags: [pydantic, query-plan, feature-flag, langgraph, sql-sanitization]

# Dependency graph
requires:
  - phase: 06-context-aware-domain-tools
    provides: GraphState TypedDict with last_turn_context pattern, query_service turn_context wiring
provides:
  - QueryPlan and FilterClause Pydantic v2 models with validation and SQL injection guards
  - USE_QUERY_PLAN_COMPILER feature flag in Settings
  - query_plan: dict | None field in GraphState
  - QueryPlan deserialization and serialization through query_service
affects:
  - 07-02-queryplan-compiler (next plan — filter extractor uses QueryPlan model)
  - 07-03, 07-04 (SQL compiler and semantic wiring depend on this contract)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase 7 pattern: QueryPlan stored as dict | None in GraphState (consistent with last_turn_context)"
    - "from_untrusted_dict() classmethod for safe deserialization of external/LLM-provided data"
    - "Feature flag pattern: use_query_plan_compiler bool in Settings for migration-safe rollout"

key-files:
  created:
    - backend/app/llm/graph/query_plan.py
    - backend/tests/test_query_plan_model.py
  modified:
    - backend/app/config.py
    - backend/app/llm/graph/state.py
    - backend/app/services/query_service.py
    - backend/tests/test_graph_state.py

key-decisions:
  - "QueryPlan serialized as dict | None in GraphState (not as Pydantic object) — consistent with Phase 6 last_turn_context pattern avoiding Pydantic imports in graph layer"
  - "SQL injection guard includes single quote (') — original plan regex missed it; test caught this as a bug"
  - "query_service passes through whatever graph produces without checking feature flag — flag is for upstream nodes to check"
  - "base_sql construction gracefully falls back to _prior_sql/sql when QueryPlan deserialization fails"

patterns-established:
  - "Pattern: QueryPlan.from_untrusted_dict() + try/except in service layer for safe deserialization"
  - "Pattern: Feature flags in Settings with env var auto-mapping via pydantic-settings"

requirements-completed:
  - QP-01

# Metrics
duration: 20min
completed: 2026-04-06
---

# Phase 07 Plan 01: QueryPlan Foundation Summary

**QueryPlan and FilterClause Pydantic v2 models with SQL injection guards, USE_QUERY_PLAN_COMPILER feature flag, GraphState field, and query_service deserialization wiring**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-06T11:46:00Z
- **Completed:** 2026-04-06T12:06:51Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `FilterClause` model with op validation (eq/in/lt/gt/between), 50-item limit, and SQL injection sanitization
- `QueryPlan` model with `from_untrusted_dict()` classmethod (rejects unknown keys, coerces single strings) and `to_api_dict()` method
- `USE_QUERY_PLAN_COMPILER` feature flag in Settings, defaulting to False
- `query_plan: dict | None` added to GraphState TypedDict
- `query_service.py` wired: QueryPlan deserialization for base_sql, query_plan included in turn_context, graceful fallback when None

## Task Commits

Each task was committed atomically:

1. **Task 1.1: Create QueryPlan and FilterClause Pydantic models** - `3acbb2c` (feat)
2. **Task 1.2: Add feature flag to Settings and query_plan to GraphState** - `debe60a` (feat)
3. **Task 1.3: Update query_service.py for QueryPlan deserialization and serialization** - `524490b` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `backend/app/llm/graph/query_plan.py` — FilterClause + QueryPlan models with SQL injection guard, from_untrusted_dict, to_api_dict
- `backend/tests/test_query_plan_model.py` — 18 tests covering all model validation, feature flag, and GraphState field
- `backend/app/config.py` — Added `use_query_plan_compiler: bool = False` setting
- `backend/app/llm/graph/state.py` — Added `query_plan: dict | None` to GraphState TypedDict
- `backend/app/services/query_service.py` — QueryPlan import, initial_state default, base_sql deserialization, turn_context inclusion
- `backend/tests/test_graph_state.py` — Updated GraphState keys whitelist to include query_plan

## Decisions Made

- **QueryPlan stored as dict (not Pydantic object) in GraphState** — Follows the Phase 6 pattern where `last_turn_context` is also `dict | None`. Avoids importing Pydantic models into the graph state layer, keeps the TypedDict serializable.
- **Feature flag not checked in query_service** — `query_service.py` just passes through whatever the graph produces. The flag is for upstream nodes (filter extractor, SQL compiler) to decide whether to populate `query_plan` in graph state. This keeps service-layer concerns separate.
- **Graceful fallback on QueryPlan deserialization failure** — If `from_untrusted_dict()` raises (e.g. corrupted state), `base_sql` falls back to the existing `_prior_sql → sql` path. Zero behavioral change for the current pipeline where `query_plan` is always None.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SQL injection sanitizer regex missing single quote**
- **Found during:** Task 1.1 verification (`pytest tests/test_query_plan_model.py -xvs`)
- **Issue:** `_SQL_DANGEROUS_TOKENS` regex in `query_plan.py` did not include `'` (single quote). Test `test_sql_injection_characters_sanitized` asserted that `'` should be stripped from filter values, but the implementation left it in.
- **Fix:** Added `'` to the `_SQL_DANGEROUS_TOKENS` regex pattern: `r"(;|'|--|/\*|\*/|DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE)"`
- **Files modified:** `backend/app/llm/graph/query_plan.py`
- **Verification:** All 15 model tests passed after fix
- **Committed in:** `3acbb2c` (Task 1.1 commit)

**2. [Rule 1 - Bug] test_graph_state.py whitelist missing query_plan key**
- **Found during:** Task 1.3 verification (full test suite run)
- **Issue:** `tests/test_graph_state.py::test_graph_state_keys` maintains an exact whitelist of GraphState keys. Adding `query_plan` to GraphState caused this test to fail with "Extra items in the right set: 'query_plan'".
- **Fix:** Added `"query_plan"` to the required set in `test_graph_state.py` with a Phase 7 comment.
- **Files modified:** `backend/tests/test_graph_state.py`
- **Verification:** All 164 tests pass after fix
- **Committed in:** `524490b` (Task 1.3 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 - Bug)
**Impact on plan:** Both were minor correctness fixes caught by tests. The SQL injection guard fix was a pre-existing bug in the created file; the GraphState whitelist update was a necessary consequence of adding a new field.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- QueryPlan contract is stable and validated — ready for Plan 07-02 (filter extractor LLM node)
- Feature flag defaults to False — existing pipeline behavior unchanged until Phase 7 nodes are wired
- GraphState has the `query_plan` field ready for Phase 7 nodes to write into

---
*Phase: 07-queryplan-compiler*
*Completed: 2026-04-06*

## Self-Check: PASSED

- FOUND: backend/app/llm/graph/query_plan.py
- FOUND: backend/tests/test_query_plan_model.py
- FOUND: backend/app/config.py
- FOUND: backend/app/llm/graph/state.py
- FOUND: backend/app/services/query_service.py
- FOUND: .planning/phases/07-queryplan-compiler/07-01-SUMMARY.md
- FOUND: commit 3acbb2c (Task 1.1)
- FOUND: commit debe60a (Task 1.2)
- FOUND: commit 524490b (Task 1.3)
