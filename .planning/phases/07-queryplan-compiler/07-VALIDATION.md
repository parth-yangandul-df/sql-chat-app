---
phase: 07
slug: queryplan-compiler
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode="auto") |
| **Config file** | backend/pyproject.toml (existing) |
| **Quick run command** | `cd backend && pytest tests/test_query_plan_model.py tests/test_field_registry.py -xvs` |
| **Full suite command** | `cd backend && pytest tests/ -xvs` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_query_plan_model.py tests/test_field_registry.py tests/test_filter_extractor.py -xvs`
- **After every plan wave:** Run `cd backend && pytest tests/ -xvs`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | QP-01 | unit | `pytest tests/test_query_plan_model.py -xvs` | ❌ W1 | ⬜ pending |
| 07-01-02 | 01 | 1 | QP-01 | unit | `pytest tests/test_query_plan_model.py -xvs` | ❌ W1 | ⬜ pending |
| 07-01-03 | 01 | 1 | QP-01 | integration | `pytest tests/test_queryplan_integration.py -xvs` | ❌ W1 | ⬜ pending |
| 07-02-01 | 02 | 1 | QP-02 | unit | `pytest tests/test_field_registry.py -xvs` | ❌ W1 | ⬜ pending |
| 07-02-02 | 02 | 2 | QP-02 | unit | `pytest tests/test_filter_extractor.py -xvs` | ❌ W1 | ⬜ pending |
| 07-02-03 | 02 | 2 | QP-02 | unit | `pytest tests/test_plan_updater.py -xvs` | ❌ W1 | ⬜ pending |
| 07-02-04 | 02 | 2 | QP-02 | integration | `pytest tests/test_queryplan_integration.py -xvs` | ❌ W2 | ⬜ pending |
| 07-03-01 | 03 | 1 | QP-03 | unit | `pytest tests/test_sql_compiler.py -xvs` | ❌ W1 | ⬜ pending |
| 07-03-02 | 03 | 1 | QP-03 | integration | `pytest tests/test_queryplan_integration.py -xvs` | ❌ W1 | ⬜ pending |
| 07-03-03 | 03 | 2 | QP-03 | integration | `pytest tests/test_queryplan_integration.py::test_resource_chain -xvs` | ❌ W2 | ⬜ pending |
| 07-03-04 | 03 | 3 | QP-03 | import | `pytest tests/test_retirement.py -xvs` | ❌ W3 | ⬜ pending |
| 07-03-05 | 03 | 3 | QP-03 | cleanup | `pytest tests/test_retirement.py -xvs` | ❌ W3 | ⬜ pending |
| 07-04-01 | 04 | 1 | QP-04 | integration | `pytest tests/test_semantic_wiring.py -xvs` | ❌ W1 | ⬜ pending |
| 07-04-02 | 04 | 1 | QP-04 | integration | `pytest tests/test_semantic_wiring.py -xvs` | ❌ W1 | ⬜ pending |
| 07-04-03 | 04 | 2 | QP-04 | integration | `pytest tests/test_semantic_wiring.py -xvs` | ❌ W2 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_query_plan_model.py` — stubs for QueryPlan/FilterClause tests
- [ ] `tests/test_field_registry.py` — stubs for FieldRegistry tests
- [ ] `tests/test_filter_extractor.py` — stubs for filter extraction tests
- [ ] `tests/test_plan_updater.py` — stubs for accumulation rule tests
- [ ] `tests/test_sql_compiler.py` — stubs for SQL compilation tests
- [ ] `tests/test_queryplan_integration.py` — stubs for 5 regression flows
- [ ] `tests/test_semantic_wiring.py` — stubs for glossary/dict/metric tests
- [ ] `tests/test_retirement.py` — stubs for old module retirement tests
- [ ] `tests/conftest.py` — shared fixtures (existing, extend with QueryPlan fixtures)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Feature flag cutover | QP-03 | Requires deployment env change | Set `USE_QUERY_PLAN_COMPILER=true` in .env, run docker compose up, verify regression flows pass |
| RBAC guard (user_self + None resource_id) | QP-03 | Requires authenticated session simulation | Call API with user_self intent and no resource_id, expect 422 error |
| Graceful degradation (LLM fallback turn) | QP-03 | Requires LLM provider | Trigger LLM fallback, then switch to domain tool, verify fresh plan starts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending