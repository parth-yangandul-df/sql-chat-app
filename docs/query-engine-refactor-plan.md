# QueryWise Query Engine Refactor Plan

## Status

- Branch: `query-architecture-refactor`
- Document type: architecture and execution plan
- Audience: engineers, agents, reviewers, maintainers
- Scope: backend query architecture, conversation state management, safety, latency, scaling, and reliability

---

## 1. Purpose

This document defines the final target architecture and the full implementation plan for refactoring QueryWise's backend query engine.

It is intentionally agent-agnostic. Any engineer or coding agent should be able to read this document and:

1. understand the current problems,
2. understand the target architecture,
3. understand the file-level refactor plan,
4. execute the implementation in phases,
5. verify correctness and completeness.

This plan replaces the current patch-driven evolution of the query system with one coherent architecture.

---

## 2. Problem Statement

QueryWise currently combines multiple query-routing and query-generation approaches:

- predefined SQL in domain agents,
- rule-based routing,
- regex and keyword heuristics,
- embedding-assisted retrieval,
- Groq-based structured extraction,
- dynamic text-to-SQL fallback,
- partial multi-turn chat context via ad hoc turn context.

Each individual approach worked in constrained demos, but the system has become brittle in real-world usage because the approaches were layered on top of each other rather than unified under one architecture.

### 2.1 Core product goals

The product must support both:

1. **trusted predefined query capabilities** for common business questions, and
2. **dynamic query generation** for novel or unsupported questions.

It must also behave like a **context-aware chatbot**, not just a one-shot text-to-SQL API.

### 2.2 Current system problems

#### Problem A: predefined queries are not modeled as capabilities

Predefined SQL currently behaves like a brittle FAQ shortcut layer rather than a formal business query capability catalog.

Effects:

- hard to know when a question should use trusted SQL,
- hard to know which filters a predefined query supports,
- hard to support follow-up refinements consistently,
- logic spread across many files and styles.

#### Problem B: dynamic SQL generation is too involved in normal traffic

The system currently risks sending too many requests into LLM-driven SQL generation or LLM-heavy routing behavior.

Effects:

- higher cost,
- higher latency,
- more failure modes,
- less deterministic behavior,
- lower confidence in common business flows.

#### Problem C: multiple routing systems compete

Routing logic currently exists across:

- Groq extractor behavior,
- graph branch logic,
- domain agents,
- SQL compiler,
- fallback logic,
- turn-context heuristics.

Effects:

- inconsistent decision-making,
- duplicated logic,
- hard debugging,
- architecture drift.

#### Problem D: multi-turn chat state is not a real state system

Current follow-up support relies on short conversation history plus `last_turn_context` and previous SQL hints.

Effects:

- topic switching can be unreliable,
- follow-up refinement behavior is inconsistent,
- state is not durable enough,
- behavior may differ across restarts or instances,
- raw SQL leaks into chat memory concerns.

#### Problem E: safety and RBAC are inconsistent across paths

The predefined SQL path and the generated SQL path do not share one consistent execution guardrail layer.

Effects:

- RBAC can depend too much on prompt instructions in fallback logic,
- safety and validation are not uniformly enforced,
- auditing is fragmented.

#### Problem F: latency path is not optimized

Common, high-volume business questions should take a short, deterministic path. Instead, the architecture encourages heavy reasoning or semantic context assembly too early.

Effects:

- unnecessary LLM work,
- slower responses for common asks,
- worse p95 latency,
- more infrastructure cost.

#### Problem G: current system is difficult to scale and maintain

Effects:

- logic tightly coupled to in-process orchestration,
- background tasks are not durable enough,
- difficult to reason about behavior during migration,
- high maintenance burden for every new fix.

---

## 3. Design Goals

The refactor must satisfy all of the following:

### Functional goals

1. Prefer trusted predefined query capabilities for common business questions.
2. Use dynamic SQL generation only when predefined capabilities cannot satisfy the request.
3. Support context-aware multi-turn conversation with persistent state.
4. Support refinement, topic switching, clarification, and result-aware follow-up.

