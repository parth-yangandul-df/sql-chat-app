# Phase 07: QueryPlan Compiler - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace SQL subquery wrapping (refinement_registry.py + _try_refinement) with a structured QueryPlan state model that accumulates typed FilterClause objects across conversation turns and compiles SQL deterministically for all 24 active PRMS intents.

Delivers: QueryPlan Pydantic model, filter extraction node, plan updater node, deterministic SQL compiler, feature-flag-gated base_domain rewrite, regression tests, and semantic layer wiring (glossary/dict/metrics into filter extraction).

Out of scope: Sort layer, query result caching, new UI, new API endpoints, schema changes to any DB tables.

</domain>

<decisions>
## Implementation Decisions

### QueryPlan Model
- Pydantic v2 BaseModel (not dataclass) — free validation, `extra="forbid"`, `strict=True`, `schema_version: Literal[1]`
- `FilterClause`: `field` (registry-validated), `op: Literal["eq","in","lt","gt","between"]`, `values: list[str]` (sanitized, max 50), SQL injection guard on values
- `QueryPlan` fields: `domain`, `intent`, `filters: list[FilterClause]`, `base_intent_sql: str`, `schema_version: Literal[1]`
- `from_untrusted_dict()` classmethod for safe client round-trip deserialization
- `to_api_dict()` method for serialization into turn_context response
- Stored in GraphState as `query_plan: dict | None` (consistent with Phase 6 pattern of storing Pydantic objects as dicts in graph layer — avoids Pydantic imports in graph layer)

### Filter Accumulation Rules
- Multi-value string fields: append new values into `list[str]` when `FieldConfig.multi_value=True`
- Date ranges: new dates replace old dates as BETWEEN clause (last-wins)
- Boolean/scalar fields: last-wins
- Coerce single string to `[string]` for multi-value fields
- Conflict resolution is deterministic — no user prompt, no ambiguity
- `initial_query_plan=None` (first turn or LLM fallback turn): create fresh `QueryPlan(domain, intent, filters=[], base_intent_sql="")`

### Feature Flag
- `use_query_plan_compiler: bool = False` in `app/config.py` Settings (pydantic-settings)
- Env var: `USE_QUERY_PLAN_COMPILER`
- Comment: `# MIGRATION FLAG: remove after phase validation`
- Single `if settings.use_query_plan_compiler:` branch in `BaseDomainAgent.execute()` — flag off → existing `_try_refinement()` path runs unchanged
- Flag is per-deployment via env var; no auto-flip — engineer sets it after regression tests pass

### Migration Cutover Strategy
- Flag default is `False` — zero behavioral change until explicitly enabled
- Enable in test/staging first; production flip is a manual deployment decision
- No automatic cutover — engineer reviews test results, then sets `USE_QUERY_PLAN_COMPILER=true`
- Rollback: set flag back to `False` (no data migration needed — QueryPlan is ephemeral, in-memory)

### Retirement of Old Path
- `refinement_registry.py` deleted **only after** 5 regression tests pass under `USE_QUERY_PLAN_COMPILER=true`
- `param_extractor.py` moved to `_deprecated/` folder (not deleted) when graph.py is rewired — deleted after Phase 3 regression tests pass
- Test asserting `refinement_registry` module is no longer imported anywhere added as part of retirement
- `_run_refinement()` overrides removed from domain agents only after retirement tests pass

### LLM Fallback Interaction
- QueryPlan is only built/updated on domain-tool turns (when `domain` and `intent` are set)
- LLM fallback turns: `query_plan` in GraphState remains `None` (no plan accumulation on LLM turns)
- `base_sql` in query_service.py falls back gracefully: `query_plan.base_intent_sql if query_plan else final_params.get("_prior_sql") or final_state.get("sql") or ""`
- When a conversation switches from domain-tool to LLM mid-turn: `query_plan` in turn_context becomes `None`, client stops sending it, next domain-tool turn starts a fresh plan

### RBAC Guard
- `resource_id` is NOT stored in QueryPlan — it is passed as a separate parameter to `compile_query(plan, resource_id=state.get("resource_id"))`
- `compile_query()` raises `ValueError` if `plan.domain == "user_self" and resource_id is None`
- This guard prevents RBAC bypass — user_self queries always require authenticated resource_id

### SQL Compiler
- `BASE_QUERIES: dict[str, str]` contains all 24 active PRMS intent SQL templates
- Every template has `{select_extras}` and `{join_extras}` named tokens (default empty string) for Phase 4 metric injection
- `build_in_clause(column, values) → (sql_fragment, list)` with edge guards: empty → `"1=0"`, single → `"field=?"`, >2000 → `ValueError`
- Commented-out intents (`resource_utilization`, `resource_billing_rate`, `resource_timesheet_summary`) explicitly excluded with `# deferred: #baadme` comment
- `benched_resources` hardcoded `p.ProjectId = 119` preserved as-is with inline known-limitation comment

### FieldRegistry
- `FieldConfig(column_name, multi_value: bool, sql_type, aliases: list[str])` covering all PRMS filterable fields
- All 6 audited param fallback chains encoded as `aliases` (not duplicated logic): `client_name aliases=["resource_name"]`, `project_name aliases=["resource_name"]` in project/timesheet domain
- `validate_registry_completeness()` raises `StartupIntegrityError(RuntimeError)` — called in `app/main.py` lifespan hook (not `assert` — assert is stripped by -O in production)
- `StartupIntegrityError` crashes startup before traffic starts, also tested in CI

