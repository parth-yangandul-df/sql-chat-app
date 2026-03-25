---
phase: 01-langfuse-integration
plan: 03
type: execute
wave: 2
depends_on: ["01-langfuse-integration-01", "01-langfuse-integration-02"]
files_modified: ["backend/app/llm/providers/base_provider.py", "backend/app/llm/providers/anthropic_provider.py", "backend/app/llm/providers/openai_provider.py", "backend/app/llm/providers/ollama_provider.py"]
autonomous: true
requirements: ["OBS-02", "OBS-06", "OBS-10"]
must_haves:
  truths:
    - "All LLM calls create Langfuse traces with token usage"
    - "LLM latency and model information captured"
    - "Errors from LLM calls are properly traced"
    - "Cost tracking implemented where available"
  artifacts:
    - path: "backend/app/llm/providers/base_provider.py"
      provides: "Base LLM provider with tracing"
      contains: "observe"
    - path: "backend/app/llm/providers/anthropic_provider.py"
      provides: "Anthropic provider with trace wrapping"
      contains: "@observe"
    - path: "backend/app/llm/providers/openai_provider.py"
      provides: "OpenAI provider with trace wrapping"
      contains: "@observe"
    - path: "backend/app/llm/providers/ollama_provider.py"
      provides: "Ollama provider with trace wrapping"
      contains: "@observe"
  key_links:
    - from: "backend/app/llm/providers/*.py"
      to: "backend/app/observability/tracing.py"
      via: "import"
      pattern: "from.*observability import observe"
---

<objective>
Wrap all LLM provider calls with Langfuse observability for complete token tracking and cost monitoring.

Purpose: Implement comprehensive LLM observability by wrapping all provider-specific LLM calls with Langfuse tracing, capturing token usage, latency, model information, and implementing cost tracking where available.
Output: All LLM calls fully instrumented with observability without modifying business logic.
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
@backend/app/llm/providers/base_provider.py
@backend/app/llm/providers/anthropic_provider.py
@backend/app/llm/providers/openai_provider.py
@backend/app/llm/providers/ollama_provider.py
@.planning/phases/01-langfuse-integration/01-langfuse-integration-01-PLAN.md
@.planning/phases/01-langfuse-integration/01-langfuse-integration-02-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Wrap base LLM provider with tracing decorator</name>
  <files>backend/app/llm/providers/base_provider.py</files>
  <action>Import the @observe decorator from observability.tracing and apply it to the abstract methods in BaseLLMProvider (create and stream methods). Ensure the decorator properly handles async methods and captures model information.</action>
  <verify>grep -n "@observe\|from.*observability" backend/app/llm/providers/base_provider.py</verify>
  <done>Base LLM provider properly decorated for tracing</done>
</task>

<task type="auto">
  <name>Task 2: Add observability to Anthropic provider</name>
  <files>backend/app/llm/providers/anthropic_provider.py</files>
  <action>Import and apply the @observe decorator to AnthropicProvider's create and stream methods. Add cost tracking logic for Anthropic models using their pricing structure. Handle token extraction from Anthropic response format.</action>
  <verify>grep -n "@observe" backend/app/llm/providers/anthropic_provider.py</verify>
  <done>Anthropic provider fully instrumented with tracing and cost tracking</done>
</task>

<task type="auto">
  <name>Task 3: Add observability to OpenAI provider</name>
  <files>backend/app/llm/providers/openai_provider.py</files>
  <action>Import and apply the @observe decorator to OpenAIProvider's create and stream methods. Add cost tracking for OpenAI models using their pricing. Capture token usage directly from OpenAI response object.</action>
  <verify>grep -n "@observe" backend/app/llm/providers/openai_provider.py</verify>
  <done>OpenAI provider fully instrumented with tracing and cost tracking</done>
</task>

<task type="auto">
  <name>Task 4: Add observability to Ollama provider</name>
  <files>backend/app/llm/providers/ollama_provider.py</files>
  <action>Import and apply the @observe decorator to OllamaProvider's create and stream methods. Implement manual token counting for Ollama responses since they don't provide token usage. Add error handling for tracing failures.</action>
  <verify>grep -n "@observe" backend/app/llm/providers/ollama_provider.py</verify>
  <done>Ollama provider fully instrumented with tracing and manual token counting</done>
</task>

</tasks>

<verification>
- All LLM providers properly decorated with @observe
- Token usage captured for OpenAI/Anthropic (automatic) and Ollama (manual)
- Cost tracking implemented for supported providers
- Error handling in place for tracing failures
- Async methods properly wrapped
</verification>

<success_criteria>
- LLM calls create traces with complete token information
- Latency measurements captured for all providers
- Model information properly attached to spans
- Cost calculations working for supported models
- No breaking changes to provider interfaces
</success_criteria>

<output>
After completion, create `.planning/phases/01-langfuse-integration/01-langfuse-integration-03-SUMMARY.md`
</output>