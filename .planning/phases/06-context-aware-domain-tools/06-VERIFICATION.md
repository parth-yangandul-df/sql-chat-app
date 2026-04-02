---
phase: 06-context-aware-domain-tools
verified: 2026-03-31T00:00:00Z
status: passed
score: 10/10 must-haves verified
gaps: []
human_verification:
  - test: "Refinement follow-up in live chat"
    expected: "Asking 'show me only the active ones' after a resource query inherits prior SQL, strips ORDER BY, and returns filtered results without re-running the full intent pipeline"
    why_human: "Requires a running LLM + database stack; end-to-end flow through graph cannot be verified statically"
  - test: "turn_context round-trip in widget"
    expected: "After a successful query in the ChatWidget, the returned turn_context is stored in state and sent back on the next message; confirm in browser devtools network tab"
    why_human: "React state transitions and network payload inspection require a running frontend"
---

# Phase 06: Context-Aware Domain Tools — Verification Report

**Phase Goal:** Enable multi-turn conversational queries where follow-up questions inherit context (prior SQL, extracted params, intent) from the previous turn, so users can refine results without repeating themselves.
**Verified:** 2026-03-31
**Status:** ✅ PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `TurnContext` is a typed Pydantic model returned from the query endpoint | ✓ VERIFIED | `schemas/query.py` — `class TurnContext(BaseModel)` with `intent`, `params`, `prior_sql`, `prior_columns` fields; `QueryResponse.turn_context: TurnContext \| None` |
| 2 | `QueryRequest` accepts `last_turn_context` from the client | ✓ VERIFIED | `schemas/query.py` — `last_turn_context: dict \| None = None`; endpoint calls `.model_dump()` and passes it into `initial_state` |
| 3 | `GraphState` carries `last_turn_context` through the graph | ✓ VERIFIED | `graph/state.py` — `last_turn_context: dict \| None` typed key present |
| 4 | Refinement follow-ups are classified without an LLM call | ✓ VERIFIED | `intent_classifier.py` — `_is_refinement_followup()` checks `_FOLLOWUP_PATTERNS` + `_REFINEMENT_KEYWORDS`; fast path sets confidence=0.95 and skips LLM |
| 5 | Extracted params carry forward from prior turn | ✓ VERIFIED | `param_extractor.py` — seeds from `last_turn_context["params"]`, strips internal keys, overlays new extractions; `_refine_mode=true` flag set |
| 6 | Every intent catalog entry declares a `fallback_intent` | ✓ VERIFIED | `intent_catalog.py` — all 24 `IntentEntry` objects have the `fallback_intent` field (18 non-None, 6 intentionally None for terminal intents) |
| 7 | A `run_fallback_intent` graph node retries with the fallback intent on 0-row results | ✓ VERIFIED | `nodes/fallback_intent.py` — checks `row_count == 0`, reads `fallback_intent` from catalog, re-dispatches; max 1 hop (`_fallback_attempted` guard) |
| 8 | `base_domain.py` dispatches to `_run_refinement()` when `_refine_mode` is set | ✓ VERIFIED | `domains/base_domain.py` — `execute()` checks `_is_refine_mode()`; `_get_prior_sql()` + `_strip_order_by()` helpers present; `_run_refinement()` default falls back to `_run_intent()` |
| 9 | `ResourceAgent` generates a subquery-style refinement SQL | ✓ VERIFIED | `domains/resource.py` — `_run_refinement()` generates `SELECT prev.* FROM (<stripped_sql>) AS prev JOIN ...` for both benched and active employee column patterns |
| 10 | Frontend stores and round-trips `turn_context` on every message | ✓ VERIFIED | `types/api.ts` — `TurnContext` interface + `QueryResult.turn_context`; `queryApi.ts` — `last_turn_context?: TurnContext` in request; `ChatWidget.tsx` + `ChatPanel.tsx` + `StandaloneChatPage.tsx` — state kept, sent, updated on each response |

**Score: 10/10 truths verified**

---

## Required Artifacts

