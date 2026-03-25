---
phase: 01-langfuse-integration
plan: 05
type: execute
wave: 3
depends_on: ["01-langfuse-integration-01"]
files_modified: ["backend/app/middleware/__init__.py", "backend/app/middleware/observability_middleware.py", "backend/app/main.py"]
autonomous: true
requirements: ["OBS-07", "OBS-08"]
must_haves:
  truths:
    - "FastAPI middleware captures HTTP observability without interference"
    - "Endpoints, methods, latency, and status codes captured"
    - "Optional metrics persistence to SQL Server implemented"
    - "No interference with Langfuse tracing"
  artifacts:
    - path: "backend/app/middleware/observability_middleware.py"
      provides: "HTTP observability middleware"
      min_lines: 40
    - path: "backend/app/services/observability_service.py"
      provides: "Metrics persistence service"
      min_lines: 30
    - path: "backend/app/main.py"
      provides: "Middleware registration"
      contains: "middleware"
  key_links:
    - from: "backend/app/main.py"
      to: "backend/app/middleware/observability_middleware.py"
      via: "middleware registration"
      pattern: "add_middleware"
    - from: "backend/app/middleware/observability_middleware.py"
      to: "backend/app/observability/tracing.py"
      via: "import"
      pattern: "from.*observability import"
---

<objective>
Implement FastAPI middleware for HTTP observability and optional metrics persistence.

Purpose: Create FastAPI middleware to capture HTTP request/response information for observability, and optionally persist LLM metrics to SQL Server for additional analytics and reporting capabilities.
Output: Complete HTTP observability with optional local metrics storage.
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
@backend/app/main.py
@backend/app/db/models/
@.planning/phases/01-langfuse-integration/01-langfuse-integration-01-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create observability middleware module</name>
  <files>backend/app/middleware/observability_middleware.py</files>
  <action>Create FastAPI middleware for HTTP observability that captures endpoint, HTTP method, latency, and status code without interfering with Langfuse tracing. Use proper async middleware pattern and ensure minimal performance impact.</action>
  <verify>test -f backend/app/middleware/observability_middleware.py</verify>
  <done>HTTP observability middleware created with proper async handling</done>
</task>

<task type="auto">
  <name>Task 2: Implement optional metrics persistence service</name>
  <files>backend/app/services/observability_service.py</files>
  <action>Create a service for persisting LLM metrics to SQL Server. Implement the LLM_Metrics table model insertion logic with UserId, Query, Token counts, Latency, Model, Cost, Intent, StoredProcedure, Status, and Timestamp fields. Use async patterns matching the codebase.</action>
  <verify>test -f backend/app/services/observability_service.py</verify>
  <done>Metrics persistence service implemented with async SQL operations</done>
</task>

<task type="auto">
  <name>Task 3: Register middleware in FastAPI application</name>
  <files>backend/app/main.py</files>
  <action>Import and register the observability middleware in the FastAPI application. Ensure it's added in the correct order to avoid conflicts with existing middleware and exception handlers.</action>
  <verify>grep -n "observability" backend/app/main.py</verify>
  <done>Middleware properly registered in FastAPI application</done>
</task>

<task type="auto">
  <name>Task 4: Update middleware exports and integration</name>
  <files>backend/app/middleware/__init__.py</files>
  <action>Create or update the middleware __init__.py file to properly export the observability middleware for clean imports. Ensure the module follows the same patterns as other middleware modules.</action>
  <verify>test -f backend/app/middleware/__init__.py</verify>
  <done>Middleware module exports properly configured</done>
</task>

</tasks>

<verification>
- Observability middleware captures HTTP metrics correctly
- Metrics persistence service created with proper async patterns
- Middleware registered in FastAPI without conflicts
- Clean module exports for easy importing
- No interference with existing Langfuse tracing
</verification>

<success_criteria>
- HTTP requests tracked with endpoint, method, latency, and status
- Optional metrics persistence to SQL Server working correctly
- Middleware adds minimal overhead to request processing
- No conflicts with existing exception handlers or middleware
- Graceful degradation when metrics persistence fails
</success_criteria>

<output>
After completion, create `.planning/phases/01-langfuse-integration/01-langfuse-integration-05-SUMMARY.md`
</output>