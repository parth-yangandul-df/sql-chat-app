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

## LG-01: Feature Branch
- Create git branch `feature/langgraph-domain-tools` from dev

## LG-02: LangGraph Dependencies
- Add `langgraph>=0.2` and `langchain-core>=0.3` to pyproject.toml `llm` extras

## LG-03: GraphState
- Implement `GraphState` TypedDict in `graph/state.py`

## LG-04: Intent Catalog
- Implement `INTENT_CATALOG` with 24 intents (Resource×9, Client×5, Project×6, Timesheet×4) in `graph/intent_catalog.py`
- Each `IntentEntry` has optional `sql_fallback_template` and `fallback_intent` fields

## LG-05: Intent Classifier
- Implement `classify_intent` node with async embed + cosine similarity, confidence threshold from `TOOL_CONFIDENCE_THRESHOLD` env var (default 0.78)
- Log routing decision: INFO for domain_tool, WARNING for llm_fallback
- Graceful degradation: if embedding unavailable, route to llm_fallback (no crash)

## LG-06: Parameter Extractor
- Implement regex/keyword parameter extractor for skill, date range, resource name, client name

## LG-07: ResourceAgent
- Implement `ResourceAgent` with 9 SQL templates

## LG-08: ClientAgent
- Implement `ClientAgent` with 5 SQL templates

## LG-09: ProjectAgent
- Implement `ProjectAgent` with 6 SQL templates

## LG-10: TimesheetAgent
- Implement `TimesheetAgent` with 4 SQL templates

## LG-11: Result Interpreter Node
- Implement `interpret_result` node wrapping existing `ResultInterpreterAgent`

## LG-12: LLM Fallback Node
- Implement `llm_fallback` node reusing existing `QueryComposerAgent` + `SQLValidatorAgent` + `ErrorHandlerAgent`

## LG-13: History Writer Node
- Implement `write_history` node wrapping existing `QueryExecution` save

## LG-14: StateGraph Assembly
- Assemble `StateGraph` with updated topology including 0-row conditional edge after `run_domain_tool`
- 0 rows → try `fallback_intent` (1 hop max) → if still 0 rows → `llm_fallback`

## LG-15: Query Service Integration
- Replace `execute_nl_query` in `query_service.py` with LangGraph invocation on feature branch

## LG-16: Startup Catalog Embedding
- Pre-embed intent catalog at app startup in `main.py` lifespan, wrapped in try/except for graceful failure

## LG-17: SQL Server Params Bug Fix
- Fix `SQLServerConnector._run_query()` to pass params tuple to `cursor.execute(sql, params)`
- Update `execute_query()` signature: `params: tuple[Any, ...] | None = None`
- Update `base_connector.py` abstract method signature to match