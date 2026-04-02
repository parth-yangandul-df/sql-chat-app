# QueryWise Roadmap

## Phases

- [x] **Phase 1: Foundation** - Basic FastAPI setup, LLM providers, semantic layer, connection management
- [x] **Phase 5: LangGraph Domain Tool Pipeline** - Replace LLM SQL generation with embedding-based intent classification and PRMS domain tools (completed 2026-03-26)
- [x] **Phase 6: Context-Aware Domain Tools** - Stateful follow-up handling, TurnContext propagation, domain tool subquery refinement, fallback_intent wiring (completed 2026-04-02)
- [ ] **Phase 7: QueryPlan Compiler** - Replace SQL subquery wrapping with a structured QueryPlan state model that accumulates typed filters across turns and compiles SQL deterministically (in progress)

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
**Status:** Complete (2026-03-26)
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
- [x] 05-05-PLAN.md — Wire graph into query_service.py + startup hook + full test suite

### Phase 6: Context-Aware Domain Tools & Stateful Follow-Up

**Goal:** Make the LangGraph pipeline stateful across conversation turns so follow-up queries ("Which of these know Python?", "Filter by active only") route to domain tools instead of falling back to LLM — by adding structured TurnContext propagation, follow-up detection in intent classification, param inheritance in param extraction, subquery-based domain tool refinement mode, and fallback_intent wiring for 0-row results
**Status:** Complete (2026-04-02)
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

**Plans:** 5/5 plans executed

Plans:
- [x] 06-01-PLAN.md — TurnContext schema foundation (backend schemas, GraphState, query_service, endpoint)
- [x] 06-02-PLAN.md — fallback_intent wiring for all 24 active catalog entries
- [x] 06-03-PLAN.md — Context-aware classify_intent (follow-up fast path) + param inheritance in extract_params
- [x] 06-04-PLAN.md — Domain tool subquery refinement (base_domain helpers + ResourceAgent._run_refinement)
- [x] 06-05-PLAN.md — Frontend TurnContext tracking (types, queryApi, ChatWidget session, ChatPanel, StandaloneChatPage)

### Phase 7: QueryPlan Compiler

**Goal:** Replace SQL subquery wrapping with a structured QueryPlan state model that accumulates typed filters across conversation turns and compiles SQL deterministically — with zero RBAC regressions, a safe feature-flag rollout (`USE_QUERY_PLAN_COMPILER`), and full regression test coverage before retiring the old path.
**Status:** Not Started
**Depends on:** Phase 6
**Requirements**: QP-01, QP-02, QP-03, QP-04

**Plans:** 4/4 plans planned

Plans:
- [ ] 07-01-PLAN.md — QueryPlan Foundation (query_plan.py, GraphState, query_service, feature flag)
- [ ] 07-02-PLAN.md — Filter Extraction + Plan Update (FieldRegistry, filter_extractor, plan_updater, graph wiring)
- [ ] 07-03-PLAN.md — SQL Compiler + Domain Agent Rewrite (sql_compiler, base_domain flag, regression tests, retirements)
- [ ] 07-04-PLAN.md — Semantic Layer Executable (glossary→filters, dict value_map, metric injection)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | N/A | Complete | 2026-03-01 |
| 5. LangGraph Domain Tool Pipeline | 5/5 | Complete | 2026-03-26 |
| 6. Context-Aware Domain Tools | 5/5 | Complete | 2026-04-02 |
| 7. QueryPlan Compiler | 0/4 | Not Started | — |
