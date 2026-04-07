# QueryWise Requirements

## Phase 5: LangGraph Domain Tool Pipeline

### LG-01: LangGraph Dependencies
- Add `langgraph>=0.2` and `langchain-core>=0.3` to `backend/pyproject.toml` under `llm` extras
- Both packages must be importable after install

### LG-02: GraphState TypedDict
- Define `GraphState` TypedDict in `backend/app/llm/graph/state.py`
- Must contain all 24 required keys: question, connection_id, connector_type, connection_string, timeout_seconds, max_rows, db, domain, intent, confidence, params, sql, result, generated_sql, retry_count, explanation, llm_provider, llm_model, answer, highlights, suggested_followups, execution_id, execution_time_ms, error

### LG-03: 24-Intent Catalog
- Define `INTENT_CATALOG` in `backend/app/llm/graph/intent_catalog.py`
- Exactly 24 entries across 4 domains: Resource (9), Client (5), Project (6), Timesheet (4)
- Each `IntentEntry` has: name, domain, description, embedding, sql_fallback_template (optional), fallback_intent (optional)
- Intent names must be unique; domains restricted to: resource, client, project, timesheet

### LG-04: Catalog Pre-Embedding
- `ensure_catalog_embedded()` pre-embeds all 24 catalog descriptions at startup
- Idempotent — safe to call multiple times (asyncio.Lock guarded)
- Uses `embed_text()` from `app/services/embedding_service.py`
- If embedding provider is unavailable: log warning and skip — do NOT crash startup

### LG-05: Intent Classifier Node
- `classify_intent` node embeds the question and picks best catalog match via cosine similarity
- Sets: domain, intent, confidence in returned state dict
- Reads threshold from `TOOL_CONFIDENCE_THRESHOLD` env var (default 0.78)
- If catalog not yet embedded, calls `ensure_catalog_embedded()` lazily
- If embedding fails: catch exception, route to `llm_fallback` (graceful degradation)

### LG-06: Routing Edge + Param Extractor
- `route_after_classify(state)` returns `"run_domain_tool"` if confidence >= threshold, else `"llm_fallback"`
- `extract_params(state)` extracts skill, start_date, end_date, resource_name from question using regex only (no LLM)
- No extraction → params={} (empty dict)

### LG-07: SQLServer Connector Bug Fix
- Fix `backend/app/connectors/sqlserver/connector.py`: `_run_query()` currently ignores `params` argument entirely
- Update `_run_query()` to accept and pass params tuple to `cursor.execute(sql, params_tuple)`
- Update `execute_query()` signature: `params: tuple[Any, ...] | None = None`
- Update `backend/app/connectors/base_connector.py` abstract method signature to match

### LG-08: Resource Domain Agent
- `ResourceAgent` handles all 9 resource intents with parameterized SQL templates
- Uses `?` positional placeholders (SQL Server / pyodbc style)
- Bare table names (no `dbo.` prefix)
- Unknown intent raises `ValueError`

### LG-09: Client, Project, Timesheet Domain Agents
- `ClientAgent` handles 5 client intents
- `ProjectAgent` handles 6 project intents
- `TimesheetAgent` handles 4 timesheet intents — all valid-entry queries include `IsApproved=1 AND IsDeleted=0 AND IsRejected=0`
- Unknown intent raises `ValueError` in each agent

### LG-10: Domain Registry + run_domain_tool Node
- `DOMAIN_REGISTRY` maps domain name → agent class
- `run_domain_tool(state)` looks up state["domain"], instantiates agent, calls `execute(state)`
- Unknown domain raises `ValueError`
- Agent `execute()` returns: sql, result, llm_provider="domain_tool", llm_model=intent_name

### LG-11: 0-Row Fallback Chain
- After `run_domain_tool`: if `result.row_count == 0`:
  1. If `IntentEntry.fallback_intent` is defined → run that intent's SQL (1 hop max, no chaining)
  2. If fallback intent also returns 0 rows (or none defined) → route to `llm_fallback`
- SQL execution errors (exceptions) → immediate AppError, no retry, no LLM fallback
- `interpret_result` node only reached when rows > 0

### LG-12: Result Interpreter Node
- `interpret_result` node wraps existing `ResultInterpreterAgent` unchanged
- If result has rows: calls `interpreter.interpret()`, sets answer, highlights, suggested_followups
- If result has no rows: sets answer=None, highlights=[], suggested_followups=[]