| Artifact | Plan | Status | Details |
|----------|------|--------|---------|
| `backend/app/api/v1/schemas/query.py` | 06-01 | ✓ VERIFIED | `TurnContext`, `QueryRequest.last_turn_context`, `QueryResponse.turn_context` all present and substantive |
| `backend/app/llm/graph/state.py` | 06-01 | ✓ VERIFIED | `last_turn_context: dict \| None` key present in `GraphState` TypedDict |
| `backend/app/services/query_service.py` | 06-01 | ✓ VERIFIED | Accepts `last_turn_context`, puts into `initial_state`, returns `turn_context` in response dict |
| `backend/app/api/v1/endpoints/query.py` | 06-01 | ✓ VERIFIED | Passes `last_turn_context=request.last_turn_context.model_dump()` to service |
| `backend/app/llm/graph/intent_catalog.py` | 06-02 | ✓ VERIFIED | All 24 entries; `fallback_intent` field present on every `IntentEntry` |
| `backend/app/llm/graph/nodes/intent_classifier.py` | 06-03 | ✓ VERIFIED | `_FOLLOWUP_PATTERNS`, `_REFINEMENT_KEYWORDS`, `_is_refinement_followup()`, fast-path in `classify_intent()` |
| `backend/app/llm/graph/nodes/param_extractor.py` | 06-03 | ✓ VERIFIED | Carry-forward logic, `_refine_mode` flag injection |
| `backend/app/llm/graph/domains/base_domain.py` | 06-04 | ✓ VERIFIED | `_is_refine_mode()`, `_get_prior_sql()`, `_strip_order_by()`, `execute()` dispatch, default `_run_refinement()` |
| `backend/app/llm/graph/domains/resource.py` | 06-04 | ✓ VERIFIED | `ResourceAgent._run_refinement()` — benched + active employee subquery patterns |
| `backend/app/llm/graph/nodes/fallback_intent.py` | *(undocumented — see notes)* | ✓ VERIFIED | `run_fallback_intent()`, `route_after_domain_tool()`, `route_after_fallback_intent()` all present and wired into `graph.py` |
| `chatbot-frontend/src/types/api.ts` | 06-05 | ✓ VERIFIED | `TurnContext` interface, `QueryResult.turn_context: TurnContext \| null` |
| `chatbot-frontend/src/api/queryApi.ts` | 06-05 | ✓ VERIFIED | `last_turn_context?: TurnContext` in request payload |
| `chatbot-frontend/src/components/widget/ChatWidget.tsx` | 06-05 | ✓ VERIFIED | `sessionId` + `lastTurnContext` state, `useEffect` session creation |
| `chatbot-frontend/src/components/widget/ChatPanel.tsx` | 06-05 | ✓ VERIFIED | Receives props, sends both in mutation, updates `lastTurnContext` on success |
| `chatbot-frontend/src/pages/StandaloneChatPage.tsx` | 06-05 | ✓ VERIFIED | `lastTurnContext` state, reset on new session, sent + captured on each turn |

---

## Test Coverage

| Test File | Plan | Tests | Status |
|-----------|------|-------|--------|
| `backend/tests/test_turn_context_schema.py` | 06-01 | 5 | ✓ Present |
| `backend/tests/test_intent_catalog_fallbacks.py` | 06-02 | 3 | ✓ Present |
| `backend/tests/test_context_aware_classifier.py` | 06-03 | 15 (11 unit + 4 async) | ✓ Present |
| `backend/tests/test_context_aware_param_extractor.py` | 06-03 | 9 | ✓ Present |
| `backend/tests/test_subquery_refinement.py` | 06-04 | 20 | ✓ Present |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `query.py` (endpoint) | `query_service.py` | `last_turn_context=request.last_turn_context.model_dump()` | ✓ WIRED | Confirmed in endpoint handler |
| `query_service.py` | `GraphState` | `initial_state["last_turn_context"]` | ✓ WIRED | Confirmed in service |
| `intent_classifier.py` | `_is_refinement_followup()` | fast-path branch in `classify_intent()` | ✓ WIRED | Returns early with confidence=0.95 |
| `param_extractor.py` | `last_turn_context["params"]` | carry-forward seed before LLM extraction | ✓ WIRED | Strips internal keys, overlays new |
| `base_domain.execute()` | `_run_refinement()` | `_is_refine_mode()` guard | ✓ WIRED | Dispatch confirmed in `execute()` |
| `ResourceAgent._run_refinement()` | `_strip_order_by()` | Called before subquery wrapping | ✓ WIRED | Regex strip + subquery join |
| `run_fallback_intent` node | `graph.py` | `add_node` + conditional edges | ✓ WIRED | Node registered and routed via `route_after_domain_tool` / `route_after_fallback_intent` |
| `ChatPanel.tsx` mutation | `queryApi.ts` | `last_turn_context` in request body | ✓ WIRED | Sent on every `sendMessage` call |
| `StandaloneChatPage.tsx` | `lastTurnContext` state | `onSuccess` captures from response | ✓ WIRED | State updated after each response |

---

## Requirements Coverage

> **Note:** CTX-01 through CTX-10 are declared in `.planning/ROADMAP.md` under Phase 6 but are **absent from `.planning/REQUIREMENTS.md`**, which only contains Phase 5 `LG-xx` entries. This is a documentation gap — requirements were defined at the roadmap level only and never promoted into the canonical requirements registry. The phase was fully implemented against the roadmap-level definitions.

