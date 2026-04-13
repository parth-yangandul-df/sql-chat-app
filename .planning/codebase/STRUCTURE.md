# Codebase Structure

**Analysis Date:** 2026-04-07

## Directory Layout

```
querywise/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/      # FastAPI route handlers
│   │   │   └── schemas/         # Pydantic models
│   │   ├── connectors/          # Database connector plugins
│   │   ├── core/                # Exceptions, logging, security
│   │   ├── db/
│   │   │   ├── models/          # SQLAlchemy ORM models
│   │   │   └── session.py       # Async engine + session factory
│   │   ├── llm/
│   │   │   ├── agents/          # LLM agents (composer, validator, interpreter)
│   │   │   ├── providers/       # LLM provider implementations
│   │   │   ├── prompts/         # Prompt templates
│   │   │   ├── graph/           # LangGraph stateful graph
│   │   │   └── router.py        # Model routing
│   │   ├── semantic/            # Context building (schema, glossary, knowledge)
│   │   ├── services/            # Business logic
│   │   ├── utils/               # Utilities (SQL sanitizer)
│   │   ├── config.py            # Settings
│   │   └── main.py              # FastAPI app factory
│   └── scripts/                 # Backend scripts
├── frontend/                    # Mantine UI (port 5173)
│   └── src/
│       ├── api/                 # API client functions
│       ├── components/          # React components
│       ├── hooks/               # Custom React hooks
│       ├── pages/               # Page components
│       ├── types/               # TypeScript types
│       └── utils/               # Utilities
├── chatbot-frontend/            # React + Tailwind + shadcn/ui (port 5174)
│   └── src/
│       ├── api/
│       ├── components/
│       ├── hooks/
│       ├── pages/
│       └── types/
└── .planning/codebase/          # Architecture documentation
```

## Directory Purposes

**Backend Core Directories:**

`backend/app/api/v1/endpoints/`:
- Purpose: FastAPI route handlers (one file per resource)
- Contains: `query.py`, `connections.py`, `schemas.py`, `glossary.py`, `metrics.py`, `dictionary.py`, `knowledge.py`, `sample_queries.py`, `query_history.py`, `sessions.py`, `auth.py`, `health.py`

`backend/app/api/v1/schemas/`:
- Purpose: Pydantic request/response models
- Contains: `query.py`, `connection.py`, `schema.py`, `glossary.py`, `metric.py`, `dictionary.py`, `knowledge.py`, `session.py`

`backend/app/connectors/`:
- Purpose: Database connector plugin system
- Contains: `base_connector.py` (ABC), `connector_registry.py`, `postgresql/connector.py`, `sqlserver/connector.py`
- Key pattern: Register connectors via registry, get by connection_id

`backend/app/core/`:
- Purpose: Cross-cutting concerns
- Contains: `exceptions.py` (custom exceptions), `exception_handlers.py`, `logging_config.py`

`backend/app/db/models/`:
- Purpose: SQLAlchemy ORM models
- Contains: `user.py`, `connection.py`, `glossary.py`, `metric.py`, `dictionary.py`, `knowledge.py`, `sample_query.py`, `schema_cache.py`, `query_history.py`, `chat_session.py`

`backend/app/llm/agents/`:
- Purpose: LLM-driven tasks (SQL generation, validation, interpretation)
- Contains: `query_composer.py` (generates SQL), `sql_validator.py`, `result_interpreter.py`, `error_handler.py`

`backend/app/llm/providers/`:
- Purpose: LLM API implementations
- Contains: `anthropic_provider.py`, `openai_provider.py`, `ollama_provider.py`, `openrouter_provider.py`, `groq_provider.py`, `base_provider.py`, `provider_registry.py`

`backend/app/llm/graph/`:
- Purpose: LangGraph stateful pipeline
- Contains: `graph.py` (StateGraph assembly), `state.py` (GraphState TypedDict), `query_plan.py`, `intent_catalog.py`, `nodes/` (intent_classifier, filter_extractor, result_interpreter, etc.)

`backend/app/semantic/`:
- Purpose: Context building for LLM prompts
- Contains: `context_builder.py` (orchestrator), `schema_linker.py`, `glossary_resolver.py`, `prompt_assembler.py`, `relationship_inference.py`, `relevance_scorer.py`

`backend/app/services/`:
- Purpose: Business logic
- Contains: `query_service.py` (main pipeline), `connection_service.py`, `schema_service.py`, `embedding_service.py`, `knowledge_service.py`, `setup_service.py`, `embedding_progress.py`