### LG-13: LLM Fallback Node
- `llm_fallback` node reuses existing `QueryComposerAgent`, `SQLValidatorAgent`, `ErrorHandlerAgent` unchanged
- Mirrors current `query_service.execute_nl_query()` LLM logic exactly
- Sets: sql, result, generated_sql, retry_count, llm_provider, llm_model, explanation

### LG-14: Write History Node + Graph Assembly
- `write_history` node creates `QueryExecution` record, calls `db.add()` + `db.flush()`
- Sets: execution_id, execution_time_ms
- `get_compiled_graph()` returns a compiled LangGraph `StateGraph` singleton
- Graph topology reflects the 0-row conditional edge (LG-11)

### LG-15: query_service.py Integration
- Replace `execute_nl_query()` body with `get_compiled_graph().ainvoke(initial_state)`
- Response dict shape preserved exactly (same 17 keys as original)
- `generate_sql_only()` and `execute_raw_sql()` completely unchanged

### LG-16: Startup Hook
- `main.py` lifespan calls `ensure_catalog_embedded()` after `ensure_embedding_dimensions()`, before `auto_setup_sample_db()`
- Wrapped in try/except — failure logs warning but does NOT prevent startup

---

## Phase 7: QueryPlan Compiler

### QP-01: QueryPlan Model and Foundation
- Define `QueryPlan` and `FilterClause` Pydantic v2 models in `backend/app/llm/graph/query_plan.py`
- `FilterClause`: `field` (registry-validated), `op: Literal["eq","in","lt","gt","between"]`, `values: list[str]` (sanitized, max 50), SQL injection guard on values
- `QueryPlan` fields: `domain`, `intent`, `filters: list[FilterClause]`, `base_intent_sql: str`, `schema_version: Literal[1]`
- `QueryPlan.from_untrusted_dict()` classmethod for safe deserialization; `to_api_dict()` for serialization
- Add `query_plan: dict | None` to GraphState TypedDict (stored as dict, not raw Pydantic — follows Phase 6 pattern)
- Add `use_query_plan_compiler: bool = False` feature flag to Settings (reads from `USE_QUERY_PLAN_COMPILER` env var)
- Update `query_service.py` to deserialize QueryPlan from graph state for `base_sql` construction, include in `turn_context` response, fall back to existing `_prior_sql` logic when None

### QP-02: Filter Extraction and Plan Update Pipeline
- Create `FieldRegistry` in `backend/app/llm/graph/nodes/field_registry.py` with all PRMS filterable fields across 5 domains (resource, client, project, timesheet, user_self), column mappings, aliases, and multi-value flags
- `FieldConfig` dataclass: `field_name`, `column_name`, `multi_value`, `sql_type`, `aliases`, `domains`
- `validate_registry_completeness()` raises `StartupIntegrityError(RuntimeError)` if any domain-intent pair has no registered fields
- Create `filter_extractor` node (regex-first extraction with LLM fallback stub) — reuses patterns from `param_extractor.py`, validates all extracted fields against FieldRegistry, drops unknowns safely
- Create `plan_updater` node — accumulates filters across turns: multi-value fields append, date ranges last-wins, boolean/scalar last-wins, domain/intent switch creates fresh plan
- Wire `extract_filters → update_query_plan` into LangGraph pipeline, replace `extract_params` node
- Move `param_extractor.py` to `_deprecated/` folder (not deleted)

### QP-03: SQL Compiler and Domain Agent Rewrite
- Create `sql_compiler.py` with `BASE_QUERIES` dict containing all 24 active PRMS intent SQL templates, each with `{select_extras}` and `{join_extras}` named tokens
- `build_in_clause(column, values)` with edge guards: empty → `"1=0"`, single → `"field=?"`, >2000 → `ValueError`
- `compile_query(plan, resource_id=None, metrics=None)` — produces deterministic SQL with correct WHERE clauses, parameter tuples, RBAC guard (raises ValueError if `plan.domain == "user_self" and resource_id is None`)
- Rewrite `BaseDomainAgent.execute()` with feature flag branch: flag ON → `compile_query()` path, flag OFF → existing `_try_refinement()` path unchanged
- 5 regression flow tests: resource chain, project filter chain, timesheet date chain, topic switch recovery, LLM fallback→domain tool
- Wire `StartupIntegrityError` into `main.py` lifespan hook
- Mark `refinement_registry.py` as deprecated (not deleted — kept for rollback safety), add deprecation warning to `_try_refinement()`

