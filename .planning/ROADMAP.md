# QueryWise Roadmap

## Phases

- [x] **Phase 1: Foundation** - Basic FastAPI setup, LLM providers, semantic layer, connection management
- [x] **Phase 5: LangGraph Domain Tool Pipeline** - Replace LLM SQL generation with embedding-based intent classification and PRMS domain tools (completed 2026-03-26)

---

## Phase Details

### Phase 1: Foundation
**Goal**: Core application infrastructure running end-to-end
**Status:** Complete
**Depends on**: Nothing
**Requirements**: N/A (pre-planning)
**Success Criteria**:
  1. FastAPI server starts and serves API requests
  2. LLM providers (Anthropic, OpenAI, Ollama) are configurable via env vars
  3. Semantic layer (glossary, metrics, dictionary) stores and retrieves metadata
  4. Database connections can be created, tested, and used to execute queries
**Plans**: N/A

---

### Phase 5: LangGraph Domain Tool Pipeline
**Goal**: Replace `execute_nl_query()` with a LangGraph `StateGraph` that routes NL questions to 24 pre-built PRMS domain SQL tools (via embedding-based intent classification) or falls back to the existing LLM generation chain
**Status:** In Progress
**Depends on**: Phase 1
**Requirements**: LG-01, LG-02, LG-03, LG-04, LG-05, LG-06, LG-07, LG-08, LG-09, LG-10, LG-11, LG-12, LG-13, LG-14, LG-15, LG-16
**Success Criteria**:
  1. NL questions matching a known PRMS intent route to domain SQL tools without LLM generation
  2. Low-confidence questions fall back to the existing LLM pipeline transparently
  3. 0-row domain tool results attempt a fallback intent before escalating to LLM
  4. SQL Server params bug is fixed — parameterized queries execute correctly
  5. Embedding unavailability degrades gracefully (app starts, pipeline routes to LLM fallback)
  6. `generate_sql_only()` and `execute_raw_sql()` are completely unchanged

**Plans**:
- [x] 05-01-PLAN.md — Feature branch, LangGraph deps, GraphState, 24-intent catalog, test scaffolding
- [x] 05-02-PLAN.md — Intent classifier node (cosine similarity) + param extractor node
- [x] 05-03-PLAN.md — SQLServer connector bug fix + 4 PRMS domain agents + domain registry
- [x] 05-04-PLAN.md — result_interpreter, llm_fallback, write_history nodes + graph assembly (with 0-row topology)
- [ ] 05-05-PLAN.md — Wire graph into query_service.py + startup hook + full test suite

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | N/A | Complete | 2026-03-01 |
| 5. LangGraph Domain Tool Pipeline | 5/5 | Complete   | 2026-03-26 |
