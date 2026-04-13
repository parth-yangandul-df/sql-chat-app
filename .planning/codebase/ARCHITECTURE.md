# Architecture

**Analysis Date:** 2026-04-07

## Pattern Overview

**Overall:** Layered Architecture with Agentic LLM Pipeline

**Key Characteristics:**
- **Service-oriented layers**: Clear separation between API handlers, business logic services, and data access
- **Plugin-based connectors**: Database connectors follow a registry pattern (`BaseConnector` ABC)
- **Provider abstraction**: LLM providers implement a common interface (`BaseLLMProvider` ABC)
- **Stateful graph pipeline**: LangGraph orchestrates the NL→SQL pipeline with state management
- **Semantic context layer**: Hybrid context building combines embeddings, keywords, FK relationships, and domain-specific metadata

## Layers

**API Layer:**
- Purpose: Handle HTTP requests/responses, authentication, validation
- Location: `backend/app/api/v1/endpoints/`
- Contains: FastAPI route handlers for auth, queries, connections, schemas, glossary, metrics, dictionary, knowledge, sessions, history
- Depends on: Services layer
- Used by: Frontend clients (React apps)

**Service Layer:**
- Purpose: Business logic orchestration, transaction management
- Location: `backend/app/services/`
- Contains: `query_service.py` (main pipeline), `connection_service.py`, `schema_service.py`, `embedding_service.py`, `knowledge_service.py`, `setup_service.py`
- Depends on: LLM agents, semantic layer, connectors, db models
- Used by: API endpoints

**LLM Layer (Agents):**
- Purpose: SQL generation, validation, error handling, result interpretation
- Location: `backend/app/llm/agents/`
- Contains: `query_composer.py`, `sql_validator.py`, `result_interpreter.py`, `error_handler.py`
- Depends on: LLM providers
- Used by: Services layer, LangGraph nodes

**LLM Layer (Graph):**
- Purpose: Stateful orchestration of the query pipeline with intent classification, filtering, and fallback handling
- Location: `backend/app/llm/graph/`
- Contains: `graph.py` (StateGraph), `nodes/` (intent_classifier, filter_extractor, result_interpreter, history_writer, etc.), `state.py`, `query_plan.py`
- Depends on: LLM agents, semantic layer
- Used by: Query service

**LLM Providers:**
- Purpose: Abstract interface for LLM API calls (Anthropic, OpenAI, Ollama, OpenRouter, Groq)
- Location: `backend/app/llm/providers/`
- Contains: Provider implementations with `complete()`, `stream()`, `generate_embedding()` methods
- Depends on: External LLM APIs
- Used by: LLM agents, semantic layer (for embeddings)

**Semantic Layer:**
- Purpose: Build context for LLM prompts using hybrid retrieval (embeddings + keywords + relationships)
- Location: `backend/app/semantic/`
- Contains: `context_builder.py`, `schema_linker.py`, `glossary_resolver.py`, `prompt_assembler.py`, `relationship_inference.py`
- Depends on: DB models, embedding service
- Used by: LLM agents, LangGraph nodes

**Connector Layer:**
- Purpose: Execute SQL against target databases (PostgreSQL, SQL Server)
- Location: `backend/app/connectors/`
- Contains: `base_connector.py` (ABC), `postgresql/connector.py`, `sqlserver/connector.py`, `connector_registry.py`
- Depends on: Database drivers (asyncpg, aioodbc)
- Used by: Query service

**Database Layer:**
- Purpose: ORM models, session management, schema caching
- Location: `backend/app/db/`
- Contains: `session.py` (async engine), `models/` (user, connection, glossary, metric, dictionary, knowledge, sample_query, schema_cache, query_history, chat_session)
- Depends on: SQLAlchemy, asyncpg
- Used by: All layers needing data access

**Core Layer:**
- Purpose: Cross-cutting concerns (exceptions, logging, security)
- Location: `backend/app/core/`
- Contains: `exceptions.py`, `exception_handlers.py`, `logging_config.py`
- Used by: All layers

## Data Flow

**Query Pipeline (NL → SQL → Results):**

