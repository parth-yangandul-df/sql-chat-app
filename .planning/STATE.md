---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 07-04 complete
status: phase_complete
stopped_at: Phase 07 complete
last_updated: "2026-04-06T00:00:00.000Z"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 19
  completed_plans: 19
---

# QueryWise Project State

**Current State:** Phase 07 complete — QueryPlan Compiler 4/4 plans executed
**Last Updated:** 2026-04-06
**Phase Focus:** Phase 7 — QueryPlan Compiler ✅ COMPLETE
**Current Plan:** 07-04 complete

## Project Architecture

QueryWise is a text-to-SQL application with semantic metadata layer. Users ask natural language questions, LLM generates SQL using business context, executes against database, returns human-readable answers.

### Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), asyncpg, pgvector, aioodbc
- **Frontend:** React 19, TypeScript, Vite, Mantine UI, TanStack Query
- **Databases:** PostgreSQL with pgvector extension (app DB), SQL Server (PRMS target DB)
- **LLM:** Provider-agnostic (Anthropic Claude, OpenAI, Ollama, Groq)
- **Embeddings:** Ollama nomic-embed-text (768-dim)

### Current Request Flow
User → FastAPI → LangGraph pipeline → classify_intent → extract_filters → update_query_plan → [domain tool | llm_fallback] → interpret_result → write_history → Response

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
- [Phase 06-03]: Two-signal detection gate: deictic phrase + refinement keyword both required to avoid false positives on follow-up detection
- [Phase 06-03]: _refine_mode only set on same-intent follow-up — intent switch carries params forward but runs fresh classification (not refinement)
- [Phase 06-04]: ORDER BY stripped with re.DOTALL flag — regex strips from first ORDER BY to end of string, correct for simple resource queries used as prior SQL
- [Phase 06-04]: _run_refinement() default in BaseDomainAgent falls back to _run_intent() — ProjectAgent, ClientAgent, TimesheetAgent, UserSelfAgent require zero changes
- [Phase 07-01]: QueryPlan stored as dict in GraphState (consistent with Phase 6 last_turn_context pattern)
- [Phase 07-01]: query_service passes through QueryPlan without checking feature flag — flag is for upstream graph nodes to check
- [Phase 07-02]: route_after_classify returns "extract_params" key — remapped in add_conditional_edges to "extract_filters" node (no change needed in classifier)
- [Phase 07-02]: filters stored as list[FilterClause] in GraphState (not serialized to dict — only query_plan is dict)
- [Phase 07-02]: skill is the only multi_value=True field — all others are last-wins
- [Phase 07-02]: _SKILL_WORD_BEFORE_RE added beyond param_extractor patterns: catches "Python skill" phrasing
- [Phase 07-queryplan-compiler]: Lazy imports in execute() enable test isolation via importlib.reload()
- [Phase 07-queryplan-compiler]: Text field IN filter uses OR chain of LIKE clauses (not IN) — text search requires wildcard matching
- [Phase 07-queryplan-compiler]: param_extractor.py kept at original path for test compatibility; archived to _deprecated/ for audit trail
- [Phase 07-04]: semantic_resolver uses module-level value_map cache loaded at startup via load_value_map(); get_cached_value_map() returns synchronously for zero per-query DB hits
- [Phase 07-04]: MetricFragment is a dataclass (not Pydantic) in sql_compiler.py; detect_metrics() returns [] stub — LLM-based detection deferred to future phase

### Phase 07 Post-Execution Decisions (2026-04-06)
- [QueryPlan]: QueryPlan + FilterClause Pydantic v2 models with SQL injection guards and schema_version=1
- [FieldRegistry]: 22 canonical fields across 5 domains; `skill` is the only `multi_value=True` field — all others are last-wins
- [Graph Rewiring]: `route_after_classify` returns "extract_params" key — remapped in `add_conditional_edges` to `extract_filters` node (no change needed in classifier)
- [Feature Flag]: `USE_QUERY_PLAN_COMPILER=false` (default); flag=ON routes through `sql_compiler.py`, flag=OFF preserves `_try_refinement()` path
- [Retirement]: `refinement_registry.py` kept with DEPRECATED header for rollback safety; `param_extractor.py` moved to `_deprecated/` with README
- [Semantic Layer]: `semantic_resolver.py` has module-level `value_map` cache loaded at startup via `load_value_map()`; all DB calls degrade gracefully; `MetricFragment` is a dataclass (not Pydantic); `detect_metrics()` returns [] stub — LLM-based detection deferred