### Non-functional goals

1. Lower latency for common questions.
2. Lower LLM usage and cost.
3. Higher determinism and reliability.
4. Clear safety model with deterministic RBAC.
5. Horizontally scalable API layer.
6. Stateless application processes with persistent backing services.
7. Clear observability for routing, generation, latency, and failures.

### Engineering goals

1. One canonical request pipeline.
2. One canonical `QueryPlan` contract.
3. One canonical conversation state model.
4. Minimal architecture duplication.
5. Agent-agnostic execution plan.

---

## 4. Final Architecture

The final architecture is:

**Conversation-first, plan-first, catalog-preferred, generation-fallback, state-persistent**

### 4.1 Single pipeline

Every user query follows the same pipeline:

1. `Conversation Resolver`
2. `Query Planner`
3. `Capability Matcher`
4. `Strategy Selector`
5. `Executor`
6. `Result Narrator`
7. `State Store`

This is the only query pipeline. There should not be parallel "old path vs new path" systems in the final architecture.

### 4.2 High-level behavior

1. User sends a message.
2. System resolves conversational context against persistent thread state.
3. System creates a structured `QueryPlan`.
4. System checks whether a trusted capability fully satisfies the plan.
5. If yes, system executes trusted template SQL.
6. If not, system performs controlled generation fallback.
7. System validates, scopes, executes, summarizes, and updates thread state.

---

## 5. Architecture Components

### 5.1 Conversation Resolver

#### Responsibility

Convert a raw user message plus thread state into a resolved conversational request context.

#### Inputs

- user message,
- conversation state,
- optional last result metadata,
- user identity and access scope.

#### Outputs

- follow-up classification:
  - `refine`,
  - `clarify`,
  - `new_topic`,
- resolved references,
- active plan adjustment guidance.

#### Rules

- Use structured state, not raw prior SQL, as primary conversation memory.
- Resolve pronouns and entity references.
- Detect topic switches deterministically.
- Preserve active filter state when user is refining.

### 5.2 Query Planner

#### Responsibility

Produce a canonical structured `QueryPlan`.

#### Important rule

The planner must output a structured plan, not SQL.

#### Outputs

- domain,
- intent candidate,
- task type,
- filters,
- metrics,
- grouping,
- sort,
- limit,
- ambiguity flags,
- novelty flags,
- confidence,
- clarification need.

### 5.3 Capability Catalog

#### Responsibility

Represent trusted predefined business query capabilities in a structured, declarative way.

Each catalog entry defines:

- intent id,
- domain,
- business meaning,
- SQL template,
- supported filters,
- supported grouping and metrics,
- unsupported operations,
- follow-up behavior,
- result shape,
- parameter binding rules.

This replaces the current brittle model where predefined SQL is spread across domain agent implementations and compiler branches.

### 5.4 Capability Matcher

#### Responsibility

Compare a `QueryPlan` against the capability catalog and determine whether the plan can be satisfied by trusted SQL.

#### Output categories

- `full_match`,
- `partial_match`,
- `no_match`.

### 5.5 Strategy Selector

#### Responsibility

Choose exactly one execution strategy:

- `template`,
- `clarify`,
- `generate`,
- `reject`.

#### Deterministic decision order

1. reject if out of scope,
2. clarify if ambiguous,
3. template if fully covered by catalog,
4. generate otherwise.

### 5.6 Template Executor

#### Responsibility

Execute trusted predefined query capabilities.

#### Properties

- deterministic,
- fast,
- parameterized,
- scope-aware,
- lower-latency path,
- lower-cost path.

### 5.7 Generation Executor

#### Responsibility

Handle only those requests that cannot be satisfied by the capability catalog.

#### Properties

- fallback path only,
- uses semantic retrieval,
- may use LLM to produce structured query spec and/or SQL,
- always passes through centralized guardrail layer.

### 5.8 Execution Guard

#### Responsibility

Centralize:

