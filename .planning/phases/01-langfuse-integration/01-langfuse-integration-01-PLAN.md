---
phase: 01-langfuse-integration
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: ["backend/pyproject.toml", "backend/app/observability/__init__.py", "backend/app/observability/langfuse_client.py", "backend/app/config.py"]
autonomous: true
requirements: ["OBS-01"]
must_haves:
  truths:
    - "Langfuse SDK is installed and configured"
    - "Langfuse client initializes with environment variables"
    - "Configuration is centralized and reusable"
  artifacts:
    - path: "backend/pyproject.toml"
      provides: "Langfuse dependency"
      contains: "langfuse"
    - path: "backend/app/observability/langfuse_client.py"
      provides: "Langfuse client singleton"
      min_lines: 20
    - path: "backend/app/config.py"
      provides: "Environment variable configuration"
      contains: "LANGFUSE_PUBLIC_KEY"
  key_links:
    - from: "backend/app/observability/langfuse_client.py"
      to: "backend/app/config.py"
      via: "import"
      pattern: "from.*config import LANGFUSE"
---

<objective>
Setup Langfuse foundation with SDK installation and centralized client configuration.

Purpose: Establish the observability foundation by installing Langfuse SDK and creating a reusable client configuration that can be imported throughout the application.
Output: Configured Langfuse client with environment variable support.
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
@backend/app/config.py
@backend/pyproject.toml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Install Langfuse SDK and update dependencies</name>
  <files>backend/pyproject.toml</files>
  <action>Add langfuse>=2.0 to the [project.dependencies] section in pyproject.toml. Place it after httpx but before sse-starlette to maintain alphabetical order within the dependencies list.</action>
  <verify>grep -n "langfuse" backend/pyproject.toml</verify>
  <done>Langfuse SDK added to project dependencies</done>
</task>

<task type="auto">
  <name>Task 2: Create observability module structure</name>
  <files>backend/app/observability/__init__.py</files>
  <action>Create the observability module directory with an __init__.py file that exports the main components. Initialize with the basic module structure following Python package conventions.</action>
  <verify>test -d backend/app/observability && test -f backend/app/observability/__init__.py</verify>
  <done>Observability module created with proper Python package structure</done>
</task>

<task type="auto">
  <name>Task 3: Implement Langfuse client singleton</name>
  <files>backend/app/observability/langfuse_client.py</files>
  <action>Create a Langfuse client singleton that initializes with environment variables. Implement lazy initialization pattern with proper error handling for missing credentials. The client should be importable and reusable across the application.</action>
  <verify>python -c "from backend.app.observability.langfuse_client import get_langfuse_client; print('Client import successful')" 2>/dev/null</verify>
  <done>Langfuse client singleton properly configured with environment variables</done>
</task>

<task type="auto">
  <name>Task 4: Add Langfuse configuration to app config</name>
  <files>backend/app/config.py</files>
  <action>Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST environment variables to the Pydantic Settings configuration. Use proper Optional[str] typing and default values (None for keys, "https://cloud.langfuse.com" for host).</action>
  <verify>grep -n "LANGFUSE" backend/app/config.py</verify>
  <done>Langfuse environment variables properly configured in app settings</done>
</task>

</tasks>

<verification>
- Langfuse SDK successfully installed in pyproject.toml
- Observability module created with proper package structure
- Langfuse client singleton implemented with environment variable support
- Configuration variables added to app config with proper typing
</verification>

<success_criteria>
- Langfuse client can be imported without errors
- Client initialization works with valid environment variables
- Graceful error handling for missing credentials
- Configuration centralized in app settings
</success_criteria>

<output>
After completion, create `.planning/phases/01-langfuse-integration/01-langfuse-integration-01-SUMMARY.md`
</output>