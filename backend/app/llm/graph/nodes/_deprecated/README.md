# _deprecated/ — Phase 7 Retirement Archive

This directory contains modules that have been superseded by the QueryPlan compiler
pipeline introduced in Phase 7, but are kept here for safety until the feature flag
`USE_QUERY_PLAN_COMPILER=true` is confirmed stable in production.

## Modules

### param_extractor.py
**Superseded by:** `filter_extractor.py` (Phase 7, Plan 02)

`param_extractor.py` was the original regex-based parameter extraction node that
extracted skill/date/name params from user questions and stored them in `state["params"]`.

It has been replaced by `filter_extractor.py` which extracts typed `FilterClause` objects
into `state["filters"]`, which are then accumulated into `state["query_plan"]` by the
`update_query_plan` node.

**When to delete:** After `USE_QUERY_PLAN_COMPILER=true` is confirmed in production and
the old refinement path (flag=OFF) is no longer needed for rollback.

**Original location:** `backend/app/llm/graph/nodes/param_extractor.py`

## See also
- `backend/app/llm/graph/domains/refinement_registry.py` — marked deprecated but kept
  at original location for flag=OFF rollback safety
- `backend/app/llm/graph/nodes/field_registry.py` — replacement registry
- `backend/app/llm/graph/nodes/filter_extractor.py` — replacement node
- `backend/app/llm/graph/nodes/sql_compiler.py` — new SQL compiler
