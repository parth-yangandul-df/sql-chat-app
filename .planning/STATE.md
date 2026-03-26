# QueryWise Project State

**Current State:** Active development
**Last Updated:** 2026-03-26
**Phase Focus:** Phase 5 — LangGraph Domain Tool Pipeline
**Current Plan:** 05-02 (Plan 1 of 5 complete)

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

### Phase 5 Plan 01 Decisions (2026-03-26)
- Patched embed_text at usage site (app.llm.graph.intent_catalog) not definition site for correct mock isolation in tests
- Reset _catalog_embedded global in idempotency test for deterministic test ordering

### Phase 5 Key Decisions
- Intent catalog is code-only (no DB-backed admin config in this phase)
- Routing transparency via Python `logging` only — no user-facing indicator
- `TOOL_CONFIDENCE_THRESHOLD` env var (default 0.78) controls routing gate
- 0-row results: try `fallback_intent` (1 hop max) → then `llm_fallback`
- SQL execution errors → immediate AppError, no LLM retry
- Embedding failure → graceful degradation to full LLM mode (no 503)
- SQLServer `_run_query()` params bug must be fixed in Plan 03 before domain agents work
- All 24 SQL templates use bare table names (no `dbo.` prefix)
- `generate_sql_only()` and `execute_raw_sql()` completely untouched

### Code Style
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
| 05-02 | Intent classifier + param extractor | Not started |
| 05-03 | SQLServer bug fix + 4 domain agents + registry | Not started |
| 05-04 | result_interpreter, llm_fallback, write_history, graph assembly | Not started |
| 05-05 | Wire into query_service.py + startup hook + full test suite | Not started |

## Last Session
- **Stopped at:** Completed 05-01-PLAN.md
- **Resume file:** None
