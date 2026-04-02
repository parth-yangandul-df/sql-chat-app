---
phase: 01-langfuse-integration
plan: 04
type: execute
wave: 3
depends_on: ["01-langfuse-integration-01", "01-langfuse-integration-03"]
files_modified: ["backend/app/services/query_service.py", "backend/app/api/v1/endpoints/query.py"]
autonomous: true
requirements: ["OBS-03", "OBS-04", "OBS-05", "OBS-10"]
must_haves:
  truths:
    - "Every user query creates a root trace with user context"
    - "Pipeline spans exist for intent detection, query generation, stored procedure execution, and response formatting"
    - "Business metadata attached to traces (intent, stored_procedure_name, tables_used, status)"
    - "Errors properly captured in traces with failure status"
  artifacts:
    - path: "backend/app/services/query_service.py"
      provides: "Pipeline-level tracing with business metadata"
      contains: "create_trace"
    - path: "backend/app/api/v1/endpoints/query.py"
      provides: "Root trace creation for user requests"
      contains: "trace"
  key_links:
    - from: "backend/app/api/v1/endpoints/query.py"
      to: "backend/app/services/query_service.py"
      via: "trace context propagation"
      pattern: "trace.*id"
    - from: "backend/app/services/query_service.py"
      to: "backend/app/observability/tracing.py"
      via: "import"
      pattern: "from.*observability import"
---

<objective>
Implement end-to-end request tracing with pipeline spans and business metadata enrichment.

Purpose: Create comprehensive request tracing that captures the complete user query pipeline, including root traces for each request, pipeline-level spans for key processing steps, and business metadata for observability and analysis.
Output: Complete end-to-end observability with trace context propagation throughout the request pipeline.
</objective>

<execution_context>
@C:/Users/ParthYangandul/.config/opencode/get-shit-done/workflows/execute-plan.md
@C:/Users/ParthYangandul/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-langfuse-integration/01-CONTEXT.md
@.planning/phases/01-langfuse-integration/01-RESEARCH.md
@backend/app/services/query_service.py
@backend/app/api/v1/endpoints/query.py
@backend/app/llm/agents/interpreter.py
@.planning/phases/01-langfuse-integration/01-langfuse-integration-01-PLAN.md
@.planning/phases/01-langfuse-integration/01-langfuse-integration-03-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add root trace creation to query endpoint</name>
  <files>backend/app/api/v1/endpoints/query.py</files>
  <action>Create a root trace for each user query request in the query endpoint. Attach user_id, query text, and timestamp to the trace. Propagate trace context through the request pipeline by passing trace ID to the query service.</action>
  <verify>grep -n "create_trace\|langfuse" backend/app/api/v1/endpoints/query.py</verify>
  <done>Query endpoint creates root traces with user context</done>
</task>

<task type="auto">
  <name>Task 2: Implement pipeline spans in query service</name>
  <files>backend/app/services/query_service.py</files>
  <action>Implement pipeline-level spans for the four key steps: intent detection, LLM query generation, stored procedure execution, and response formatting. Use the trace context from the endpoint to create child spans. Measure latency for each span and capture inputs/outputs where applicable.</action>
  <verify>grep -n "span\|trace" backend/app/services/query_service.py | wc -l</verify>
  <done>All four pipeline steps properly instrumented with spans</done>
</task>

<task type="auto">
  <name>Task 3: Add business metadata enrichment</name>
  <files>backend/app/services/query_service.py</files>
  <action>Extract and attach business metadata to traces including: intent (from intent detection), stored_procedure_name (from LLM output), tables_used (if available from interpretation), success/failure status, and error messages. Ensure metadata is properly structured for Langfuse UI querying.</action>
  <verify>grep -n "metadata\|update" backend/app/services/query_service.py</verify>
  <done>Business metadata properly attached to traces</done>
</task>

<task type="auto">
  <name>Task 4: Implement error handling in traces</name>
  <files>backend/app/services/query_service.py</files>
  <action>Wrap pipeline operations in try/catch blocks to capture exceptions in Langfuse traces. Mark trace status as "failure" when exceptions occur and include detailed error information in trace metadata. Ensure graceful degradation when tracing fails.</action>
  <verify>grep -n "except\|error\|failure" backend/app/services/query_service.py</verify>
  <done>Complete error handling implementation for observability</done>
</task>

</tasks>

<verification>
- Root traces created for every user query request
- Four pipeline spans properly implemented with correct hierarchy
- Business metadata attached and queryable in Langfuse
- Error conditions captured and marked as failures
- Trace context properly propagated through request pipeline
</verification>

<success_criteria>
- Every user request has a complete trace with pipeline visibility
- Business context available for analysis and debugging
- Error scenarios fully observable with detailed metadata
- No impact on existing request processing logic
- Trace performance overhead minimal (<20ms)
</success_criteria>

<output>
After completion, create `.planning/phases/01-langfuse-integration/01-langfuse-integration-04-SUMMARY.md`
</output>