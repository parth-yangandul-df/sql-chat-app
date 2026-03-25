# QueryWise Roadmap

## Phase 1: Foundation
**Status:** Complete
- Basic FastAPI setup with SQLAlchemy
- LLM providers (Anthropic, Openai, Ollama)
- Semantic layer foundation
- Connection management system

## Phase 2: Langfuse Integration (Current)
**Status:** In Progress
**Goal:** Implement end-to-end observability with Langfuse
**Requirements:** [OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, OBS-06, OBS-07, OBS-08, OBS-09, OBS-10]
**Plans:** 5 plans

### Overview
Integrate Langfuse-based observability into the existing FastAPI backend for comprehensive tracing, token tracking, cost monitoring, and pipeline observability.

### Deliverables
- Langfuse client configuration
- LLM call wrapping and tracing
- End-to-end request tracing
- Pipeline-level spans (intent detection, query generation, stored procedure execution, response formatting)
- Business metadata enrichment
- Cost tracking implementation
- FastAPI middleware for non-LLM observability
- Optional SQL Server metrics persistence
- Comprehensive error handling in traces
- Clean, modular code structure

### Plans
- [ ] 01-langfuse-integration-01-PLAN.md — Foundation setup with Langfuse SDK and client configuration
- [ ] 01-langfuse-integration-02-PLAN.md — Tracing utilities and decorators
- [ ] 01-langfuse-integration-03-PLAN.md — LLM provider observability integration
- [ ] 01-langfuse-integration-04-PLAN.md — End-to-end request tracing and pipeline spans
- [ ] 01-langfuse-integration-05-PLAN.md — FastAPI middleware and metrics persistence

## Phase 3: Production Readiness
**Status:** Planned
- Performance optimizations
- Additional database connectors (BigQuery, Databricks)
- Advanced semantic features

## Phase 4: Enterprise Features
**Status:** Future
- Multi-tenant support
- Advanced analytics
- Collaboration features