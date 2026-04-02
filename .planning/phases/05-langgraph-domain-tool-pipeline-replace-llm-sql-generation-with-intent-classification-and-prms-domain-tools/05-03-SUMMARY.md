---
phase: 05-langgraph-domain-tool-pipeline
plan: 03
subsystem: api
tags: [langgraph, sqlserver, domain-agents, parameterized-sql, prms, tdd]

# Dependency graph
requires:
  - phase: 05-01
    provides: GraphState TypedDict and 24-intent PRMS catalog
  - phase: 05-02
    provides: classify_intent node and extract_params node
provides:
  - Fixed SQLServerConnector._run_query() that passes params tuple to cursor.execute()
  - Updated BaseConnector.execute_query() abstract signature with params as tuple[Any, ...] | None
  - BaseDomainAgent ABC with shared execute() dispatch logic
  - ResourceAgent with 9 parameterized SQL intents
  - ClientAgent with 5 parameterized SQL intents
  - ProjectAgent with 6 parameterized SQL intents
  - TimesheetAgent with 4 parameterized SQL intents (IsApproved/IsDeleted/IsRejected filters)
  - DOMAIN_REGISTRY dict mapping domain names to agent classes
  - run_domain_tool LangGraph node that dispatches to correct domain agent
affects:
  - 05-04-graph-nodes
  - 05-05-wire-query-service

# Tech tracking
tech-stack:
  added: []
  patterns:
    - BaseDomainAgent ABC with execute() + _run_intent() contract
    - Parameterized SQL with ? positional placeholders (SQL Server / aioodbc)
    - Timesheet valid-entry filter constant (_VALID) shared across intents
    - DOMAIN_REGISTRY dict + run_domain_tool dispatcher node pattern
    - TDD (RED-GREEN) cycle for domain agent implementation

key-files:
  created:
    - backend/app/llm/graph/domains/__init__.py
    - backend/app/llm/graph/domains/base_domain.py
    - backend/app/llm/graph/domains/resource.py
    - backend/app/llm/graph/domains/client.py
    - backend/app/llm/graph/domains/project.py
    - backend/app/llm/graph/domains/timesheet.py
    - backend/app/llm/graph/domains/registry.py
  modified:
    - backend/app/connectors/base_connector.py
    - backend/app/connectors/sqlserver/connector.py
    - backend/tests/test_domain_agents.py

key-decisions:
  - "BaseConnector.execute_query() abstract signature changed from dict[str, Any] | None to tuple[Any, ...] | None for params, aligning with SQL Server ? positional placeholder style"
  - "BaseDomainAgent.execute() uses intent or '' guard so domain agents always receive a str (not None) to _run_intent()"
  - "TimesheetAgent uses a module-level _VALID constant to ensure the IsApproved/IsDeleted/IsRejected filter is consistently applied across all valid-entry timesheet intents"

patterns-established:
  - "Domain agent pattern: subclass BaseDomainAgent, implement _run_intent() with if/elif/else over intent strings, raise ValueError for unknown intent"
  - "Parameterized SQL: pass params=(value,) as keyword arg to execute_query(); omit params kwarg for queries without parameters"
  - "DOMAIN_REGISTRY + run_domain_tool: single dispatcher node looks up domain in registry, instantiates agent, calls execute(state)"

requirements-completed: [LG-07, LG-08, LG-09, LG-10]

# Metrics
duration: 5min
completed: 2026-03-26
---

# Phase 5 Plan 03: SQLServer Params Fix + 4 PRMS Domain Agents + Registry Summary

**Fixed SQLServerConnector params bug and implemented 4 domain agents (24 SQL intents total) with DOMAIN_REGISTRY dispatcher node using parameterized ? placeholder SQL**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-26T07:54:10Z
- **Completed:** 2026-03-26T07:59:31Z
- **Tasks:** 3 (Task 0 + Task 1 + Task 2)
- **Files modified:** 10

## Accomplishments
- Fixed critical SQLServer params bug: `_run_query()` now passes params tuple to `cursor.execute()` so parameterized queries work correctly
- Implemented `BaseDomainAgent` ABC with shared `execute()` dispatch logic (connector lookup + `_run_intent()` call + result packaging)
- Built 4 domain agents covering all 24 PRMS intents with correct SQL templates and `?` positional placeholders
- Created `DOMAIN_REGISTRY` + `run_domain_tool` LangGraph node that dispatches to the correct agent based on `state["domain"]`
- All 8 domain agent tests pass (TDD RED-GREEN cycle)

## Task Commits

Each task was committed atomically:

1. **Task 0: Fix SQLServer connector params bug** - `269c856` (fix)
2. **TDD RED: Failing tests for all domain agents** - `f55ee50` (test)
3. **TDD GREEN: All 4 domain agents + registry implementation** - `26ac11f` (feat)

**Plan metadata:** *(to be added)*

## Files Created/Modified
- `backend/app/connectors/base_connector.py` - Updated execute_query() abstract signature: params now tuple[Any, ...] | None
- `backend/app/connectors/sqlserver/connector.py` - Fixed _run_query() to accept and pass params tuple to cursor.execute()
- `backend/app/llm/graph/domains/__init__.py` - Package init (empty)
- `backend/app/llm/graph/domains/base_domain.py` - BaseDomainAgent ABC with execute() dispatch logic
- `backend/app/llm/graph/domains/resource.py` - ResourceAgent with 9 SQL intents
- `backend/app/llm/graph/domains/client.py` - ClientAgent with 5 SQL intents
- `backend/app/llm/graph/domains/project.py` - ProjectAgent with 6 SQL intents
- `backend/app/llm/graph/domains/timesheet.py` - TimesheetAgent with 4 SQL intents + _VALID filter constant
- `backend/app/llm/graph/domains/registry.py` - DOMAIN_REGISTRY dict + run_domain_tool LangGraph node
- `backend/tests/test_domain_agents.py` - 8 tests covering all agents, parameterized SQL, unknown intent/domain errors

## Decisions Made
- Changed `BaseConnector.execute_query()` params type from `dict[str, Any] | None` to `tuple[Any, ...] | None` to align with SQL Server `?` positional placeholder style. Other connectors (PostgreSQL, BigQuery, Databricks) retain the `dict` signature in their implementations but don't use params in practice.
- `BaseDomainAgent.execute()` uses `state["intent"] or ""` guard to safely pass a `str` to `_run_intent()` even when `GraphState.intent` is `str | None`.
- `TimesheetAgent` uses a module-level `_VALID` constant (`"ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0"`) for consistent valid-entry filtering across all applicable intents.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `run_domain_tool` LangGraph node is ready to be wired into the graph assembly (Plan 04)
- All 24 intents covered; Plans 04/05 can reference `DOMAIN_REGISTRY` directly
- `BaseDomainAgent` contract established — future domain agents (e.g. Finance, HR) follow the same subclass pattern

---
*Phase: 05-langgraph-domain-tool-pipeline*
*Completed: 2026-03-26*

## Self-Check: PASSED

- All 10 key files found on disk ✅
- Commits `269c856`, `f55ee50`, `26ac11f` verified in git log ✅
- All 8 pytest tests pass ✅
- DOMAIN_REGISTRY has 4 entries ✅
- Timesheet _VALID filter contains IsApproved=1, IsDeleted=0, IsRejected=0 ✅
