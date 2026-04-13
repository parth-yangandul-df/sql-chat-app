# External Integrations

**Analysis Date:** 2026-04-07

## APIs & External Services

**LLM Providers:**
- Anthropic - Primary provider, Claude models for SQL generation
  - SDK: `anthropic` Python package
  - Auth: `ANTHROPIC_API_KEY` env var
- OpenAI - Alternative LLM provider
  - SDK: `openai` Python package
  - Auth: `OPENAI_API_KEY` env var
- Ollama - Local LLM (self-hosted)
  - Implementation: Direct HTTP via httpx to Ollama REST API
  - Auth: `OLLAMA_API_KEY` (optional for cloud Ollama)
  - Endpoint: `OLLAMA_BASE_URL` (default: http://localhost:11434)
- OpenRouter - Unified API for multiple providers
  - Auth: `OPENROUTER_API_KEY` env var
- Groq - Fast inference provider
  - Auth: `GROQ_API_KEY` env var

**Embedding Providers:**
- OpenAI `text-embedding-3-small` - Default embedding model
- Ollama `nomic-embed-text` - Local embeddings (768 dimensions)
- Configurable via `EMBEDDING_PROVIDER` and `EMBEDDING_DIMENSION`

## Data Storage

**App Metadata Database:**
- PostgreSQL 16 with pgvector extension
- Connection: `DATABASE_URL` env var
- Client: SQLAlchemy async with asyncpg driver
- Purpose: Stores metadata, glossary, metrics, knowledge documents, user data

**Target Database Connectors:**
- PostgreSQL - Direct connection via asyncpg (built-in)
- SQL Server - ODBC connection via aioodbc (optional, lazy-loaded)
- Connection strings encrypted with Fernet (`ENCRYPTION_KEY`)

**File Storage:**
- Local filesystem only - No cloud storage integration

**Caching:**
- None - In-memory only

## Authentication & Identity

**Auth Provider:**
- Custom JWT-based authentication
- Implementation: PyJWT with bcrypt password hashing
- Token: `jwt_secret`, `jwt_algorithm` (HS256), `jwt_expiry_seconds`
- Routes: `/api/v1/auth/*` endpoints

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service

**Logs:**
- Approach: loguru (structured logging to stdout + optional file rotation)
- Config: `LOG_LEVEL`, `LOG_FILE_ENABLED`, `LOG_ROTATION`, `LOG_RETENTION`

## CI/CD & Deployment

**Hosting:**
- Docker Compose for local development
- Compatible with any container hosting (Render, Fly.io, etc.)

**CI Pipeline:**
- None detected - No GitHub Actions or similar

## Environment Configuration

**Required env vars:**
- `DATABASE_URL` - App metadata PostgreSQL connection
- `JWT_SECRET` - Secret for JWT token signing
- `ENCRYPTION_KEY` - Fernet key for connection string encryption
- `ANTHROPIC_API_KEY` - Required for Anthropic LLM
- `OPENAI_API_KEY` - Required for OpenAI LLM/embeddings
- `DEFAULT_LLM_PROVIDER` - Which LLM to use (anthropic, openai, ollama, openrouter, groq)
- `DEFAULT_LLM_MODEL` - Default model name

**Optional env vars:**
- `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `OLLAMA_API_KEY`
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL`
- `EMBEDDING_PROVIDER`, `EMBEDDING_DIMENSION`
- `CORS_ORIGINS`

**Secrets location:**
- `.env` file at project root
- Loaded by `pydantic-settings` in `backend/app/config.py`

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected

---

*Integration audit: 2026-04-07*