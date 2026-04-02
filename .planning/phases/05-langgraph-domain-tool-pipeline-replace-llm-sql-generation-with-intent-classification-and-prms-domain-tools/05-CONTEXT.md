# Phase 05: LangGraph Domain Tool Pipeline — Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace `execute_nl_query()` in `query_service.py` with a LangGraph `StateGraph` pipeline that routes NL questions to 24 pre-built PRMS domain SQL tools (embedding-based intent classification) or falls back to the existing LLM generation chain. Operates on a `feature/langgraph-domain-tools` branch only — the `dev` branch pipeline remains unchanged.

Creating new UI, adding new API endpoints, or expanding the PRMS schema beyond the 24 defined intents are out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Intent Catalog Extensibility
- Intents are code-only: defined in `intent_catalog.py`, require a code change + redeploy to add new ones
- No DB-backed or admin-configurable catalog in this phase
- Each `IntentEntry` gets two new optional fields:
  - `sql_fallback_template: str | None` — runs when param extraction fails but confidence is high (avoids LLM fallback for known high-confidence intents with missing params)
  - `fallback_intent: str | None` — name of a broader/related intent to try when primary returns 0 rows
- One primary SQL template per intent; fallback template is optional, not required

### Routing Transparency (Logging)
- No user-facing routing indicator — end users don't need to know which path ran
- Developer visibility via **Python `logging`** in the `classify_intent` node:
  - Log fields: `question[:80]`, `domain`, `intent`, `confidence`, `route_taken`
  - `INFO` level when routing to `domain_tool`
  - `WARNING` level when falling back to `llm_fallback` (low confidence or failed extraction)
- Langfuse spans for classify_intent, domain_tool, and llm_fallback are deferred to Phase 2 (Langfuse integration phase)
- `llm_provider` field in response dict already distinguishes paths: `"domain_tool"` vs real LLM name

### SQL Server Param Binding — Critical Fix Required
- **Bug found:** `SQLServerConnector.execute_query()` at `backend/app/connectors/sqlserver/connector.py` accepts `params` but `_run_query()` calls `cursor.execute(sql)` with **no params** — the argument is completely ignored
- **Fix required in this phase:** Update `_run_query()` signature to accept params tuple and pass to `cursor.execute(sql, params_tuple)`
- **Domain tool param style:** `BaseDomainAgent` passes params as a positional **tuple** (values in `param_keys` order)
- `execute_query()` signature updated: `params: tuple[Any, ...] | None = None` (also update `base_connector.py` abstract method signature)
- This fix is isolated to `sqlserver/connector.py` and `base_connector.py`

### SQL Template Schema Prefixes
- All 24 SQL templates use **bare table names** (e.g., `Resource`, `ProjectResource`, `TS_EODDetails`) — no `dbo.` prefix
- SQL Server resolves unqualified names to the user's default schema automatically
- SQL Server identifier matching is case-insensitive by default — no casing normalization needed

### Empty Result & Fallback Handling (Updated Graph Topology)
- **SQL execution error** (exception, invalid SQL, connection failure) → immediate `AppError` — no retry, no LLM fallback
- **0 rows returned** from domain tool → follow this chain:
  1. If `IntentEntry.fallback_intent` is defined, run that intent's SQL (1 hop maximum — no chaining beyond 1 to prevent loops)
  2. If fallback intent also returns 0 rows (or no fallback_intent defined) → route to `llm_fallback` node as last resort
  3. LLM fallback produces its own result or error response
- This introduces a **new conditional edge** after `run_domain_tool`: checks `result.row_count == 0`
- `interpret_result` node is only reached when there are actual rows to interpret
- LLM fallback is the final escalation path — it is not bypassed for 0-row scenarios

### Embedding Unavailability (Graceful Degradation)
- If `ensure_catalog_embedded()` fails at startup (embedding provider offline) → **log a warning and skip** — app starts normally
- First incoming query triggers a lazy re-attempt of `ensure_catalog_embedded()`
- If lazy init also fails → `classify_intent` catches the exception and routes to `llm_fallback` (mirrors existing pattern in `schema_linker.py:_vector_search_tables` which falls back gracefully on vector failure)
- No 503 responses, no hard startup failure — the pipeline degrades gracefully to full LLM mode