1. **Request In**: Frontend sends natural language question via `POST /api/v1/query`
2. **API Handler**: `query.py` endpoint validates request, extracts connection_id, session_id
3. **Service Entry**: `execute_nl_query()` in `query_service.py` creates initial `GraphState`
4. **Graph Invocation**: Calls `get_compiled_graph().ainvoke(initial_state)`
5. **Intent Classification**: `classify_intent` node uses embeddings to classify query domain/intent
6. **Filter Extraction**: `extract_filters` node extracts date/value filters from question
7. **Query Plan Update**: `update_query_plan` node builds `QueryPlan` with base SQL
8. **Domain Tool / LLM Fallback**:
   - High confidence → `run_domain_tool` (execute generated SQL)
   - Low confidence → `llm_fallback` (use LLM to generate SQL directly)
9. **SQL Execution**: Connector executes against target database
10. **Result Interpretation**: `interpret_result` node uses LLM to summarize results
11. **History Writing**: `write_history` node persists execution to `query_history` table
12. **Response**: Returns {sql, results, summary, highlights, suggested_followups}

**Context Building Flow:**

1. Question embedded via `embedding_service.py`
2. `schema_linker.py` finds relevant tables (hybrid: embedding similarity + keyword + FK expansion)
3. `glossary_resolver.py` resolves business terms from glossary
4. `metrics_resolver.py` finds related metrics
5. `knowledge_resolver.py` retrieves relevant knowledge chunks
6. `sample_query_resolver.py` finds similar example queries
7. `relationship_inference.py` applies inferred relationship rules
8. `prompt_assembler.py` combines all into formatted prompt context

## Key Abstractions

**BaseConnector (ABC):**
- Purpose: Interface for database connectors enforcing read-only queries
- Examples: `backend/app/connectors/postgresql/connector.py`, `backend/app/connectors/sqlserver/connector.py`
- Pattern: Abstract Base Class with registry

**BaseLLMProvider (ABC):**
- Purpose: Interface for LLM providers
- Examples: `anthropic_provider.py`, `openai_provider.py`, `ollama_provider.py`, `openrouter_provider.py`, `groq_provider.py`
- Pattern: Abstract Base Class with provider registry

**GraphState:**
- Purpose: TypedDict state passed through LangGraph nodes
- Location: `backend/app/llm/graph/state.py`
- Fields: question, connection_id, domain, intent, confidence, sql, result, explanation, answer, highlights, etc.

**QueryPlan:**
- Purpose: Structured representation of query intent with filters
- Location: `backend/app/llm/graph/query_plan.py`
- Fields: base_intent_sql, filters, sort_column, sort_direction, limit

**LinkedTable:**
- Purpose: Table with relevance score and match reason
- Location: `backend/app/semantic/schema_linker.py`
- Fields: table, columns, score, match_reason

## Entry Points

**Backend Entry:**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app --reload` or Docker
- Responsibilities: FastAPI app creation, CORS setup, lifespan management (embedding dimension check, intent catalog pre-embed), router inclusion

**Query Endpoint:**
- Location: `backend/app/api/v1/endpoints/query.py`
- Triggers: `POST /api/v1/query/execute`
- Responsibilities: Request validation, dependency injection (db, current_user), calls `execute_nl_query()`

**Frontend Entry:**
- Location: `frontend/src/main.tsx`
- Triggers: `npm run dev` (Vite dev server)
- Responsibilities: React app mount, Mantine provider, React Query client, React Router setup

**Chatbot Frontend Entry:**
- Location: `chatbot-frontend/src/main.tsx`
- Triggers: `npm run dev` (port 5174)
- Responsibilities: React app mount, Tailwind, shadcn/ui setup

## Error Handling

**Strategy:** Centralized exception handlers with typed error responses

**Patterns:**
- Custom exceptions in `core/exceptions.py` (AppError, SQLSafetyError, etc.)
- Exception handlers registered in `core/exception_handlers.py`
- Errors propagated through GraphState (`error` field)
- Graceful degradation: embedding failures fall back to keyword-only context

## Cross-Cutting Concerns

**Logging:** Loguru with centralized configuration in `core/logging_config.py`
- Configured in app lifespan, supports file rotation, structured logging

**Validation:** Pydantic models in `api/v1/schemas/` for request/response validation

**Authentication:** JWT-based in `api/v1/endpoints/auth.py`
- Token validation via `api/deps.py` dependency
- Role-based access control (RBAC) threaded through GraphState

**Encryption:** Fernet encryption for stored connection strings (`encryption_key` config)

---

*Architecture analysis: 2026-04-07*