| Requirement | Source | Description | Status | Evidence |
|-------------|--------|-------------|--------|---------|
| CTX-01 | ROADMAP.md | `TurnContext` schema + round-trip wiring | ✓ SATISFIED | `schemas/query.py`, `state.py`, endpoint, service |
| CTX-02 | ROADMAP.md | Refinement classifier fast path (no LLM) | ✓ SATISFIED | `intent_classifier.py` — pattern + keyword match, confidence=0.95 |
| CTX-03 | ROADMAP.md | Param carry-forward from prior turn | ✓ SATISFIED | `param_extractor.py` — seeds from `last_turn_context["params"]` |
| CTX-04 | ROADMAP.md | `fallback_intent` on every catalog entry + retry node | ✓ SATISFIED | `intent_catalog.py` (24 entries) + `fallback_intent.py` node |
| CTX-05 | ROADMAP.md | Frontend `TurnContext` type + round-trip in all chat surfaces | ✓ SATISFIED | `types/api.ts`, `queryApi.ts`, `ChatWidget`, `ChatPanel`, `StandaloneChatPage` |
| CTX-06 | ROADMAP.md | `base_domain` refine-mode dispatch + `_strip_order_by` | ✓ SATISFIED | `base_domain.py` — `execute()`, `_is_refine_mode()`, `_strip_order_by()` |
| CTX-07 | ROADMAP.md | `ResourceAgent` subquery-style refinement SQL | ✓ SATISFIED | `resource.py` — benched + active patterns |
| CTX-08 | ROADMAP.md | ORDER BY stripped before subquery wrapping | ✓ SATISFIED | `_strip_order_by()` regex `re.IGNORECASE\|re.DOTALL` |
| CTX-09 | ROADMAP.md | Column-based heuristic for benched vs active pattern | ✓ SATISFIED | `employeeid`/`EMPID` detection in `_run_refinement()` |
| CTX-10 | ROADMAP.md | Non-resource agents fall back gracefully in refine mode | ✓ SATISFIED | `base_domain._run_refinement()` default calls `_run_intent()` |

---

## Anti-Patterns Found

No blocking anti-patterns detected. Scan of all modified files found:

- No `TODO` / `FIXME` / `PLACEHOLDER` / `XXX` comments in implementation code
- No `return null` / `return {}` / `return []` stubs in route handlers
- No empty event handlers
- No console-log-only implementations

---

## Human Verification Required

### 1. End-to-end refinement follow-up

**Test:** In a running stack, ask a question that invokes `ResourceAgent` (e.g. "Show me all active employees"). Then follow up with "show me only the benched ones."
**Expected:** Second query is classified as refinement (fast path), inherits prior SQL, strips ORDER BY, wraps in subquery JOIN, and returns a filtered result set without re-running the full LLM classification pipeline.
**Why human:** Requires live LLM + database; graph execution path cannot be verified statically.

### 2. `turn_context` round-trip in ChatWidget

**Test:** Open the embedded ChatWidget in a browser. Send one query. Open DevTools → Network. Send a second message.
**Expected:** The second request body contains `last_turn_context` populated with `intent`, `params`, `prior_sql`, and `prior_columns` from the first response.
**Why human:** React state transitions and network payload inspection require a running frontend.

### 3. Fallback intent retry in practice

**Test:** Craft a query likely to return 0 rows for its primary intent but where the catalog's `fallback_intent` would succeed (e.g. an intent with a date filter that excludes all rows, whose fallback drops the filter).
**Expected:** The graph transparently retries with the fallback intent and returns results; the user sees results rather than an empty response.
**Why human:** Requires controlled data + live graph execution.

---

## Findings & Notes

### 1. `fallback_intent.py` undocumented in plan `files_modified`

`backend/app/llm/graph/nodes/fallback_intent.py` is a substantive file (contains `run_fallback_intent`, `route_after_domain_tool`, `route_after_fallback_intent`) that is wired into `graph.py`. It does not appear in any plan's `files_modified` list. It was created during execution of plan 06-02/06-04 but not declared. The implementation is correct and complete — this is purely a documentation gap.

### 2. CTX requirements missing from REQUIREMENTS.md

`.planning/REQUIREMENTS.md` ends at Phase 5 (`LG-xx` series). Phase 6 requirements (`CTX-01` through `CTX-10`) exist only in `ROADMAP.md`. If future phases reference requirements by ID, this will cause cross-reference failures. Recommend promoting CTX-01..CTX-10 into `REQUIREMENTS.md`.

### 3. ROADMAP.md progress is stale

ROADMAP.md still shows Phase 6 as "2/5 plans executed" with all plan checkboxes unchecked (`[ ]`). All 5 plans were committed and verified complete. This is a cosmetic issue in the planning artifact only — the codebase is correct.

---

## Commit Verification

All 10 commits for this phase confirmed present in git log:

| Hash | Description |
|------|-------------|
| `eb4ac9b` | feat(06-01): TurnContext model |
| `797ce5b` | feat(06-01): wire last_turn_context |
| `77b6b89` | test(06-02): RED tests |
| `d8cc9d7` | feat(06-02): fallback_intent catalog entries |
| `26f40c4` | feat(06-03): classify_intent fast path |
| `aaa026c` | feat(06-03): param inheritance + _refine_mode |
| `a9df169` | feat(06-05): TurnContext types + queryApi |
| `f78f11b` | feat(06-05): session management + lastTurnContext frontend |
| `5a23c03` | feat(06-04): base_domain helpers + dispatch |
| `6666557` | feat(06-04): ResourceAgent._run_refinement + tests |

---

_Verified: 2026-03-31_
_Verifier: Claude (gsd-verifier)_
