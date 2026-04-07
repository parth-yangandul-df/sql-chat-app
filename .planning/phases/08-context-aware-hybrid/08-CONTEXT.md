# Phase 8: Context-Aware Hybrid AI Query System

**Gathered:** 2026-04-07
**Status:** Ready for planning
**Source:** PRD Express Path (docs/v2-context-refinement.md)

<domain>
## Phase Boundary

Upgrade QueryWise into a production-grade conversational query engine that maintains robust multi-turn context, uses deterministic logic wherever possible, uses LLM only where necessary (controlled + structured), minimizes cost and failure propagation, and compiles syntactically correct SQL via structured query plans (NOT raw LLM SQL).

**Phase 8 builds on:** Phase 7 (QueryPlan Compiler) — extends the deterministic SQL compilation with the full context-aware hybrid system from the v2 design.

</domain>

<decisions>
## Implementation Decisions

### Core Architecture
- LLM = Parser, NOT decision maker
- System state = source of truth
- Deterministic layers override LLM outputs
- Graceful degradation > hard failure
- Structured query plan → SQL compilation
- Context = structured state, NOT raw chat

### State Management (GraphState)
- Must include: session_id, last_query, last_query_embedding, last_intent, last_filters, last_query_plan, last_base_sql

### Intent Classification
- Use nomic-embed-text via Ollama
- Embed precomputed descriptions, compute cosine similarity
- If similarity < 0.6: intent = "unknown"

### Follow-up Detection (CRITICAL)
- Inputs: current query embedding, previous query embedding, previous intent
- Logic: refine (add filters), replace (same field), new (discard context)
- Semantic similarity > 0.7 = refine

### LLM Extraction
- Single call only
- STRICT JSON output, NO explanation, NO hallucinated fields
- Output schema: filters, sort, limit, follow_up_type

### Deterministic Override Layer
- Intent mismatch override: if current_intent != last_intent: follow_up_type = "new"
- Same field → REPLACE, Different field → ADD
- Field validation: Must exist in semantic layer, must match intent schema

### SQL Compilation
- DO NOT use LLM for SQL
- Use: base query registry, join registry, filter mapping
- Must ensure: valid joins, correct aliases, no duplicate joins, proper WHERE chaining

### Filter Extraction Fallback Ladder (6 levels)
1. Retry LLM (stronger prompt, stricter formatting)
2. Heuristic Extraction (KNOWN_* constants)
3. Context Recovery (infer from query tokens)
4. Partial Execution (run partial query)
5. Clarification (ask user)
6. Full LLM Fallback (only when intent unknown + extraction failed)

### Confidence Scoring
- valid_json: +0.3, valid_fields: +0.3, matches_schema: +0.4
- >= 0.7: accept, >= 0.4: partial fallback, else: fallback ladder

### Conflict Resolution
- Same field: REPLACE, Different field: ADD

### Semantic Layer Integration
- MUST use: glossary, metrics, dictionary
- Map user terms to DB columns

### Claude's Discretion
- Exact progress bar implementation
- Compression algorithm choice (if caching)
- Temp file handling
- Loading skeleton design
- Exact spacing and typography
- Error state handling

</decisions>

<specifics>
## Specific Ideas

- Never trust LLM output blindly
- Never generate SQL via LLM (except fallback)
- Always validate filters
- Always maintain base query integrity
- Always preserve context correctly

**Goals:**
- Transform from: rigid + fragile, regex dependent, high LLM cost
- Into: adaptive + context-aware, deterministic + controllable, cost-efficient, production-ready

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- GraphState in backend/app/llm/graph/state.py — extend with new keys
- FieldRegistry from Phase 7 — extend with all PRMS fields
- QueryPlan + FilterClause models from Phase 7 — reuse for structured plan
- sql_compiler.py from Phase 7 — base for deterministic compilation

### Established Patterns
- TypedDict for GraphState (not Pydantic) — follow Phase 6/7 pattern
- Feature flag pattern: USE_QUERY_PLAN_COMPILER — extend for hybrid mode
- Graceful degradation: embedding failure → LLM fallback
- Domain agents: BaseDomainAgent with execute() returning structured results

### Integration Points
- Extend existing LangGraph pipeline with new nodes
- Reuse semantic_resolver.py from Phase 7 for glossary/dictionary integration
- Extend intent_catalog.py with more intents if needed for hybrid routing

</code_context>

<deferred>
## Deferred Ideas

- Langfuse observability integration
- RBAC with JWT auth (separate todo)
- Angular widget embedding (separate todo)
- Scheduled backups
- Face detection grouping
- Cloud sync
- LLM-based metric detection (stub in Phase 7, deferred further)

</deferred>

---

*Phase: 08-context-aware-hybrid*
*Context gathered: 2026-04-07 via PRD Express Path*