---
phase: 06-context-aware-domain-tools
plan: "03"
subsystem: api
tags: [langgraph, intent-classifier, param-extractor, regex, follow-up-detection, refine-mode, tdd]

# Dependency graph
requires:
  - phase: 06-context-aware-domain-tools
    plan: "01"
    provides: "last_turn_context field in GraphState + TurnContext data contract"
provides:
  - "_is_refinement_followup() helper in intent_classifier.py for deictic follow-up detection"
  - "classify_intent() fast path: skip embedding → inherit prior domain/intent at confidence=0.95"
  - "extract_params() param carry-forward from prior turn (new values win on conflict)"
  - "_refine_mode=True flag + _prior_sql + _prior_columns in params for same-intent follow-ups"
affects:
  - 06-04-domain-tool-refine-mode
  - 06-05-frontend-turn-context

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deictic phrase detection via compiled regex (_FOLLOWUP_PATTERNS) before embedding — avoids expensive embed call for thin follow-ups"
    - "Two-signal gate for follow-up: deictic phrase AND refinement keyword both required to avoid false positives"
    - "_refine_mode flag shape: {_refine_mode: True, _prior_sql: str, _prior_columns: list[str]} injected into params for domain tools to use as subquery filter"
    - "Param carry-forward: strip internal refine keys from inherited params to prevent cascade across multi-hop turns"

key-files:
  created:
    - backend/tests/test_context_aware_classifier.py
    - backend/tests/test_context_aware_param_extractor.py
  modified:
    - backend/app/llm/graph/nodes/intent_classifier.py
    - backend/app/llm/graph/nodes/param_extractor.py

key-decisions:
  - "Two-signal detection gate: deictic phrase (e.g. 'which of these') + refinement keyword (e.g. 'active', 'billable') both required — single pattern alone risks false positives"
  - "RBAC gate applies in fast path: user_role='user' + inherited non-user_self domain still blocked (confidence=0.0)"
  - "_refine_mode only set on same-intent follow-up — intent switch carries params forward but runs fresh classification (not a refinement)"
  - "Internal refine keys stripped from inherited params to prevent leaking across multi-hop turns"

patterns-established:
  - "_refine_mode flag shape for Plan 04: params['_refine_mode']=True, params['_prior_sql']=str, params['_prior_columns']=list[str]"
  - "Param inheritance order: inherited params seeded first, regex extraction overlays (new wins on conflict)"

requirements-completed:
  - CTX-02
  - CTX-03

# Metrics
duration: 6min
completed: "2026-03-31"
---

# Phase 6 Plan 03: Context-Aware Classifier and Param Extractor Summary

**Deictic follow-up detection with regex fast path in classify_intent (skip embedding, confidence=0.95) and param carry-forward + _refine_mode flag in extract_params**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-31T12:30:43Z
- **Completed:** 2026-03-31T12:36:31Z
- **Tasks:** 2 (each TDD: RED → GREEN)
- **Files modified:** 4

## Accomplishments

- Added `_FOLLOWUP_PATTERNS` regex (deictic phrases: "which of these", "among them", "filter by", "those who", "same ones", etc.) and `_REFINEMENT_KEYWORDS` regex (skill, active, billable, assigned, available, etc.)
- Added `_is_refinement_followup(question, last_turn_context)` helper with two-signal gate (deictic + keyword + context present)
- Added fast path in `classify_intent()`: when follow-up detected, skip embedding entirely → return inherited domain/intent at confidence=0.95 (RBAC gate still enforced)
- Added param carry-forward in `extract_params()`: seed from `last_turn_context["params"]`, strip internal refine keys, overlay newly extracted values
- Added `_refine_mode=True` + `_prior_sql` + `_prior_columns` injection for same-intent follow-ups (Plan 04 domain tools use these for subquery-based refinement)
- 24 tests across both test files; 124 total tests pass (0 regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: _is_refinement_followup() + classify_intent fast path** - `26f40c4` (feat)
2. **Task 2: param inheritance + _refine_mode flag in extract_params** - `aaa026c` (feat)

**Plan metadata:** `(pending)` (docs: complete plan)

_Note: TDD tasks — RED phase tests written first, then GREEN implementation_

## Files Created/Modified

- `backend/app/llm/graph/nodes/intent_classifier.py` — `_FOLLOWUP_PATTERNS`, `_REFINEMENT_KEYWORDS`, `_is_refinement_followup()`, fast path in `classify_intent()`; `import re` added
- `backend/app/llm/graph/nodes/param_extractor.py` — Param carry-forward from `last_turn_context["params"]`; `_refine_mode` + `_prior_sql` + `_prior_columns` flags
- `backend/tests/test_context_aware_classifier.py` — 15 tests: 11 unit tests for `_is_refinement_followup`, 4 async tests for `classify_intent` fast path (including RBAC edge cases)
- `backend/tests/test_context_aware_param_extractor.py` — 9 tests: carry-forward, override precedence, refine mode detection, intent mismatch guard, key leak prevention

## Decisions Made

- **Two-signal detection gate** — deictic phrase AND refinement keyword both required before fast-pathing. A question like "Among them, display all" (deictic but no keyword) correctly falls through to embedding.
- **RBAC gate in fast path** — user_role="user" + inherited non-user_self domain returns confidence=0.0, same as the normal path. Consistency critical.
- **_refine_mode intent guard** — only set when `state["intent"] == last_turn_context["intent"]`. If intent switches (resource → client), carry params forward but let domain tools run fresh — not a refinement.
- **Internal key stripping** — `_refine_mode`, `_prior_sql`, `_prior_columns` stripped from inherited params to prevent multi-hop cascade (these are ephemeral per-request, not persistent state).

## Deviations from Plan

None - plan executed exactly as written. Regex patterns from the plan spec worked correctly without modification.

## Issues Encountered

None — both TDD cycles completed cleanly on first implementation attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04 (domain tool refine mode) can now read `params["_refine_mode"]`, `params["_prior_sql"]`, and `params["_prior_columns"]` from state when building SQL
- `_refine_mode` flag shape is: `{_refine_mode: True, _prior_sql: "SELECT ...", _prior_columns: ["col1", "col2", ...]}`
- `_prior_sql` is the complete SQL from the prior turn — domain tools should use it as a CTE or subquery to filter results
- Plan 05 (frontend turn context) can proceed independently

## Self-Check: PASSED

- ✅ `backend/app/llm/graph/nodes/intent_classifier.py` — exists, contains `_is_refinement_followup`
- ✅ `backend/app/llm/graph/nodes/param_extractor.py` — exists, contains `_refine_mode`
- ✅ `backend/tests/test_context_aware_classifier.py` — exists (15 tests)
- ✅ `backend/tests/test_context_aware_param_extractor.py` — exists (9 tests)
- ✅ Commit `26f40c4` — feat(06-03): classify_intent fast path
- ✅ Commit `aaa026c` — feat(06-03): param inheritance + _refine_mode
- ✅ 124 total tests pass, 0 regressions

---
*Phase: 06-context-aware-domain-tools*
*Completed: 2026-03-31*
