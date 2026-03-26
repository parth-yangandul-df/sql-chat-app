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
| LG-15 | Phase 5 | Pending |
| LG-16 | Phase 5 | Pending |
