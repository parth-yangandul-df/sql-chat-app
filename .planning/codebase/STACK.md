# Technology Stack

**Analysis Date:** 2026-04-07

## Languages

**Primary:**
- Python 3.11+ - Backend API, LLM integrations, database operations
- TypeScript - Frontend (both frontend and chatbot-frontend)

**Secondary:**
- JavaScript - Minimal (TypeScript dominant)

## Runtime

**Environment:**
- Python: 3.11+ via uvicorn ASGI server
- Node.js: 19+ via Vite for frontend bundling

**Package Manager:**
- Python: pip via pyproject.toml (PEP 517)
- Node.js: npm via package.json

**Lockfiles:**
- Python: Not present (uses pip directly)
- Node.js: `package-lock.json` in frontend and chatbot-frontend

## Frameworks

**Core (Backend):**
- FastAPI 0.115+ - Web framework with Pydantic validation
- SQLAlchemy 2.0+ (async) - ORM with asyncpg driver
- pgvector 0.3+ - Vector embeddings for semantic search
- Alembic - Database migrations
- LangGraph 0.2+ - LLM agent orchestration (optional, via `[llm]` extra)

**Core (Frontend):**
- React 19 - UI framework (both frontend and chatbot-frontend)
- Vite 7/8 - Build tool and dev server

**Frontend UI Libraries:**
- Mantine UI 8.3+ - Primary frontend (port 5173)
- Tailwind CSS 3.4+ - Chatbot frontend (port 5174)
- shadcn/ui (Radix primitives) - Chatbot UI components

**Frontend State/Data:**
- React Query (TanStack) 5.90+ - Server state management
- React Router 7 - Navigation

**Testing:**
- pytest 8.0+ - Backend test runner
- pytest-asyncio 0.24+ - Async test support
- ESLint + TypeScript ESLint - Frontend linting

**Code Quality:**
- Ruff 0.8+ - Python linting and formatting
- mypy 1.13+ - Python type checking

## Key Dependencies

**Critical:**
- asyncpg 0.30+ - Async PostgreSQL driver
- pydantic 2.0+ - Data validation
- pydantic-settings 2.0+ - Environment configuration
- httpx 0.27+ - Async HTTP client (LLM calls, URL fetching)
- cryptography 43.0+ - Connection string encryption
- loguru 0.7+ - Structured logging

**LLM (optional via `[llm]` extra):**
- anthropic 0.40+ - Claude API client
- openai 1.50+ - OpenAI API client
- langgraph 0.2+ - Agent state management

**Database Connectors (optional via `[sqlserver]` extra):**
- aioodbc 0.5+ - Async ODBC driver for SQL Server

**Authentication:**
- PyJWT 2.8+ - JWT token handling
- passlib[bcrypt] 1.7+ - Password hashing

## Configuration

**Environment:**
- `.env` file at project root (backend reads from workspace root)
- Configuration class: `backend/app/config.py` with `Settings(BaseSettings)`
- Loads from `.env` files via `pydantic-settings`

**Build:**
- Backend: `pyproject.toml` (Ruff, pytest config)
- Frontend: `vite.config.ts`, `tsconfig.json`
- Chatbot-frontend: `vite.config.ts`, `tsconfig.json`

## Platform Requirements

**Development:**
- Docker + Docker Compose for full stack
- PostgreSQL 16 with pgvector extension
- Node.js 19+
- Python 3.11+

**Production:**
- FastAPI ASGI server (uvicorn)
- PostgreSQL 16 with pgvector
- LLM provider API keys (Anthropic, OpenAI, Ollama, OpenRouter, or Groq)

---

*Stack analysis: 2026-04-07*