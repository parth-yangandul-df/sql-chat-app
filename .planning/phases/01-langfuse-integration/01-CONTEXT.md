# Phase 1: Langfuse Integration - Context

**Gathered:** 2025-03-25
**Status:** Ready for planning
**Source:** Technical requirements document

<domain>
## Phase Boundary

Integrate **Langfuse-based observability** into an existing FastAPI backend that uses LLMs to process user queries and execute database operations via stored procedures.

The goal is to implement **end-to-end tracing, token tracking, cost monitoring, and pipeline observability** without modifying business logic or introducing direct SQL queries.

</domain>

<decisions>
## Implementation Decisions

### Architecture
- Use Langfuse Python SDK for observability
- Environment variables for configuration (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
- Centralized configuration in config/langfuse.py
- Organize code as observability/ directory with clean separation of concerns

### LLM Observability
- Wrap all LLM calls using Langfuse tracing
- Capture: token usage, latency, model name, input/output
- Create reusable LLM wrapper function/module
- Use Langfuse decorators or explicit tracing

### Request Tracing 
- Create root trace for every user query
- Attach: user_id, query text, timestamp
- Pipeline spans: intent_detection, llm_query_generation, stored_procedure_execution, response_formatting

### Business Metadata
- Attach: intent, stored_procedure_name, tables_used, success/failure status, error message
- Ensure metadata is queryable in Langfuse UI

### Infrastructure
- Implement FastAPI middleware for non-LLM observability
- Automatic or manual cost tracking based on model pricing
- Optional LLM_Metrics table in SQL Server for persistence

### Error Handling
- Capture all exceptions in Langfuse traces
- Mark trace status as "failure" 
- Include error message in metadata

### Claude's Discretion
- Specific implementation details for span creation and tracing
- Cost calculation methodology
- Metrics persistence approach
- Testing strategy for observability

</decisions>

<specifics>
## Specific Ideas

### Code Structure 
```
observability/
  langfuse_client.py
  tracing.py
services/
  llm_service.py (wrapped with observability)
middleware/
  logging_middleware.py
```

### Pipeline Spans
1. intent_detection - measure and capture inputs/outputs
2. llm_query_generation - latency and token tracking
3. stored_procedure_execution - performance monitoring
4. response_formatting - final processing metrics

### Constraints
- DO NOT modify business logic
- DO NOT introduce direct SQL queries (must use stored procedures only)
- Keep implementation lightweight and modular
- Avoid tight coupling with Langfuse (allow future replacement)

</specifics>

<deferred>
## Deferred Ideas

None — requirements cover the complete phase scope for Langfuse integration

</deferred>

---

*Phase: 01-langfuse-integration*
*Context gathered: 2025-03-25 via technical requirements*