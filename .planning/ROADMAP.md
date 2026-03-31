# QueryWise Roadmap

## Phases

- [x] **Phase 1: Foundation** - Basic FastAPI setup, LLM providers, semantic layer, connection management
- [x] **Phase 5: LangGraph Domain Tool Pipeline** - Replace LLM SQL generation with embedding-based intent classification and PRMS domain tools (completed 2026-03-26)
- [ ] **Phase 6: Context-Aware Domain Tools** - Stateful follow-up handling, TurnContext propagation, domain tool subquery refinement, fallback_intent wiring

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

### Phase 6: Context-Aware Domain Tools & Stateful Follow-Up

**Goal:** Make the LangGraph pipeline stateful across conversation turns so follow-up queries ("Which of these know Python?", "Filter by active only") route to domain tools instead of falling back to LLM — by adding structured TurnContext propagation, follow-up detection in intent classification, param inheritance in param extraction, subquery-based domain tool refinement mode, and fallback_intent wiring for 0-row results
**Status:** Planned
**Depends on:** Phase 5
**Requirements**: CTX-01, CTX-02, CTX-03, CTX-04, CTX-05, CTX-06, CTX-07, CTX-08, CTX-09, CTX-10
**Success Criteria**:
  1. Follow-up queries like "Which of these know Python?" after "Show benched resources" route to domain tool (not LLM) via subquery refinement
  2. Params from prior turn carry forward to follow-up params extraction when not overridden
  3. Intent classifier detects thin follow-up patterns and inherits prior domain/intent with high confidence
  4. 0-row domain tool results try a configured fallback_intent before escalating to LLM (all 29 catalog entries have fallback_intent set)
  5. Backend API response includes structured turn_context (intent, domain, params, columns, sql)
  6. chatbot-frontend ChatPanel and StandaloneChatPage send last_turn_context on every follow-up request
  7. chatbot-frontend ChatPanel sends session_id (currently missing)

**Plans:** 2/5 plans executed

Plans:
- [ ] 06-01-PLAN.md — TurnContext schema foundation (backend schemas, GraphState, query_service, endpoint)
- [ ] 06-02-PLAN.md — fallback_intent wiring for all 24 active catalog entries
- [ ] 06-03-PLAN.md — Context-aware classify_intent (follow-up fast path) + param inheritance in extract_params
- [ ] 06-04-PLAN.md — Domain tool subquery refinement (base_domain helpers + ResourceAgent._run_refinement)
- [ ] 06-05-PLAN.md — Frontend TurnContext tracking (types, queryApi, ChatWidget session, ChatPanel, StandaloneChatPage)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | N/A | Complete | 2026-03-01 |
| 5. LangGraph Domain Tool Pipeline | 5/5 | Complete | 2026-03-26 |
| 6. Context-Aware Domain Tools | 2/5 | In Progress|  |