**Frontend Directories:**

`frontend/src/api/`:
- Purpose: API client functions (React Query wrappers)
- Contains: `client.ts`, `queryApi.ts`, `connectionApi.ts`, `glossaryApi.ts`, `knowledgeApi.ts`, `embeddingApi.ts`

`frontend/src/components/`:
- Purpose: Reusable React components
- Contains: `layout/AppLayout.tsx`, `common/` (ProtectedRoute, CsvImportModal, TablePagination), etc.

`frontend/src/pages/`:
- Purpose: Page-level components
- Contains: `QueryPage.tsx`, `ConnectionsPage.tsx`, `GlossaryPage.tsx`, `MetricsPage.tsx`, `DictionaryPage.tsx`, `KnowledgePage.tsx`, `HistoryPage.tsx`, `LoginPage.tsx`

`frontend/src/hooks/`:
- Purpose: Custom React hooks
- Contains: `useConnections.ts`, `useEmbeddingStatus.ts`, `usePagination.ts`

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app factory, lifespan management
- `frontend/src/main.tsx`: React app bootstrap (Mantine + React Query + Router)
- `chatbot-frontend/src/main.tsx`: Chatbot React app bootstrap

**Configuration:**
- `backend/app/config.py`: Settings class (Pydantic BaseSettings)
- `.env`: Environment variables (NOT committed)

**Core Logic:**
- `backend/app/services/query_service.py`: Main NL→SQL pipeline
- `backend/app/llm/graph/graph.py`: LangGraph StateGraph assembly
- `backend/app/semantic/context_builder.py`: Hybrid context building

**Testing:**
- `backend/tests/`: pytest test files

## Naming Conventions

**Files:**
- Python: `snake_case.py` (e.g., `query_service.py`, `schema_linker.py`)
- TypeScript: `camelCase.ts` (e.g., `queryApi.ts`, `useConnections.ts`)
- Components: `PascalCase.tsx` (e.g., `QueryPage.tsx`, `AppLayout.tsx`)

**Directories:**
- Python: `snake_case/` (e.g., `llm/agents/`, `api/v1/endpoints/`)
- TypeScript: `kebab-case/` or `camelCase/` (e.g., `api/`, `components/ui/`)

**Functions/Methods:**
- Python: `snake_case` (e.g., `execute_nl_query`, `build_context`)
- TypeScript: `camelCase` (e.g., `executeQuery`, `useConnections`)

**Classes:**
- PascalCase (e.g., `DatabaseConnection`, `QueryComposerAgent`, `BaseConnector`)

**Types/Interfaces (TypeScript):**
- PascalCase (e.g., `QueryRequest`, `ConnectionResponse`)

## Where to Add New Code

**New API Endpoint:**
- Handler: `backend/app/api/v1/endpoints/{resource}.py`
- Schema: `backend/app/api/v1/schemas/{resource}.py`
- Router: Add to `backend/app/api/v1/router.py`

**New LLM Provider:**
- Implementation: `backend/app/llm/providers/{provider}_provider.py`
- Registry: Add to `backend/app/llm/provider_registry.py`

**New Database Connector:**
- Implementation: `backend/app/connectors/{db_type}/connector.py`
- Registry: Add to `backend/app/connectors/connector_registry.py`

**New Service:**
- Location: `backend/app/services/{service_name}.py`
- Import and use in endpoints or other services

**New LangGraph Node:**
- Location: `backend/app/llm/graph/nodes/{node_name}.py`
- Register in `backend/app/llm/graph/graph.py`

**New Frontend Page:**
- Component: `frontend/src/pages/{PageName}.tsx`
- Route: Add to `frontend/src/App.tsx`
- API: Add client in `frontend/src/api/{feature}Api.ts`

**New Frontend Component:**
- UI components: `frontend/src/components/ui/`
- Layout: `frontend/src/components/layout/`
- Common: `frontend/src/components/common/`

## Special Directories

`backend/app/db/models/`:
- Purpose: SQLAlchemy ORM model definitions
- Generated: No (manually written)
- Committed: Yes

`backend/app/llm/graph/nodes/`:
- Purpose: LangGraph node implementations
- Generated: No
- Committed: Yes

`frontend/src/types/`:
- Purpose: TypeScript type definitions matching backend schemas
- Generated: No (manually written to match API)
- Committed: Yes

`.planning/codebase/`:
- Purpose: Architecture and structure documentation
- Generated: No (this file)
- Committed: Yes (for GSD planning)

---

*Structure analysis: 2026-04-07*
