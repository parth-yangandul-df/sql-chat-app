# QueryWise Integrations

## LLM Providers

QueryWise supports multiple LLM providers via a pluggable architecture in `backend/app/llm/providers/`.

### Supported Providers

| Provider | Model Configuration | Embedding Support |
|----------|---------------------|-------------------|
| **Anthropic** | `DEFAULT_LLM_MODEL` (Claude) | Via OpenAI (fallback) |
| **OpenAI** | `DEFAULT_LLM_MODEL` (GPT-5.2) | Native |
| **Ollama** | `OLLAMA_MODEL` (llama3.1:8b) | Native (nomic-embed-text) |
| **OpenRouter** | Multiple models per role | Via OpenAI-compatible |
| **Groq** | `DEFAULT_LLM_MODEL` | Via OpenAI |

### Provider-Specific Configuration

**Anthropic**
- `ANTHROPIC_API_KEY` — Required
- Embeddings fall back to OpenAI

**OpenAI**
- `OPENAI_API_KEY` — Required
- `EMBEDDING_MODEL` — text-embedding-3-small

**Ollama**
- `OLLAMA_BASE_URL` — http://host.docker.internal:11434 (macOS native) or http://ollama:11434 (Docker)
- `OLLAMA_MODEL` — llama3.1:8b
- `OLLAMA_EMBEDDING_MODEL` — nomic-embed-text
- Supports cloud Ollama with `OLLAMA_LLM_BASE_URL` and `OLLAMA_API_KEY`

**OpenRouter**
- `OPENROUTER_API_KEY` — Required
- Multi-model routing:
  - `OPENROUTER_MODEL` — Composer (SQL generation)
  - `RESOLVER_MODEL` — Resolver (intent classification)
  - `INTERPRETER_MODEL` — Interpreter (result summaries)
- Embeddings via `EMBEDDING_PROVIDER=openrouter`

**Groq**
- `GROQ_API_KEY` — Required
- Optional: `USE_GROQ_EXTRACTOR=true` for unified intent + filter extraction

### Embedding Configuration

- `EMBEDDING_DIMENSION` — 1536 (OpenAI/Anthropic/OpenRouter) or 768 (Ollama)
- `EMBEDDING_MODEL` — openai/text-embedding-3-small (default)
- `EMBEDDING_PROVIDER` — Override for embedding routing (e.g., openrouter)

## Database Connectors

Plugin system in `backend/app/connectors/` with connector registry.

### Built-in

| Connector | Driver | Features |
|-----------|--------|----------|
| **PostgreSQL** | asyncpg | Connection pooling, full async |
| **SQL Server** | aioodbc (lazy) | ODBC driver, optional dep |

### Connector Architecture

- `BaseConnector` ABC defines interface
- `connector_registry.py` manages plugin registration
- LRU cache with 50 max connectors
- Auto-cleanup of stale connections (1-hour default)

## API Integration Points

### Backend API
- FastAPI at `/api/v1/`
- Swagger docs at `/docs`
- Server-sent events for streaming responses
- JWT authentication support

### Frontend APIs
- **Mantine UI** (port 5173) — Full admin interface
- **Chatbot UI** (port 5174) — Conversational interface

### External Services
- **PostgreSQL** — Application metadata storage
- **LLM APIs** — Anthropic, OpenAI, OpenRouter, Groq, Ollama

## Feature Flags

| Flag | Default | Description |
|------|---------|-------------|
| `USE_GROQ_EXTRACTOR` | false | Groq unified intent + filter extractor |
| `USE_QUERY_PLAN_COMPILER` | false | QueryPlan compiler |
| `USE_HYBRID_MODE` | false | Context-aware query system |

## Environment Variables Summary

### Required for Production
- `DATABASE_URL`
- `ENCRYPTION_KEY`
- LLM provider API keys

### Optional
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRY_SECONDS` — Auth
- `CORS_ORIGINS` — Frontend access
- `DEFAULT_QUERY_TIMEOUT_SECONDS`, `MAX_RETRY_ATTEMPTS` — Query config
- `MAX_QUERIES_PER_MINUTE` — Rate limiting
- `MAX_CONTEXT_TABLES`, `MAX_SAMPLE_QUERIES` — Context limits