### Phase 06 Post-Execution Decisions (2026-04-02)
- [Refinement Registry]: 61 declarative refinement templates across 5 domains (resource, client, project, timesheet, user_self) covering skill, name, date range, status, numeric, boolean, text filter types
- [BaseDomainAgent]: Unified _try_refinement() with 3-tier priority: registry → subclass override → base intent
- [ResourceAgent]: Fixed EMPID column reference — both active_resources and benched_resources return EMPID alias, unified to prev.EMPID
- [Topic Switch Detection]: _is_topic_switch() in intent_classifier.py detects domain/intent switches to auto-clear context
- [Context Clearing]: query_service.py stores base SQL (_prior_sql) in turn_context instead of refined SQL to prevent parameter marker accumulation on chained refinements
- [API]: clear_context boolean flag in QueryRequest, topic_switch_detected in QueryResponse
- [Frontend]: ChatPanel context status badge, clear button, amber banner when context cleared
- [SQL Server]: aioodbc.create_pool(minsize=1, maxsize=5) replaces single connection for concurrent query safety
- [Docker]: extra_hosts mapping for host.docker.internal to reach Ollama on Windows host
- [Intent Catalog]: Improved project intent descriptions to reduce misclassification

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
- `TOOL_CONFIDENCE_THRESHOLD` env var (default 0.65) controls routing gate
- 0-row results: try `fallback_intent` (1 hop max) → then `llm_fallback`
- SQL execution errors → immediate AppError, no LLM retry
- Embedding failure → graceful degradation to full LLM mode (no 503)
- All 24 SQL templates use bare table names (no `dbo.` prefix)
- `generate_sql_only()` and `execute_raw_sql()` completely untouched

### Phase 5 Plan 04 Decisions (2026-03-26)
- Patch llm_fallback at app.llm.graph.graph.llm_fallback (usage site in graph.py) not app.llm.graph.nodes.llm_fallback.llm_fallback (definition site) — graph.py imports function reference directly, patch must be at consuming module
- result_interpreter.py uses typed annotation sql: str = state.get("sql") or "" to satisfy type checker for str | None -> str coercion

### Code Style
- Python: Ruff, 100 char line length
- TypeScript: ESLint, strict mode
- Async everywhere for DB operations and LLM calls

## Current Environment Variables
- DATABASE_URL, ENCRYPTION_KEY
- DEFAULT_LLM_PROVIDER=groq, DEFAULT_LLM_MODEL=llama-3.3-70b-versatile
- EMBEDDING_PROVIDER=ollama, EMBEDDING_MODEL=nomic-embed-text, EMBEDDING_DIMENSION=768
- CORS_ORIGINS, AUTO_SETUP_SAMPLE_DB
- TOOL_CONFIDENCE_THRESHOLD (default 0.65)
- OLLAMA_BASE_URL=http://host.docker.internal:11434

## Known Constraints
- Feature work on `langgraph` branch
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

## Phase 6 Progress

| Plan | Description | Status |
|------|-------------|--------|
| 06-01 | TurnContext schema foundation | ✅ Complete (2026-04-02) |
| 06-02 | fallback_intent wiring for all catalog entries | ✅ Complete (2026-04-02) |
| 06-03 | Context-aware classify_intent + param inheritance | ✅ Complete (2026-04-02) |
| 06-04 | Domain tool subquery refinement | ✅ Complete (2026-04-02) |
| 06-05 | Frontend TurnContext tracking | ✅ Complete (2026-04-02) |

## Phase 7 Progress

| Plan | Description | Status |
|------|-------------|--------|
| 07-01 | QueryPlan + FilterClause models, GraphState field, query_service wiring | ✅ Complete (2026-04-06) |
| 07-02 | FieldRegistry, filter_extractor, plan_updater, graph rewiring | ✅ Complete (2026-04-06) |
| 07-03 | param_extractor retirement + SQL template migration | ✅ Complete (2026-04-06) |
| 07-04 | LLM filter extraction fallback | ✅ Complete (2026-04-06) |

## Accumulated Context

### Pending Todos (5)

- **Build QueryWise chat widget for Angular embedding** (`ui`) — `2026-03-30-build-querywise-chat-widget-for-angular-embedding.md`
- **Implement RBAC with JWT auth admin manager user roles** (`auth`) — `2026-03-30-implement-rbac-with-jwt-auth-admin-manager-user-roles.md`
- **Scaffold Angular 21 test app with widget integration** (`general`) — `2026-03-30-scaffold-angular-21-test-app-with-widget-integration.md`
- **Fix recent questions to be user-specific via token handoff** (`ui`) — `2026-03-31-fix-recent-questions-to-be-user-specific-via-token-handoff.md`
- **Build standalone dedicated chatbot page for Angular redirect** (`ui`) — `2026-03-31-build-standalone-dedicated-chatbot-page-for-angular-redirect.md`

## Last Session
- **Stopped at:** Phase 07 complete
- **Resume file:** None
