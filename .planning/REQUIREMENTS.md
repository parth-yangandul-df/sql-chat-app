# QueryWise Requirements

## OBS-01: Langfuse Setup and Configuration
- Install Langfuse Python SDK
- Initialize client with environment variables (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
- Centralized configuration management

## OBS-02: LLM Observability
- Wrap all LLM calls with Langfuse tracing
- Capture token usage (prompt, completion, total)
- Capture latency, model name, input/output
- Create reusable LLM wrapper function/module

## OBS-03: End-to-End Request Tracing
- Create root trace for every user query
- Attach user_id, query text, timestamp
- Maintain trace context throughout request pipeline

## OBS-04: Pipeline-Level Spans
- Instrument four key pipeline steps:
  1. Intent detection
  2. LLM query generation
  3. Stored procedure execution
  4. Response formatting
- Measure latency for each span
- Capture inputs/outputs where applicable
- Capture errors if they occur

## OBS-05: Business Metadata Enrichment
- Attach business metadata to each trace:
  - intent
  - stored_procedure_name
  - tables_used (if available)
  - success/failure status
  - error message (if any)
- Ensure metadata is queryable in Langfuse UI

## OBS-06: Cost Tracking
- Implement automatic cost tracking where available
- Manual cost calculation based on model pricing
- Attach cost to trace metadata

## OBS-07: FastAPI Middleware
- Implement middleware for non-LLM observability
- Capture endpoint, HTTP method, latency, status code
- Ensure no interference with Langfuse tracing

## OBS-08: Optional Metrics Persistence
- Create LLM_Metrics table in SQL Server
- Insert record after each completed request
- Include: UserId, Query, Token counts, Latency, Model, Cost, Intent, StoredProcedure, Status, Timestamp

## OBS-09: Code Structure Requirements
- Organize as observability/ and services/ directories
- No duplication of tracing logic
- Reusable utilities
- Clean separation of concerns

## OBS-10: Error Handling
- Capture all exceptions in Langfuse traces
- Mark trace status as "failure"
- Include error message in metadata