- RBAC,
- row limits,
- timeout,
- read-only enforcement,
- SQL validation,
- audit metadata.

This must be shared by both template and generation paths.

### 5.9 Result Narrator

#### Responsibility

Convert execution results into:

- user summary,
- follow-up suggestions,
- structured result metadata for future turns.

### 5.10 Persistent State Store

#### Responsibility

Persist conversation state across requests, restarts, and horizontal scaling.

#### Required properties

- durable,
- user-scoped,
- session-scoped,
- multi-instance safe,
- restart-safe.

Use LangGraph with a persistent checkpointer / Postgres-backed state persistence approach.

### 5.11 LangGraph Role in Final Architecture

LangGraph is **not** being discarded entirely.

However, the current LangGraph graph shape is being retired because it is tightly coupled to the current brittle routing architecture.

#### LangGraph will be kept for these purposes only

- persistent chat state,
- clarification loops,
- thread checkpointing,
- explicit conversation workflow.

#### LangGraph will not be kept as the main place for business query architecture

The following responsibilities should move out of the current graph-node patch model and into regular query-engine services:

- predefined SQL capability dispatch,
- brittle query-routing hacks,
- direct domain SQL orchestration,
- fallback patch logic,
- ad hoc turn-context mutation,
- mixed routing and execution concerns in the same node graph.

#### Final split of responsibilities

**LangGraph owns:**

- thread lifecycle,
- persistent state,
- pause and resume behavior,
- clarification loops,
- conversation transitions,
- checkpointing and recovery.

**Query engine services own:**

- conversation resolution logic,
- structured planning,
- capability matching,
- strategy selection,
- template execution,
- generation fallback execution,
- execution guards,
- result narration.

This means the refactor retires **most current LangGraph nodes**, but keeps LangGraph as a thin, state-centric orchestration layer.

---

## 6. QueryPlan Contract

The final architecture depends on one canonical plan schema.

Suggested shape:

```json
{
  "domain": "resource",
  "intent": "resource_by_skill",
  "task_type": "lookup",
  "filters": [
    {"field": "skill", "op": "eq", "value": "Python"}
  ],
  "metrics": [],
  "group_by": [],
  "sort": [],
  "limit": 100,
  "needs_clarification": false,
  "ambiguity_reason": null,
  "novel_requirements": [],
  "confidence": 0.91
}
```

### Contract principles

1. no SQL in planner output,
2. no backend-specific execution details,
3. explicit ambiguity,
4. explicit novelty,
5. explicit execution preference signals,
6. explicit support for multi-turn refinement.

---

## 7. Conversation State Contract

The final chatbot behavior depends on one canonical conversation state schema.

Suggested fields:

- `thread_id`
- `user_id`
- `connection_id`
- `messages`
- `active_topic`
- `active_domain`
- `active_plan`
- `active_filters`
- `last_result_meta`
- `clarification_pending`
- `clarification_question`
- `execution_strategy`
- `confidence`
- `schema_version`

### State rules

1. Follow-up refinement mutates active plan.
2. Topic switch replaces active plan.
3. Clarification pauses execution until answered.
4. Raw SQL is not primary conversation memory.
5. Last result metadata is stored structurally for future reference.

---

## 8. Proposed Solution Summary

### 8.1 What changes

The backend will stop behaving like a set of layered experiments and instead behave like one query engine with:

- one planner,
- one matcher,
- one selector,
- one state model,
- one execution guard,
- two execution strategies under one interface.

### 8.2 How predefined SQL works after refactor

Predefined SQL becomes a **capability catalog**.

It is no longer:

- FAQ matching,
- ad hoc rule branching,
- intent-specific hand wiring spread across multiple execution paths.

It becomes:

- trusted business capability definitions,
- matched by structured plan fit,
- compiled and executed deterministically.

### 8.3 How generated SQL works after refactor

Generated SQL becomes a formal fallback strategy.

It is no longer:

- equal peer to every other path,
- implicitly invoked by many fragile branches.

It becomes:

