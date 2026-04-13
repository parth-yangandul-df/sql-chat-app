---
plan: 07-02
phase: 07-queryplan-compiler
status: complete
completed: 2026-04-06
---

# Plan 07-02: FieldRegistry, Filter Extractor, Plan Updater, Graph Rewiring

## What Was Built

Replaced `extract_params` node with a two-stage filter pipeline (`extract_filters → update_query_plan`) that produces structured `QueryPlan` objects with typed `FilterClause` filters.

### FieldRegistry (`field_registry.py`)
- 22 canonical filterable fields across 5 domains (resource, client, project, timesheet, user_self)
- `FieldConfig` dataclass: field_name, column_name, multi_value, sql_type, aliases, domains
- `FIELD_REGISTRY_BY_DOMAIN` nested lookup built at module load
- `lookup_field()`, `resolve_alias()` helpers
- `validate_registry_completeness()` — raises `StartupIntegrityError` if any catalog domain has no fields

### Filter Extractor (`filter_extractor.py`)
- Regex-first extraction: skill (3 patterns), dates, project/client/resource name, designation, numeric thresholds (hours, allocation, budget, experience, days overdue), billable
- Validates every extracted value against FieldRegistry — unknown fields dropped with WARNING
- Refine-mode fallback for bare follow-ups ("which of these know Python")
- LLM extraction deferred to Plan 04 (logged as stub)

### Plan Updater (`plan_updater.py`)
- Creates fresh `QueryPlan` on first turn or topic/intent switch
- Merges filters across turns: multi_value=True → append, multi_value=False → last-wins
- Serializes to `dict` for GraphState storage (follows Phase 6 pattern)

### Graph Rewiring (`graph.py`)
- Topology: `classify_intent → extract_filters → update_query_plan → run_domain_tool`
- `extract_params` node removed; `route_after_classify` key "extract_params" remapped to `extract_filters`
- `param_extractor.py` NOT deleted — retirement in Plan 03
- `query_service.py`: `"filters": []` added to initial_state

## Key Files

### key-files:
created:
  - backend/app/llm/graph/nodes/field_registry.py
  - backend/app/llm/graph/nodes/filter_extractor.py
  - backend/app/llm/graph/nodes/plan_updater.py
  - backend/tests/test_field_registry.py
  - backend/tests/test_filter_extractor.py
  - backend/tests/test_plan_updater.py
modified:
  - backend/app/llm/graph/graph.py
  - backend/app/services/query_service.py
  - backend/app/llm/graph/state.py

## Decisions Made

- `route_after_classify` returns `"extract_params"` key — remapped in `add_conditional_edges` to `"extract_filters"` node (no change needed in classifier)
- `filters` stored as `list[FilterClause]` in GraphState (not serialized to dict — only `query_plan` is dict)
- `skill` is the only `multi_value=True` field — all others are last-wins
- `_SKILL_WORD_BEFORE_RE` added beyond param_extractor patterns: catches "Python skill" phrasing

## Self-Check: PASSED

- All 36 tests (20 field_registry + 7 filter_extractor + 9 plan_updater) pass
- Graph compiles with new node topology
- `extract_params` node removed from compiled graph
- No regressions in existing test suite