### Filter Extraction
- Regex-first: run existing patterns (skill, date, name, designation)
- LLM only fires when regex returns zero matches AND question is above confidence threshold
- All extracted field names validated against FIELD_REGISTRY — unknowns logged and dropped (never crash)
- Returns `list[FilterClause]` set in GraphState

### Semantic Layer Wiring (Phase 4)
- Glossary terms pre-resolved from DB before LLM filter extraction call — passed as available-field hints in prompt
- Dictionary value_map loaded at startup and applied in filter value normalization (e.g. "backend" → "Backend Developer")
- Metric detection: detect metric names in question → build `MetricFragment(select_expr, join_clause, requires_group_by)` → pass to `compile_query(plan, metrics=[fragment])`
- Metric injection scoped to intents that support aggregation (no GROUP BY conflicts)

### Claude's Discretion
- Exact regex patterns in filter_extractor.py (can reuse/extend from existing param_extractor.py)
- `asyncio.Lock` usage for any concurrent startup checks
- Exact logging format within nodes
- Whether `_deprecated/` folder uses a README explaining why files are there

</decisions>

<specifics>
## Specific Ideas

- Phase 6 established the pattern: store complex objects as `dict | None` in GraphState, never raw Pydantic — follow this exactly for `query_plan`
- `refinement_registry.py` is 1150 lines of declarative templates — the QueryPlan compiler replaces ALL of this with typed filter accumulation; the subquery-wrapping approach it implements is what causes nesting on chained turns
- `StartupIntegrityError` pattern chosen specifically because `assert` statements are stripped by Python's `-O` flag in production optimized mode
- The `{select_extras}` / `{join_extras}` token pattern is an explicit extension point for Phase 4 — not decorative, must be in every template

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `refinement_registry.py` (1150 lines): All 61 declarative templates contain the column names, param keys, and filter types needed to populate FieldRegistry — mine this file when building `prms_field_registry.py`
- `param_extractor.py`: Existing regex patterns for skill, date, name, designation — reuse/extend in `filter_extractor.py`
- `base_domain.py:_try_refinement()`: The method being replaced — its 3-tier priority logic (registry → subclass → base) becomes a single `compile_query()` call under the feature flag
- `state.py:GraphState`: 30-field TypedDict; `resource_id: int | None` already a first-class field (line 29); `last_turn_context: dict | None` at line 24 — `query_plan: dict | None` follows the same pattern
- `query_service.py:base_sql` construction at line 135: `final_params.get("_prior_sql") or final_state.get("sql") or ""` — this is the exact line updated in Task 1.3
- `config.py`: pydantic-settings `BaseSettings`, already has `extra="ignore"` — add `use_query_plan_compiler: bool = False` here

### Established Patterns
- GraphState fields storing serializable Pydantic data: always `dict | None`, never typed Pydantic model (Phase 6 decision — avoids circular imports and graph-layer Pydantic dependency)
- Feature flag pattern: env var → pydantic-settings bool → single `if settings.X:` branch
- `logging.getLogger(__name__)` used throughout; WARNING level on fallback paths
- All SQL uses `?` positional placeholders (pyodbc/aioodbc style) — tuples, not lists
- Startup integrity: `try/except` in lifespan hook wrapping the startup check; `StartupIntegrityError` crashes the process before traffic reaches it
- All nodes are `async def`; return `dict` of updated state keys

### Integration Points
- `backend/app/llm/graph/state.py`: Add `query_plan: dict | None` field
- `backend/app/services/query_service.py`: Three changes — deserialize plan from turn_context, update base_sql logic, include plan in turn_context response
- `backend/app/config.py`: Add `use_query_plan_compiler: bool = False`
- `backend/app/main.py`: Call `validate_registry_completeness()` in lifespan hook; add `StartupIntegrityError` import
- `backend/app/llm/graph/graph.py`: Replace `extract_params` node with `extract_filters → update_query_plan` pipeline
- `backend/app/llm/graph/domains/base_domain.py`: Add `if settings.use_query_plan_compiler:` branch in `execute()`

### Files Being Retired
- `backend/app/llm/graph/domains/refinement_registry.py` — deleted after regression tests pass (1150 lines of subquery wrapping templates)
- `backend/app/llm/graph/nodes/param_extractor.py` — moved to `_deprecated/` when graph.py is rewired; deleted after regression tests pass

</code_context>

<deferred>
## Deferred Ideas

- Sort layer (`Sort(field, direction)` dataclass, NL→sort mapping, ORDER BY in compiler) — future phase
- Query result caching (plan cache, result cache, in-memory refinement filtering, TTL) — future phase
- `FilterClause.values: list[str]` numeric operator support (e.g. `{"op": ">=", "value": 5}` with int) — future phase
- Full `QueryPlan` fields (`select`, `joins`, `sort`, `limit`) as per design docs — future phase
- Generic schema support for FieldRegistry (currently PRMS-hardcoded) — future phase
- DB-backed admin-configurable intent catalog — deferred from Phase 5, still deferred
- Langfuse spans for new nodes (filter_extractor, plan_updater) — future phase
- User-facing routing transparency (showing domain_tool vs LLM path) — deferred from Phase 5, still deferred

</deferred>

---

*Phase: 07-queryplan-compiler*
*Context gathered: 2026-04-02*
