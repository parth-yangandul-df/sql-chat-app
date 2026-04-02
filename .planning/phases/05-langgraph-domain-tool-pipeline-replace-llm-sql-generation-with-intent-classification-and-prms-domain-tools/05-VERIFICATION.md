---
phase: 05-langgraph-domain-tool-pipeline
verified: 2026-03-26T08:20:07Z
status: passed
score: 16/16 requirements verified
gaps:
  - truth: "ensure_catalog_embedded() failure logs warning but does NOT prevent startup"
    status: resolved
    reason: "Fixed in commit 7ae784d — try/except now wraps ensure_catalog_embedded() in main.py lifespan. Exception logs a warning and startup continues."
    artifacts:
      - path: "backend/app/main.py"
        issue: "Resolved: try/except added around ensure_catalog_embedded()."
human_verification:
  - test: "Start the application without an embedding service configured and verify it starts successfully"
    expected: "App starts, logs a warning about catalog embedding failure, and continues serving requests (falling back to LLM pipeline)"
    why_human: "Cannot verify runtime graceful degradation programmatically without a real embedding service failure scenario"
---

# Phase 5: LangGraph Domain Tool Pipeline — Verification Report

**Phase Goal:** Replace `execute_nl_query()` in `query_service.py` with a LangGraph `StateGraph` that routes NL questions to 24 pre-built PRMS domain SQL tools (embedding-based intent classification) or falls back to existing LLM generation.
**Verified:** 2026-03-26T08:20:07Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (derived from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | NL questions matching a known PRMS intent route to domain SQL tools without LLM generation | ✓ VERIFIED | `classify_intent` → cosine similarity → `run_domain_tool` path confirmed; `llm_provider="domain_tool"`, `generated_sql=None` |
| 2 | Low-confidence questions fall back to the existing LLM pipeline transparently | ✓ VERIFIED | `route_after_classify` returns `"llm_fallback"` when `confidence < 0.78`; `llm_fallback.py` reuses all existing agents unchanged |
| 3 | 0-row domain tool results attempt a fallback intent before escalating to LLM | ✓ VERIFIED | `route_after_domain_tool` → `run_fallback_intent` → `route_after_fallback_intent` → `llm_fallback` chain implemented; test passes |
| 4 | SQL Server params bug is fixed — parameterized queries execute correctly | ✓ VERIFIED | `_run_query()` now accepts `params: tuple[Any, ...] \| None` and calls `cursor.execute(sql, params)` when params present |
| 5 | Embedding unavailability degrades gracefully (app starts, pipeline routes to LLM fallback) | ✗ FAILED | `ensure_catalog_embedded()` in `main.py` lifespan has **no try/except** — embedding failure crashes startup (LG-16 gap) |
| 6 | `generate_sql_only()` and `execute_raw_sql()` are completely unchanged | ✓ VERIFIED | Both functions present and unmodified in `query_service.py` (lines 91–224); original imports retained |

**Score:** 5/6 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/pyproject.toml` | `langgraph>=0.2` and `langchain-core>=0.3` in llm extras | ✓ VERIFIED | Both present in `llm` extras group |
| `backend/app/llm/graph/__init__.py` | Package init | ✓ VERIFIED | Exists |
| `backend/app/llm/graph/state.py` | `GraphState` TypedDict with 24 keys | ✓ VERIFIED | 24 keys confirmed: `answer`, `confidence`, `connection_id`, `connection_string`, `connector_type`, `db`, `domain`, `error`, `execution_id`, `execution_time_ms`, `explanation`, `generated_sql`, `highlights`, `intent`, `llm_model`, `llm_provider`, `max_rows`, `params`, `question`, `result`, `retry_count`, `sql`, `suggested_followups`, `timeout_seconds` |
| `backend/app/llm/graph/intent_catalog.py` | 24-entry `INTENT_CATALOG` + `ensure_catalog_embedded()` + `get_catalog_embeddings()` | ✓ VERIFIED | 24 entries (Resource×9, Client×5, Project×6, Timesheet×4); idempotent lock via `asyncio.Lock`; imports `embed_text` from `app.services.embedding_service` |
| `backend/app/llm/graph/nodes/__init__.py` | Package init | ✓ VERIFIED | Exists |
| `backend/app/llm/graph/nodes/intent_classifier.py` | `classify_intent` + `route_after_classify` | ✓ VERIFIED | Cosine similarity via numpy; `TOOL_CONFIDENCE_THRESHOLD` env var (default `0.78`); INFO/WARNING logging; `route_after_classify` returns `"extract_params"` (not `"run_domain_tool"`) on high confidence |
| `backend/app/llm/graph/nodes/param_extractor.py` | `extract_params` regex extractor | ✓ VERIFIED | Regex patterns for skill, ISO dates, resource name; returns empty `{}` when no match; no LLM calls |
| `backend/app/connectors/base_connector.py` | `execute_query()` abstract signature with `params: tuple[Any, ...] \| None = None` | ✓ VERIFIED | Line 89: `params: tuple[Any, ...] \| None = None` |
| `backend/app/connectors/sqlserver/connector.py` | `_run_query()` passes params to `cursor.execute()` | ✓ VERIFIED | Lines 331–334: `if params: await cursor.execute(sql, params) else: await cursor.execute(sql)` |
| `backend/app/llm/graph/domains/__init__.py` | Package init | ✓ VERIFIED | Exists |
| `backend/app/llm/graph/domains/base_domain.py` | `BaseDomainAgent` ABC with `execute()` + `_run_intent()` | ✓ VERIFIED | `execute()` sets `llm_provider="domain_tool"`, `llm_model=intent`; delegates to `_run_intent()` |
| `backend/app/llm/graph/domains/resource.py` | `ResourceAgent` — 9 intents | ✓ VERIFIED | All 9 intents present: `active_resources`, `resource_by_skill`, `resource_utilization`, `resource_billing_rate`, `resource_availability`, `resource_project_assignments`, `resource_timesheet_summary`, `overallocated_resources`, `resource_skills_list` |
| `backend/app/llm/graph/domains/client.py` | `ClientAgent` — 5 intents | ✓ VERIFIED | All 5 intents present |
| `backend/app/llm/graph/domains/project.py` | `ProjectAgent` — 6 intents | ✓ VERIFIED | All 6 intents present |
| `backend/app/llm/graph/domains/timesheet.py` | `TimesheetAgent` — 4 intents with `IsApproved/IsDeleted/IsRejected` filter | ✓ VERIFIED | `_VALID = "ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0"` applied to all valid-entry intents; `unapproved_timesheets` correctly inverts to `IsApproved = 0` |
| `backend/app/llm/graph/domains/registry.py` | `DOMAIN_REGISTRY` dict + `run_domain_tool` node | ✓ VERIFIED | `DOMAIN_REGISTRY` maps 4 domains; `run_domain_tool` raises `ValueError` for unknown domain |
| `backend/app/llm/graph/nodes/fallback_intent.py` | `run_fallback_intent` + `route_after_domain_tool` + `route_after_fallback_intent` | ✓ VERIFIED | 1-hop max enforced; `route_after_domain_tool` checks `fallback_intent` in catalog; `route_after_fallback_intent` always bottoms out at `llm_fallback` |
| `backend/app/llm/graph/nodes/result_interpreter.py` | `interpret_result` — skips LLM on 0 rows | ✓ VERIFIED | Returns `answer=None, highlights=[], suggested_followups=[]` when `not result or not result.rows` |
| `backend/app/llm/graph/nodes/llm_fallback.py` | `llm_fallback` — reuses `QueryComposerAgent` + retry loop | ✓ VERIFIED | Imports `QueryComposerAgent`, `SQLValidatorAgent`, `ErrorHandlerAgent`; mirrors original pipeline logic |
| `backend/app/llm/graph/nodes/history_writer.py` | `write_history` — persists `QueryExecution` | ✓ VERIFIED | Creates `QueryExecution` with `execution_status="error" if error else "success"`; calls `db.add()` + `db.flush()` |
| `backend/app/llm/graph/graph.py` | Compiled 7-node `StateGraph` + `get_compiled_graph()` singleton | ✓ VERIFIED | All 7 nodes: `classify_intent`, `extract_params`, `run_domain_tool`, `run_fallback_intent`, `llm_fallback`, `interpret_result`, `write_history`; topology with conditional 0-row fallback chain |
| `backend/app/services/query_service.py` | `execute_nl_query()` delegates to `get_compiled_graph().ainvoke()` | ✓ VERIFIED | Lines 15–88: imports `get_compiled_graph` and `GraphState`; builds 24-key `initial_state`; calls `ainvoke()`; maps final_state to 17-key response dict; `generate_sql_only()` and `execute_raw_sql()` untouched |
| `backend/app/main.py` | `ensure_catalog_embedded()` called in lifespan after `ensure_embedding_dimensions()` | ⚠️ PARTIAL | Called at correct position (lines 23–25), but **missing try/except** — LG-16 requires graceful failure |
| `backend/tests/test_graph_state.py` | Tests all 24 GraphState annotation keys | ✓ VERIFIED | 1 test, passes |
| `backend/tests/test_intent_catalog.py` | Tests count (24), domain counts, unique names, valid domains, idempotency | ✓ VERIFIED | 5 tests, all pass |
| `backend/tests/test_intent_classifier.py` | Tests classify_intent routing + extract_params | ✓ VERIFIED | 8 tests, all pass |
| `backend/tests/test_domain_agents.py` | Tests all agents + registry + parameterized SQL | ✓ VERIFIED | 8 tests, all pass |
| `backend/tests/test_graph_nodes.py` | Tests interpret_result (0/non-0 rows), write_history (success/error) | ✓ VERIFIED | 4 tests, all pass |
| `backend/tests/test_graph_pipeline.py` | Full pipeline tests + execute_nl_query integration | ✓ VERIFIED | 7 tests, all pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `intent_catalog.py` | `embedding_service.py` | `from app.services.embedding_service import embed_text` | ✓ WIRED | Line 12 of `intent_catalog.py`; used in `ensure_catalog_embedded()` |
| `intent_classifier.py` | `intent_catalog.py` | `from app.llm.graph.intent_catalog import INTENT_CATALOG, ensure_catalog_embedded, get_catalog_embeddings` | ✓ WIRED | Line 9; `get_catalog_embeddings()` called in `classify_intent()` |
| `intent_classifier.py` | `embedding_service.py` | `from app.services.embedding_service import embed_text` | ✓ WIRED | Line 11; called in `classify_intent()` to embed the question |
| `base_domain.py` | `connector_registry.py` | `from app.connectors.connector_registry import get_or_create_connector` | ✓ WIRED | Used in `execute()` to get connector for the question's connection |
| `registry.py` | `resource.py` | `DOMAIN_REGISTRY = {"resource": ResourceAgent, ...}` | ✓ WIRED | `ResourceAgent` imported and mapped |
| `graph.py` | `intent_classifier.py` | `graph.add_node("classify_intent", classify_intent)` | ✓ WIRED | Line 41; entry point node |
| `graph.py` | `registry.py` | `graph.add_node("run_domain_tool", run_domain_tool)` | ✓ WIRED | Line 43 |
| `graph.py` | `fallback_intent.py` | `graph.add_conditional_edges("run_domain_tool", route_after_domain_tool, ...)` | ✓ WIRED | Lines 62–70 |
| `llm_fallback.py` | `query_composer.py` | `from app.llm.agents.query_composer import QueryComposerAgent` | ✓ WIRED | Line 11; called in `llm_fallback()` |
| `history_writer.py` | `query_history.py` | `from app.db.models.query_history import QueryExecution` | ✓ WIRED | Line 6; `QueryExecution` instantiated in `write_history()` |
| `query_service.py` | `graph.py` | `from app.llm.graph.graph import get_compiled_graph` | ✓ WIRED | Line 15; called in `execute_nl_query()` |
| `query_service.py` | `state.py` | `from app.llm.graph.state import GraphState` | ✓ WIRED | Line 16; `initial_state: GraphState = {...}` |
| `main.py` | `intent_catalog.py` | `from app.llm.graph.intent_catalog import ensure_catalog_embedded` | ⚠️ PARTIAL | Called (line 25) but not wrapped in try/except as required by LG-16 |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| LG-01 | 05-01-PLAN | LangGraph deps in `pyproject.toml` | ✓ SATISFIED | `langgraph>=0.2` and `langchain-core>=0.3` present in `llm` extras |
| LG-02 | 05-01-PLAN | `GraphState` TypedDict with 24 keys | ✓ SATISFIED | `state.py` — all 24 keys confirmed by `test_graph_state.py` |
| LG-03 | 05-01-PLAN | `INTENT_CATALOG` with 24 entries (Resource×9, Client×5, Project×6, Timesheet×4) | ✓ SATISFIED | `intent_catalog.py` — verified by runtime check and `test_intent_catalog.py` |
| LG-04 | 05-01-PLAN | `ensure_catalog_embedded()` idempotent, uses `embed_text()` | ✓ SATISFIED | `asyncio.Lock` guard; idempotency test passes |
| LG-05 | 05-02-PLAN | `classify_intent` node — cosine similarity, sets domain/intent/confidence | ✓ SATISFIED | Full implementation with numpy; INFO/WARNING logging; env-var threshold |
| LG-06 | 05-02-PLAN | `route_after_classify` returns `"extract_params"` or `"llm_fallback"`; `extract_params` regex-only | ✓ SATISFIED | `route_after_classify` correctly returns `"extract_params"` (not `"run_domain_tool"`) on high confidence; `extract_params` has no LLM calls |
| LG-07 | 05-03-PLAN | SQLServer `_run_query()` params bug fix | ✓ SATISFIED | `cursor.execute(sql, params)` when params present; both `execute_query()` and abstract `BaseConnector` updated |
| LG-08 | 05-03-PLAN | `ResourceAgent` — 9 intents with `?` placeholders, no `dbo.` prefix | ✓ SATISFIED | All 9 intents; bare table names (`Resource`, `Skill`, etc.); parameterized calls use `params=(f"%{skill}%",)` |
| LG-09 | 05-03-PLAN | `ClientAgent` (5), `ProjectAgent` (6), `TimesheetAgent` (4) with valid-entry filters | ✓ SATISFIED | All counts correct; `_VALID` constant in `timesheet.py`; `unapproved_timesheets` correctly uses `IsApproved = 0` |
| LG-10 | 05-03-PLAN | `DOMAIN_REGISTRY` + `run_domain_tool` node; unknown domain raises `ValueError` | ✓ SATISFIED | 4-entry registry; `ValueError` raised for unknown domain |
| LG-11 | 05-04-PLAN | 0-row fallback chain: `run_fallback_intent` (1 hop) then `llm_fallback` | ✓ SATISFIED | `route_after_domain_tool` and `route_after_fallback_intent` implement correct chain; graph wired; test passes |
| LG-12 | 05-04-PLAN | `interpret_result` node — wraps `ResultInterpreterAgent`; skips LLM on 0 rows | ✓ SATISFIED | Returns `answer=None, highlights=[]` when `not result or not result.rows`; test passes |
| LG-13 | 05-04-PLAN | `llm_fallback` node — reuses existing agents; sets sql/result/generated_sql/retry_count/llm_provider/llm_model/explanation | ✓ SATISFIED | Full retry loop; all required keys set in return dict |
| LG-14 | 05-04-PLAN | `write_history` node; `get_compiled_graph()` singleton; 7-node graph topology | ✓ SATISFIED | `QueryExecution` persisted with correct `execution_status`; singleton via `_compiled_graph` global; 7 nodes confirmed |
| LG-15 | 05-05-PLAN | `execute_nl_query()` delegates to `get_compiled_graph().ainvoke()`; same 17-key response dict | ✓ SATISFIED | Lines 15–88 of `query_service.py`; `generate_sql_only()` and `execute_raw_sql()` untouched; `test_execute_nl_query_response_keys` passes |
| LG-16 | 05-05-PLAN | `main.py` lifespan calls `ensure_catalog_embedded()` after `ensure_embedding_dimensions()`, before `auto_setup_sample_db()`; wrapped in try/except | ✗ BLOCKED | Ordering is correct. **Missing try/except** — LG-16 explicitly requires: "Wrapped in try/except — failure logs warning but does NOT prevent startup". Current implementation propagates exceptions from the embedding service and will crash the app on startup if embedding is unavailable. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/main.py` | 23–25 | Missing try/except around `ensure_catalog_embedded()` | 🛑 Blocker | If embedding service is unavailable at startup (Ollama not running, OpenAI key missing), the app fails to start entirely — violates LG-16 and CLAUDE.md's graceful degradation requirement |
| `backend/app/llm/graph/intent_catalog.py` | 22–23 | `sql_fallback_template` and `fallback_intent` fields on `IntentEntry` are never set (all `None`) | ℹ️ Info | The 0-row fallback chain (`run_fallback_intent`) works but will always return an empty result and escalate to `llm_fallback` — no catalog entries have `fallback_intent` configured. This is by design ("placeholder fields — not wired in this phase") but limits the 0-row chain's effectiveness. |

---

## Human Verification Required

### 1. Embedding Unavailability at Startup

**Test:** Start the application with `OPENAI_API_KEY` intentionally unset (or `OLLAMA_BASE_URL` unreachable), run `docker compose up`, and observe startup behavior.
**Expected:** App starts, logs a WARNING about catalog embedding failure, continues to serve requests; NL queries fall back to LLM pipeline (which itself requires the LLM key, but the app should not crash on startup from the catalog embedding failure alone).
**Why human:** Cannot simulate embedding service failure in unit tests without a real service.

### 2. End-to-End Domain Tool Path (Integration)

**Test:** With a PRMS SQL Server connection configured, send the query "show active resources" via the UI or API.
**Expected:** Response shows `llm_provider: "domain_tool"`, `llm_model: "active_resources"`, `generated_sql: null`, result contains resource rows.
**Why human:** Requires a live PRMS SQL Server database connection to verify the actual SQL execution path.

### 3. LLM Fallback Path (Integration)

**Test:** Send an obscure/off-topic query like "what is the weather in London?" to the API.
**Expected:** Classifier assigns low confidence (< 0.78), query falls through to `llm_fallback`, response shows `llm_provider` = actual LLM provider name (not "domain_tool").
**Why human:** Requires actual embedding model to compute real cosine similarity scores.

---

## Gaps Summary

### Gap: LG-16 Missing try/except Around `ensure_catalog_embedded()`

**Root Cause:** The implementation added `ensure_catalog_embedded()` to the correct position in the lifespan hook (after `ensure_embedding_dimensions()`, before `auto_setup_sample_db()`), satisfying the ordering requirement. However, the REQUIREMENTS.md for LG-16 explicitly states: *"Wrapped in try/except — failure logs warning but does NOT prevent startup."* The `main.py` implementation has no error handling:

```python
# Current (missing try/except):
from app.llm.graph.intent_catalog import ensure_catalog_embedded
await ensure_catalog_embedded()  # ← will crash startup if embedding service unavailable

# Required:
try:
    await ensure_catalog_embedded()
except Exception:
    logger.warning("Intent catalog pre-embedding failed; first query will embed on demand", exc_info=True)
```

**Impact:** If the embedding service is unavailable at startup (e.g., `OLLAMA_BASE_URL` unreachable, or `OPENAI_API_KEY` not set), the app will fail to start. This contradicts the CLAUDE.md graceful degradation design: *"If the embedding model is unavailable... the query pipeline falls back to keyword-only context matching instead of crashing."* The catalog failing to embed at startup should degrade gracefully (embeddings happen on first query call instead), not prevent the app from starting.

**Fix required:** Wrap `await ensure_catalog_embedded()` in `main.py` with a try/except that logs a warning.

---

*Verified: 2026-03-26T08:20:07Z*
*Verifier: Claude (gsd-verifier)*
