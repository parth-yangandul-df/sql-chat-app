# QueryWise Project State

**Current State:** Active development
**Last Updated:** 2025-03-25
**Phase Focus:** Langfuse Integration (Observability)

## Project Architecture

QueryWise is a text-to-SQL application with semantic metadata layer. Users ask natural language questions, LLM generates SQL using business context, executes against database, returns human-readable answers.

### Tech Stack
- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), asyncpg, pgvector
- **Frontend:** React 19, TypeScript, Vite, Mantine UI
- **Databases:** PostgreSQL with pgvector extension
- **LLM:** Provider-agnostic (Anthropic Claude, OpenAI, Ollama)

### Current Request Flow
User → FastAPI → Intent Detection → LLM → Stored Procedure → Response

## Decisions Made

### Architecture
- SQLAlchemy ORM with async patterns
- UUID primary keys, timestamps on all models
- Provider-agnostic LLM interface
- Context building with semantic search using pgvector

### Code Style
- Python: Ruff, 100 char line length
- TypeScript: ESLint, strict mode
- Async everywhere for DB operations and LLM calls

## Current Environment Variables
- DATABASE_URL, ENCRYPTION_KEY
- DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL
- EMBEDDING_MODEL, EMBEDDING_DIMENSION
- CORS_ORIGINS, AUTO_SETUP_SAMPLE_DB

## Known Constraints
- Must use stored procedures (no direct table access)
- FastAPI backend - cannot modify business logic
- Semantic layer: glossary, metrics, dictionary
- Async patterns throughout

## Pending Considerations

### Observability
- No current observability implementation
- Need LLM call tracking (tokens, costs, latency)
- Need end-to-end request tracing
- Store metrics in application database

### Integration Points
- FastAPI middleware for HTTP observability
- LLM service wrapping with tracing
- Semantic layer observability
- Error handling and tracing