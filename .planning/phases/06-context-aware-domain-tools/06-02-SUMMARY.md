---
phase: 06-context-aware-domain-tools
plan: 02
subsystem: api
tags: [langgraph, intent-catalog, domain-tools, fallback, prms]

# Dependency graph
requires:
  - phase: 05-langgraph-domain-tool-pipeline
    provides: IntentEntry dataclass with fallback_intent field, INTENT_CATALOG list
  - phase: 06-context-aware-domain-tools
    provides: 06-01 added TurnContext model and plan structure

provides:
  - 24 active PRMS catalog entries with fallback_intent fully wired (18 set, 6 None)
  - All fallback_intent values reference valid existing catalog entry names
  - CTX-04 requirement activated: 0-row domain tool results try fallback before LLM escalation

affects:
  - run_domain_tool node (consumes entry.fallback_intent on 0-row result)
  - 06-context-aware-domain-tools future plans that rely on fallback chain

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fallback chain: parameterized intent → broadest intent in same domain → LLM fallback"
    - "TDD for data-layer changes: write tests against catalog constants, then update catalog"

key-files:
  created:
    - backend/tests/test_intent_catalog_fallbacks.py
  modified:
    - backend/app/llm/graph/intent_catalog.py

key-decisions:
  - "6 broadest entries keep fallback_intent=None: active_resources, benched_resources, active_clients, active_projects, approved_timesheets, my_projects — no broader fallback exists within the domain"
  - "benched_resources keeps fallback_intent=None despite having active_resources as a sibling — the intent targets a specific pool with no useful broader fallback"
  - "my_utilization falls back to my_timesheets (not my_projects) — timesheet data is more semantically related than project list"

patterns-established:
  - "Fallback hierarchy per domain: parameterized intents → broadest list intent → LLM"
  - "Catalog tests verify referential integrity: all fallback_intent values must exist as catalog names"

requirements-completed: [CTX-04]

# Metrics
duration: 6min
completed: 2026-03-31
---

# Phase 6 Plan 2: Fallback Intent Wiring Summary

**Activated `fallback_intent` on all 24 PRMS catalog entries via TDD: 18 entries wired to broader domain intents, 6 broadest entries remain None, enabling 0-row domain tool retry before LLM escalation (CTX-04)**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-31T12:20:15Z
- **Completed:** 2026-03-31T12:26:30Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Wired `fallback_intent` on all 24 active PRMS catalog entries per RESEARCH.md mapping table
- 18 parameterized entries get specific fallback (e.g., `resource_by_skill` → `active_resources`)
- 6 broadest entries retain `None` (no useful broader fallback exists)
- All fallback_intent values verified to reference existing catalog entry names
- TDD test suite with 3 focused tests (count, referential integrity, spot-checks)

## Task Commits

Each TDD phase was committed atomically:

1. **Task 1 RED: Failing tests for fallback_intent catalog wiring** - `77b6b89` (test)
2. **Task 1 GREEN: Set fallback_intent on all 24 active catalog entries** - `d8cc9d7` (feat)

**Plan metadata:** _(to be added)_ (docs: complete plan)

_Note: No REFACTOR commit needed — implementation was clean as written._

## Files Created/Modified

- `backend/tests/test_intent_catalog_fallbacks.py` - 3 tests: count (18), referential integrity, spot-checks
- `backend/app/llm/graph/intent_catalog.py` - All 24 IntentEntry calls updated with fallback_intent kwarg; module docstring corrected to reflect 24 active entries (not 29)

## Fallback Intent Mapping Applied

| Intent | Domain | fallback_intent |
|--------|--------|----------------|
| active_resources | resource | None (broadest) |
| benched_resources | resource | None (specific pool) |
| resource_by_skill | resource | active_resources |
| resource_availability | resource | active_resources |
| resource_project_assignments | resource | active_resources |
| resource_skills_list | resource | active_resources |
| active_clients | client | None (broadest) |
| client_projects | client | active_clients |
| client_status | client | active_clients |
| active_projects | project | None (broadest) |
| project_by_client | project | active_projects |
| project_budget | project | active_projects |
| project_resources | project | active_projects |
| project_timeline | project | active_projects |
| overdue_projects | project | active_projects |
| approved_timesheets | timesheet | None (broadest) |
| timesheet_by_period | timesheet | approved_timesheets |
| unapproved_timesheets | timesheet | approved_timesheets |
| timesheet_by_project | timesheet | approved_timesheets |
| my_projects | user_self | None (broadest) |
| my_allocation | user_self | my_projects |
| my_timesheets | user_self | my_projects |
| my_skills | user_self | my_projects |
| my_utilization | user_self | my_timesheets |

## Decisions Made

- **6 broadest entries = None**: `active_resources`, `benched_resources`, `active_clients`, `active_projects`, `approved_timesheets`, `my_projects` — these are the top-level lists in their domains, no broader fallback exists
- **`benched_resources` stays None**: Despite sibling `active_resources`, the bench pool intent is specific enough that a fallback to all-active is unhelpful
- **`my_utilization` → `my_timesheets`**: Fallback to timesheet data (same data plane) rather than `my_projects` (project list), which is semantically farther from utilization

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-existing test failure in `test_graph_state_keys` (out of scope for this plan): Phase 06-01's uncommitted working directory changes added `last_turn_context` to `GraphState` but didn't update `test_graph_state.py` to include it. This failure existed before and after our changes and is unrelated to catalog wiring.

All catalog-related tests pass: 24/24 in `test_intent_catalog_fallbacks.py`, `test_intent_catalog.py`, `test_intent_classifier.py`, `test_domain_agents.py`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `fallback_intent` wiring is complete and tested
- `run_domain_tool.py` node needs to consume `entry.fallback_intent` on 0-row results (planned for a subsequent plan in Phase 06)
- All 24 catalog entry names are valid fallback targets — referential integrity confirmed

## Self-Check: PASSED

- ✅ `backend/tests/test_intent_catalog_fallbacks.py` exists on disk
- ✅ `backend/app/llm/graph/intent_catalog.py` exists on disk
- ✅ `.planning/phases/06-context-aware-domain-tools/06-02-SUMMARY.md` exists on disk
- ✅ Commit `77b6b89` (test RED) found in git log
- ✅ Commit `d8cc9d7` (feat GREEN) found in git log
- ✅ `python -c "from app.llm.graph.intent_catalog import INTENT_CATALOG; print(sum(1 for e in INTENT_CATALOG if e.fallback_intent))"` → 18

---
*Phase: 06-context-aware-domain-tools*
*Completed: 2026-03-31*