- explicit fallback when catalog does not cover the plan,
- isolated behind one executor,
- guarded by shared validation and access rules.

---

## 9. File-Level Refactor Plan

### 9.1 Keep mostly as-is

These files remain useful with minor to moderate edits:

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/db/session.py`
- `backend/app/connectors/base_connector.py`
- `backend/app/connectors/connector_registry.py`
- `backend/app/connectors/postgresql/connector.py`
- `backend/app/connectors/sqlserver/connector.py`
- `backend/app/services/connection_service.py`
- `backend/app/services/schema_service.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/knowledge_service.py`
- `backend/app/semantic/schema_linker.py`
- `backend/app/semantic/glossary_resolver.py`
- `backend/app/llm/agents/query_composer.py`
- `backend/app/llm/agents/result_interpreter.py`

### 9.2 Rewrite heavily

These files remain but with major behavior changes:

- `backend/app/api/v1/endpoints/query.py`
- `backend/app/services/query_service.py`
- `backend/app/config.py`
- `backend/app/db/models/chat_session.py`
- `backend/app/db/models/query_history.py`
- `backend/app/api/v1/endpoints/sessions.py`
- `backend/app/semantic/context_builder.py`
- `backend/app/llm/agents/sql_validator.py`
- `backend/app/services/setup_service.py`

### 9.3 Replace with new modules

These current modules are functionally replaced by new architecture modules:

- `backend/app/llm/graph/graph.py`
- `backend/app/llm/graph/state.py`
- `backend/app/llm/graph/nodes/llm_groq_extractor.py`
- `backend/app/llm/graph/nodes/llm_fallback.py`
- `backend/app/llm/graph/nodes/plan_updater.py`
- `backend/app/llm/graph/domains/base_domain.py`
- `backend/app/llm/graph/domains/registry.py`
- large portions of `backend/app/llm/graph/nodes/sql_compiler.py`
- domain-specific agent SQL implementations as they are migrated into catalog capabilities

### 9.4 New modules to create

Create package:

- `backend/app/query_engine/`

Core files:

- `backend/app/query_engine/__init__.py`
- `backend/app/query_engine/types.py`
- `backend/app/query_engine/state.py`
- `backend/app/query_engine/service.py`
- `backend/app/query_engine/conversation_resolver.py`
- `backend/app/query_engine/planner.py`
- `backend/app/query_engine/matcher.py`
- `backend/app/query_engine/selector.py`
- `backend/app/query_engine/guards.py`
- `backend/app/query_engine/validator.py`
- `backend/app/query_engine/narrator.py`
- `backend/app/query_engine/metrics.py`
- `backend/app/query_engine/checkpointer.py`
- `backend/app/query_engine/reducers.py`
- `backend/app/query_engine/conversation_graph.py`

Catalog files:

- `backend/app/query_engine/catalog/models.py`
- `backend/app/query_engine/catalog/registry.py`
- `backend/app/query_engine/catalog/resource.py`
- `backend/app/query_engine/catalog/project.py`
- `backend/app/query_engine/catalog/client.py`
- `backend/app/query_engine/catalog/timesheet.py`
- `backend/app/query_engine/catalog/user_self.py`

Executor files:

- `backend/app/query_engine/executors/template_executor.py`
- `backend/app/query_engine/executors/generation_executor.py`

Retrieval files:

- `backend/app/query_engine/retrieval/lightweight.py`
- `backend/app/query_engine/retrieval/heavyweight.py`

---

## 10. Full Phased Implementation Plan

## Phase 1: Core Contracts

### Objective

Introduce the canonical internal language of the new query engine.

### Tasks

1. Create `query_engine` package.
2. Add `QueryPlan`, `PlanFilter`, `PlanDecision`, `ExecutionStrategy`, and `ConversationState` types.
3. Define response and state serialization contracts.
4. Add docstrings and examples for all contracts.

### Acceptance criteria

- core contracts compile,
- tests validate serialization and schema shape,
- no runtime behavior change yet.

---

## Phase 2: Query Engine Configuration Cleanup

### Objective

Replace scattered query architecture config with a cleaner final config model.

### Tasks

1. Refactor query-related settings in `config.py`.
2. Add startup validation for required query engine settings.
3. Mark legacy flags as temporary migration artifacts if still needed during transition, then remove before completion.

### Acceptance criteria

- app boots cleanly,
- config is explicit and environment-driven,
- final architecture does not depend on long-lived routing flags.

---

## Phase 3: Capability Catalog Extraction

### Objective

Move trusted predefined SQL into a formal capability catalog.

### Tasks

1. Extract current resource, project, client, timesheet, and user-self query templates.
2. Define structured capability metadata.
3. Implement catalog registry.
4. Add validation for capability completeness.

### Acceptance criteria

- all trusted production intents represented in catalog,
- capabilities declare supported filters and unsupported operations,
- no business-critical predefined SQL exists only inside old domain agent classes.

---

## Phase 4: Planner Implementation

### Objective

Convert top-level LLM reasoning into structured planning.

### Tasks

1. Implement planner service.
2. Refactor current Groq extractor logic into planner-only behavior.
3. Ensure planner outputs structured `QueryPlan`, not SQL.
4. Add planner test suite with representative common, ambiguous, unsupported, and follow-up queries.

### Acceptance criteria

- planner consistently produces structured plans,
- no planner branch executes SQL directly,
- ambiguity surfaced explicitly.

---

## Phase 5: Capability Matcher

### Objective

Make predefined SQL selection deterministic and explainable.

### Tasks

1. Implement capability match scoring.
2. Evaluate full vs partial vs no match.
3. Produce mismatch reasons.
4. Add unit tests for each supported intent family.

### Acceptance criteria

- common supported asks map to full catalog matches,
- unsupported asks do not get forced into bad templates,
- mismatch reasons available to selector.

---

## Phase 6: Strategy Selector

### Objective

Create one deterministic router for the final system.

### Tasks

1. Implement selector decision contract.
2. Route among `reject`, `clarify`, `template`, and `generate`.
3. Add metrics hooks for route counts and latency.

### Acceptance criteria

- one route decision per query,
- no duplicated routing logic outside selector,
- selector behavior testable without LLM.

---

## Phase 7: Template Executor

### Objective

Implement final trusted-query fast path.

### Tasks

1. Implement executor interface.
2. Add param binding helpers.
3. Inject deterministic RBAC scope.
4. Execute through existing connectors.
5. Return normalized execution result metadata.

### Acceptance criteria

- trusted catalog-matched queries execute without generation fallback,
- parameter binding is fully safe,
- latency measurably lower than generation path.

---

## Phase 8: Generation Executor

### Objective

Implement final controlled dynamic SQL fallback.

### Tasks

1. Isolate dynamic generation into dedicated executor.
2. Move heavy semantic context building into this path only.
3. Reuse retrieval, glossary, and schema-linking where useful.
4. Validate and scope generated SQL through shared execution guard.

### Acceptance criteria

- dynamic generation invoked only when selector chooses it,
- common catalog-supported traffic does not use this path,
- fallback remains functional for novel questions.

---

## Phase 9: Execution Guardrail Layer

### Objective

Unify safety, scope, and validation.

### Tasks

1. Build shared execution guard module.
2. Centralize timeout, row limit, read-only, and RBAC behavior.
3. Improve SQL validation structure.
4. Ensure both execution strategies pass through the same guard layer.

### Acceptance criteria

- both template and generation paths share one safety layer,
- prompt-only RBAC dependence removed,
- execution auditing standardized.

---

## Phase 10: Conversation State System

### Objective

Replace ad hoc turn context with durable structured thread state.

### Tasks

1. Implement persistent state schema.
2. Configure Postgres-backed thread persistence.
3. Add reducers for messages, active filters, and active plan.
4. Implement topic-switch and refinement behavior in conversation resolver.

### Acceptance criteria

- state survives restarts,
- follow-up questions mutate plan deterministically,
- topic switch resets plan cleanly,
- behavior consistent across instances.

---

## Phase 11: Session Ownership and Security Fix

### Objective

Fix session ownership and align chat sessions with persistent thread state.

### Tasks

1. Add `user_id` to chat session model.
2. Scope session endpoints by owner.
3. Scope thread state by session and user.
4. Add migration and tests for user isolation.

### Acceptance criteria

- no cross-user session leakage,
- session listing and history are user-scoped,
- thread identity is durable and safe.

---

## Phase 12: Query Service Rewrite

### Objective

Turn `query_service.py` into a clean orchestrator over the new engine.

### Tasks

1. Replace direct graph orchestration with query engine service orchestration.
2. Remove ad hoc route branching.
3. Remove topic-switch heuristics from service layer.
4. Normalize result assembly.

### Acceptance criteria

- `query_service.py` becomes significantly smaller,
- orchestration logic delegates to `query_engine`,
- endpoint behavior preserved or improved.

---

## Phase 13: API Layer Update

### Objective

Make API layer reflect final architecture cleanly.

### Tasks

1. Refactor query endpoint to use new service.
2. Add real stage streaming if retained.
3. Return metadata such as:
   - strategy used,
   - capability id,
   - clarification status,
   - thread state version if needed.

### Acceptance criteria

- query API thin and stable,
- stream endpoint no longer uses fake timer stages,
- response contract consistent with new engine.

---

## Phase 14: Retrieval Split

### Objective

Reduce latency by splitting lightweight and heavyweight retrieval work.

### Tasks

1. Move lightweight entity/value resolution into separate retrieval module.
2. Keep heavy schema/glossary/knowledge context assembly only for generation fallback.
3. Reuse retrieval modules from query engine service.

### Acceptance criteria

- template path does not pay heavy retrieval cost,
- generation path still has full semantic support,
- lower latency for common queries.

---

## Phase 15: Observability

### Objective

Make the new architecture measurable in production.

### Metrics to add

- planner latency,
- catalog match rate,
- template execution rate,
- generation execution rate,
- clarification rate,
- reject rate,
- execution success/failure by strategy,
- p50/p95 latency by strategy,
- token cost on generation path.

### Acceptance criteria

- all core stages observable,
- production behavior explainable,
- bottlenecks identifiable.

---

## Phase 16: Retirement of Legacy Architecture

### Objective

Delete obsolete logic after parity is reached.

### Tasks

1. Remove old graph routing stack.
2. Remove deprecated domain routing modules that are fully replaced.
3. Remove dead fallback and plan-updater branches.
4. Simplify imports and tests accordingly.

### Acceptance criteria

- no parallel architecture remains,
- no core behavior depends on legacy graph stack,
- codebase easier to navigate and maintain.

---

## 11. Data Migration Requirements

### Required migrations

1. Add `user_id` to `chat_sessions`.
2. Backfill or handle existing session ownership model safely.
3. Add any required persistent thread identifiers or state references.
4. Optionally evolve query history schema to capture:
   - plan data,
   - strategy used,
   - capability id,
   - clarification events.

### Migration safety requirements

- migrations must be reversible where feasible,
- no data loss for existing chat history,
- old sessions handled explicitly rather than silently orphaned.

---

## 12. Testing Plan

### Unit tests

Add tests for:

- `QueryPlan` schema,
- capability catalog validation,
- planner behavior,
- capability matching,
- selector routing,
- template execution,
- generation execution,
- conversation reducers,
- session ownership.

### Integration tests

Cover:

1. common FAQ-like query -> template path,
2. unsupported custom query -> generation path,
3. ambiguous query -> clarification path,
4. follow-up refinement,
5. topic switch,
6. user scope enforcement,
7. session ownership enforcement.

### Regression tests

Create corpus of representative business questions from real or synthetic traffic and verify:

- expected strategy selection,
- expected plan extraction,
- acceptable latency profile,
- acceptable final result correctness.

---

## 13. Rollout and Release Strategy

### Guiding principle

Although the final architecture should not permanently rely on parallel query-routing systems, implementation should still be phased to reduce delivery risk.

### Recommended rollout order

1. contracts,
2. catalog,
3. planner,
4. matcher,
5. selector,
6. template executor,
7. generation executor,
8. conversation state,
9. session ownership fix,
10. API and service rewrite,
11. observability,
12. legacy deletion.

### Release completion criteria

The refactor is complete when:

1. all traffic uses the new query engine pipeline,
2. predefined SQL is represented only as capability catalog definitions,
3. generated SQL is used only through generation executor,
4. conversation state is persistent and user-scoped,
5. legacy query graph stack is removed.

---

## 14. Risks and Mitigations

### Risk 1: catalog extraction incomplete

Mitigation:

- create capability validation tests,
- compare legacy trusted intents against new catalog inventory,
- migrate by domain in a disciplined sequence.

### Risk 2: planner quality not sufficient

Mitigation:

- planner produces structured outputs only,
- matcher and selector remain deterministic,
- use clarification path instead of unsafe guessing.

### Risk 3: session security bug persists during refactor

Mitigation:

- prioritize session ownership fix before final release,
- add authorization tests early.

### Risk 4: generation path still depends on prompt-only scope control

Mitigation:

- centralize RBAC in execution guard,
- inject deterministic scope filters outside prompts wherever possible.

### Risk 5: too much heavy retrieval on common path

Mitigation:

- split retrieval modules,
- reserve heavyweight context build for generation executor only.

### Risk 6: long-lived migration complexity

Mitigation:

- keep document authoritative,
- keep commit scope phased and traceable,
- remove legacy architecture once parity reached.

---

## 15. Success Criteria

### Product success

1. common business questions use trusted predefined capabilities reliably,
2. novel questions still work through generation fallback,
3. multi-turn refinement is materially more reliable,
4. topic switching is explicit and stable.

### Engineering success

1. one canonical query pipeline,
2. one canonical plan contract,
3. one canonical conversation state model,
4. much lower architecture duplication,
5. easier debugging and maintenance.

### Operational success

1. lower p95 latency for common asks,
2. lower LLM cost,
3. better route observability,
4. safer horizontal scaling story,
5. stronger RBAC consistency.

---

## 16. Recommended Immediate Next Actions

1. Approve this architecture as the final target.
2. Create `backend/app/query_engine/` package and core contracts.
3. Create the new thin LangGraph conversation workflow around persistent state, clarification, and checkpointing.
4. Extract current trusted query logic into capability catalog definitions.
5. Implement planner and matcher before touching endpoint behavior.
6. Prioritize session ownership and persistent conversation state as first-class work, not cleanup.

---

## 17. Appendix: Current Files Mapped to New Roles

### Current files that seed capability extraction

- `backend/app/llm/graph/domains/resource.py`
- `backend/app/llm/graph/nodes/sql_compiler.py`
- other domain agent modules under `backend/app/llm/graph/domains/`

### Current files that seed generation fallback extraction

- `backend/app/llm/graph/nodes/llm_fallback.py`
- `backend/app/semantic/context_builder.py`
- `backend/app/llm/agents/query_composer.py`

### Current files that require security-focused rewrite

- `backend/app/db/models/chat_session.py`
- `backend/app/api/v1/endpoints/sessions.py`
- `backend/app/services/query_service.py`

### Current files that remain infrastructural

- `backend/app/connectors/*`
- `backend/app/services/connection_service.py`
- `backend/app/services/schema_service.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/knowledge_service.py`

---

## 18. Final Statement

This refactor should be treated as an architectural replacement, not a set of local fixes.

The final system must behave as:

- a conversation-aware query engine,
- a planner-driven router,
- a capability-based trusted query system,
- a controlled generation fallback system,
- and a persistent stateful chatbot backend.

LangGraph remains part of that final system, but only as the orchestration layer for conversation state, clarification loops, thread checkpointing, and explicit workflow transitions.

That is the end state this document defines.