### QP-04: Semantic Layer Wiring
- Create `semantic_resolver.py`: `resolve_glossary_hints()` returns available field names from glossary terms for filter extraction hints, `load_value_map()` loads dictionary value_map at startup, `normalize_value()` maps user-friendly values to DB values
- Wire glossary hints into `filter_extractor` — use glossary terms to disambiguate ambiguous extractions, degrade gracefully when unavailable
- Wire value_map normalization into `plan_updater` — normalize filter values through dictionary mappings before accumulation
- Add `MetricFragment` dataclass to `sql_compiler`: `select_expr`, `join_clause`, `requires_group_by`
- Update `compile_query()` to accept metrics list and inject `{select_extras}` / `{join_extras}` tokens, add GROUP BY when required
- Keyword-based metric detection stub (full LLM detection deferred)
- 4 end-to-end integration tests: glossary pipeline, value_map pipeline, metric pipeline, full semantic pipeline

---

## Phase 8: Context-Aware Hybrid AI Query System

### HYB-01: GraphState Extension for Hybrid Mode
- Extend `GraphState` TypedDict with: session_id, last_query, last_query_embedding, current_query_embedding, semantic_similarity, follow_up_type, confidence_breakdown
- Store as dict (following Phase 6/7 pattern), not raw Pydantic

### HYB-02: Session and Embedding Storage
- Store session_id across conversation turns
- Store last_query_embedding for similarity comparison
- Compute current_query_embedding at classify_intent

### HYB-03: Follow-up Detection Node
- Create `detect_followup_type()` function
- Inputs: current_query_embedding, last_query_embedding, current_intent, last_intent
- Returns: "refine" | "replace" | "new"
- Semantic similarity > 0.7 = "refine"
- Intent mismatch = "new"

### HYB-04: Semantic Similarity Calculation
- Use cosine similarity between embeddings
- Store semantic_similarity in GraphState for observability

### HYB-05: Follow-up Type Classification
- "refine": semantic_similarity > 0.7 and same intent
- "replace": same field detected in filters
- "new": intent mismatch or low similarity

### HYB-06: LLM Structured Extraction (Single Call)
- Single LLM call per query (not per filter)
- Strict JSON output: {filters, sort, limit, follow_up_type}
- No explanation, no hallucinated fields
- Uses Llama 3.3 70B (already configured as DEFAULT_LLM_MODEL)

### HYB-07: JSON Extraction with Field Validation
- Validate extracted fields against FieldRegistry
- Drop unknown fields safely
- Use semantic_resolver to map user terms to canonical names

### HYB-08: Confidence Scoring
- calculate_confidence(extracted, valid_fields, matches_schema) returns float
- Formula: valid_json (+0.3) + valid_fields (+0.3) + matches_schema (+0.4)
- Thresholds: >= 0.7 = accept, >= 0.4 = partial fallback, < 0.4 = full ladder

### HYB-09: Confidence Decision Routing
- >= 0.7: Use LLM extraction directly
- >= 0.4: Partial fallback (use some filters, heuristic for others)
- < 0.4: Trigger full fallback ladder

### HYB-10: Deterministic Override Layer
- Deterministic rules ALWAYS override LLM output
- Intent mismatch: current_intent != last_intent → force follow_up_type = "new"
- Created function: apply_overrides(extracted, state)

### HYB-11: Override Observability
- Log when overrides are applied for debugging
- Mark overrides_applied flag in state

### HYB-12: Conflict Resolution
- resolve_conflicts(new_filters, existing_filters) returns merged filters
- Same field → REPLACE (remove existing, add new)
- Different field → ADD (append new)
- Validate against FieldRegistry

### HYB-13: Field Validation in Conflict Resolution
- All fields must exist in semantic layer (FieldRegistry)
- All fields must match intent schema (domain compatibility)

### HYB-14: 6-Level Fallback Ladder
- execute_fallback_ladder(question, state, current_filters, failure_reason)
- Level 1: Retry LLM (stronger prompt)
- Level 2: Heuristic extraction (KNOWN_* constants)
- Level 3: Context recovery (infer from tokens)
- Level 4: Partial execution (run with partial filters)
- Level 5: Clarification (return ask_user prompt)
- Level 6: Full LLM fallback (generate SQL)

