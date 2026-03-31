---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: Not started
status: unknown
stopped_at: Completed 06-05-PLAN.md
last_updated: "2026-03-31T12:38:00.784Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 15
  completed_plans: 9
---

# QueryWise Project State

**Current State:** Active development
**Last Updated:** 2026-03-26
**Phase Focus:** Phase 5 — LangGraph Domain Tool Pipeline ✅ COMPLETE
**Current Plan:** Not started

## Project Architecture

QueryWise is a text-to-SQL application with semantic metadata layer. Users ask natural language questions, LLM generates SQL using business context, executes against database, returns human-readable answers.

### Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), asyncpg, pgvector
- **Frontend:** React 19, TypeScript, Vite, Mantine UI
- **Databases:** PostgreSQL with pgvector extension (app DB), SQL Server (PRMS target DB)
- **LLM:** Provider-agnostic (Anthropic Claude, OpenAI, Ollama)

### Current Request Flow (Phase 5 target)
User → FastAPI → LangGraph pipeline → classify_intent → [domain tool | llm_fallback] → interpret_result → write_history → Response

## Decisions Made

### Architecture
- SQLAlchemy ORM with async patterns
- UUID primary keys, timestamps on all models
- Provider-agnostic LLM interface
- Context building with semantic search using pgvector
- LangGraph StateGraph replaces direct `execute_nl_query()` logic
- [Phase 05]: execute_nl_query() delegates entirely to get_compiled_graph().ainvoke() — old LLM pipeline code removed (180 lines -> 50 lines)
- [Phase 05]: ensure_catalog_embedded() placed in lifespan between ensure_embedding_dimensions() and auto_setup_sample_db() so embeddings ready before seeded data triggers queries
- [Phase 06-01]: GraphState stores last_turn_context as dict | None (not TurnContext) to avoid importing Pydantic models into graph layer
- [Phase 06-01]: turn_context in response is None when no intent+domain resolved (LLM fallback path)
- [Phase 06-context-aware-domain-tools]: 6 broadest entries keep fallback_intent=None: active_resources, benched_resources, active_clients, active_projects, approved_timesheets, my_projects — no broader fallback exists within the domain
- [Phase 06-05]: lastTurnContext lifted to ChatWidget (not local to ChatPanel) so state survives panel AnimatePresence unmount/remount cycles
- [Phase 06-05]: turn_context: null added to reconstructed QueryResult in buildMessagesFromHistory — history items from API never carry turn_context (only live pipeline does)

### Phase 5 Plan 01 Decisions (2026-03-26)
- Patched embed_text at usage site (app.llm.graph.intent_catalog) not definition site for correct mock isolation in tests
- Reset _catalog_embedded global in idempotency test for deterministic test ordering

### Phase 5 Plan 02 Decisions (2026-03-26)
- Patch ensure_catalog_embedded (not just embed_text) in classifier tests — classify_intent calls it when catalog has empty embeddings, using a different import binding than the node-level mock
- extract_params is async to conform to LangGraph node signature convention, even though no I/O is performed


### Phase 5 Plan 03 Decisions (2026-03-26)
- BaseConnector.execute_query() params changed from dict[str, Any] | None to tuple[Any, ...] | None to align with SQL Server ? positional placeholder style
- BaseDomainAgent.execute() uses state["intent"] or "" guard to safely pass str to _run_intent() when GraphState.intent is str | None
- TimesheetAgent uses module-level _VALID constant for consistent IsApproved/IsDeleted/IsRejected filter across all valid-entry intents

- Intent catalog is code-only (no DB-backed admin config in this phase)
- Routing transparency via Python `logging` only — no user-facing indicator
- `TOOL_CONFIDENCE_THRESHOLD` env var (default 0.78) controls routing gate
- 0-row results: try `fallback_intent` (1 hop max) → then `llm_fallback`
- SQL execution errors → immediate AppError, no LLM retry
- Embedding failure → graceful degradation to full LLM mode (no 503)
- SQLServer `_run_query()` params bug must be fixed in Plan 03 before domain agents work
- All 24 SQL templates use bare table names (no `dbo.` prefix)
- `generate_sql_only()` and `execute_raw_sql()` completely untouched

### Phase 5 Plan 04 Decisions (2026-03-26)
- Patch llm_fallback at app.llm.graph.graph.llm_fallback (usage site in graph.py) not app.llm.graph.nodes.llm_fallback.llm_fallback (definition site) — graph.py imports function reference directly, patch must be at consuming module
- result_interpreter.py uses typed annotation sql: str = state.get("sql") or "" to satisfy type checker for str | None -> str coercion


- Python: Ruff, 100 char line length
- TypeScript: ESLint, strict mode
- Async everywhere for DB operations and LLM calls

## Current Environment Variables
- DATABASE_URL, ENCRYPTION_KEY
- DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL
- EMBEDDING_MODEL, EMBEDDING_DIMENSION
- CORS_ORIGINS, AUTO_SETUP_SAMPLE_DB
- TOOL_CONFIDENCE_THRESHOLD (new in Phase 5, default 0.78)

## Known Constraints
- Feature work on `feature/langgraph-domain-tools` branch only — `dev` branch pipeline unchanged
- SQL Server: parameterized queries use `?` positional placeholders (pyodbc/aioodbc)
- Timesheet valid entries: `IsApproved=1 AND IsDeleted=0 AND IsRejected=0`
- Status table filter: `ReferenceId=1` (Client), `ReferenceId=2` (Project), `ReferenceId=3` (Resource)
- Langfuse spans deferred to a future phase

## Phase 5 Progress

| Plan | Description | Status |
|------|-------------|--------|
| 05-01 | Feature branch, GraphState, 24-intent catalog, test scaffolding | ✅ Complete (2026-03-26) |
| 05-02 | Intent classifier + param extractor | ✅ Complete (2026-03-26) |
| 05-03 | SQLServer bug fix + 4 domain agents + registry | ✅ Complete (2026-03-26) |
| 05-04 | result_interpreter, llm_fallback, write_history, graph assembly | ✅ Complete (2026-03-26) |
| 05-05 | Wire into query_service.py + startup hook + full test suite | ✅ Complete (2026-03-26) |

## Accumulated Context

### Pending Todos (5)

- **Build QueryWise chat widget for Angular embedding** (`ui`) — `2026-03-30-build-querywise-chat-widget-for-angular-embedding.md`
- **Implement RBAC with JWT auth admin manager user roles** (`auth`) — `2026-03-30-implement-rbac-with-jwt-auth-admin-manager-user-roles.md`
- **Scaffold Angular 21 test app with widget integration** (`general`) — `2026-03-30-scaffold-angular-21-test-app-with-widget-integration.md`
- **Fix recent questions to be user-specific via token handoff** (`ui`) — `2026-03-31-fix-recent-questions-to-be-user-specific-via-token-handoff.md`
- **Build standalone dedicated chatbot page for Angular redirect** (`ui`) — `2026-03-31-build-standalone-dedicated-chatbot-page-for-angular-redirect.md`

## Last Session
- **Stopped at:** Completed 06-05-PLAN.md
- **Resume file:** None