### Claude's Discretion
- Exact logging format/structure within the Python `logging` calls
- Specific intents that receive `fallback_intent` or `sql_fallback_template` assignments (implementation can decide based on which intents have parametric SQL)
- `asyncio.Lock` implementation detail for catalog embedding race condition
- Whether `_run_query` receives params as a second positional arg or keyword arg (pyodbc/aioodbc convention)

</decisions>

<specifics>
## Specific Ideas

- Logging: `WARNING` on LLM fallback (not just INFO) — developers should notice when the classifier isn't routing confidently
- The fallback chain for 0-row results ultimately ends at LLM fallback — don't silently return empty results to the user if there's a smarter path available
- SQL templates should remain readable in `intent_catalog.py` — no dynamic SQL building beyond the pre-defined templates

</specifics>

<code_context>
## Existing Code Insights

### Critical Bug Found
- `backend/app/connectors/sqlserver/connector.py` — `_run_query(self, sql: str)` ignores params entirely. Must be fixed in this phase before domain tools can work.
- `backend/app/connectors/base_connector.py` — abstract `execute_query()` signature will need updating to match the new tuple-based params

### Reusable Assets
- `embed_text()` in `app/services/embedding_service.py` — fully async, provider-agnostic; used by intent classifier
- `schema_linker.py:_vector_search_tables` — existing pattern for graceful embedding fallback; mirror this in `classify_intent`
- `ResultInterpreterAgent`, `QueryComposerAgent`, `SQLValidatorAgent`, `ErrorHandlerAgent` — all wrapped unchanged as passthrough nodes
- `QueryExecution` model in `app/db/models/query_history.py` — unchanged for history writing
- `get_or_create_connector()` in `connector_registry.py` — used by domain agents to get the SQL Server connector
- `_serialize_rows()` in `query_service.py` — unchanged helper, still used in final response mapping

### Established Patterns
- Async everywhere: all nodes must be `async def` functions
- LangGraph nodes return `dict` of updated state keys (not mutate in-place)
- `asyncio.Lock` for catalog embedding idempotency (prevent concurrent embed on first call)
- Graceful degradation: vector/embedding failures fall back silently, never crash the pipeline
- `logging.getLogger(__name__)` pattern used throughout backend

### Integration Points
- `backend/app/main.py` lifespan hook: `ensure_catalog_embedded()` called after `ensure_embedding_dimensions()`, before `auto_setup_sample_db()` — wrapped in try/except for graceful failure
- `backend/app/services/query_service.py:execute_nl_query()` — replaced with `get_compiled_graph().ainvoke(initial_state)` while keeping `generate_sql_only()` and `execute_raw_sql()` completely unchanged
- `backend/app/llm/graph/` — new package: `state.py`, `intent_catalog.py`, `graph.py`, `nodes/`, `domains/`
- Response dict shape is preserved exactly (same 17 keys) for API compatibility

### Updated LangGraph Graph Topology (differs from original 5 plans)
```
classify_intent
    ├─ confidence >= threshold → run_domain_tool
    │                                ├─ rows > 0 → interpret_result → write_history → END
    │                                └─ 0 rows + fallback_intent? → run_fallback_intent
    │                                                    ├─ rows > 0 → interpret_result
    │                                                    └─ 0 rows → llm_fallback
    └─ confidence < threshold → llm_fallback → interpret_result → write_history → END
```
Note: The existing 5 plans have a simpler topology without the 0-row conditional edge. Plans must be rewritten to reflect this topology.

</code_context>

<deferred>
## Deferred Ideas

- Langfuse spans for classify_intent, domain_tool, llm_fallback nodes — Phase 2 (Langfuse integration)
- DB-backed admin-configurable intent catalog — future phase
- Multi-turn clarification ("which skill did you mean?") when param extraction fails — future phase
- User-facing routing transparency (showing whether domain_tool or LLM was used) — future phase if requested
- Feature flag / rollback strategy beyond branch-based isolation — future phase

</deferred>

---

*Phase: 05-langgraph-domain-tool-pipeline*
*Context gathered: 2026-03-26*