### HYB-15: Fallback Trigger Conditions
- confidence < 0.4: Start at level 3
- JSON parse failure: Start at level 2
- Invalid fields: Start at level 2

### HYB-16: Level 2 Heuristic Extraction
- Reuse patterns from param_extractor.py
- KNOWN_SKILLS, KNOWN_STATUS, KNOWN_DATES
- Map to FilterClause with appropriate operators

### HYB-17: Level 3 Context Recovery
- recover_from_context(question, last_filters)
- Tokenize question
- Match against KNOWN_PATTERNS
- Return inferred filters or empty list

### HYB-18: Level 5 Clarification
- Return structured clarification request when all levels fail
- User-friendly prompt asking for missing information

### HYB-19: Graceful Degradation
- System never crashes
- Always returns result or clarification request
- Logs fallback progression for observability

### HYB-20: Query Caching
- Cache key = hash(intent + filters + sort)
- get_cached_result(key) returns cached result or None
- cache_result(key, result) stores with TTL
- LRU eviction on max size (default 1000)

### HYB-21: Cache Integration
- Check cache after followup_detection, before llm_extraction
- Cache hit → skip LLM extraction entirely

### HYB-22: Observability Logging
- log_query_context(query, intent, filters, follow_up_type, confidence, final_sql, fallback_used)
- log_fallback_event(level, reason, extracted_filters)
- All logs in structured JSON format

### HYB-23: Semantic Integration Node
- get_field_hints(domain): Returns available fields from glossary
- normalize_filter_value(field, user_value): Maps user-friendly to DB values

### HYB-24: Glossary Integration with Extraction
- Use glossary hints to validate/map user terms
- "dev" → ResourceName, "skill" → PA_Skills.Name

### HYB-25: Dictionary Integration
- Use value_map for filter value normalization
- Load at startup (already done in Phase 7)

### HYB-26: End-to-End Hybrid Pipeline
- Full graph wiring: classify → followup_detection → llm_extraction → confidence_scoring → deterministic_override → conflict_resolution → plan_updater → run_domain_tool
- Fallback ladder at appropriate points
- Cache check before LLM extraction
- Observability at pipeline end

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| LG-01 | Phase 5 | Complete |
| LG-02 | Phase 5 | Complete |
| LG-03 | Phase 5 | Complete |
| LG-04 | Phase 5 | Complete |
| LG-05 | Phase 5 | Complete |
| LG-06 | Phase 5 | Complete |
| LG-07 | Phase 5 | Complete |
| LG-08 | Phase 5 | Complete |
| LG-09 | Phase 5 | Complete |
| LG-10 | Phase 5 | Complete |
| LG-11 | Phase 5 | Complete |
| LG-12 | Phase 5 | Complete |
| LG-13 | Phase 5 | Complete |
| LG-14 | Phase 5 | Complete |
| LG-15 | Phase 5 | Complete |
| LG-16 | Phase 5 | Complete |
| QP-01 | Phase 7 | Planned |
| QP-02 | Phase 7 | Planned |
| QP-03 | Phase 7 | Planned |
| QP-04 | Phase 7 | Planned |
| HYB-01 | Phase 8 | Planned |
| HYB-02 | Phase 8 | Planned |
| HYB-03 | Phase 8 | Planned |
| HYB-04 | Phase 8 | Planned |
| HYB-05 | Phase 8 | Planned |
| HYB-06 | Phase 8 | Planned |
| HYB-07 | Phase 8 | Planned |
| HYB-08 | Phase 8 | Planned |
| HYB-09 | Phase 8 | Planned |
| HYB-10 | Phase 8 | Planned |
| HYB-11 | Phase 8 | Planned |
| HYB-12 | Phase 8 | Planned |
| HYB-13 | Phase 8 | Planned |
| HYB-14 | Phase 8 | Planned |
| HYB-15 | Phase 8 | Planned |
| HYB-16 | Phase 8 | Planned |
| HYB-17 | Phase 8 | Planned |
| HYB-18 | Phase 8 | Planned |
| HYB-19 | Phase 8 | Planned |
| HYB-20 | Phase 8 | Planned |
| HYB-21 | Phase 8 | Planned |
| HYB-22 | Phase 8 | Planned |
| HYB-23 | Phase 8 | Planned |
| HYB-24 | Phase 8 | Planned |
| HYB-25 | Phase 8 | Planned |
| HYB-26 | Phase 8 | Planned |
