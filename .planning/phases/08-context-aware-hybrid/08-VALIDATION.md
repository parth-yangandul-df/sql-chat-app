---
phase: 08
slug: context-aware-hybrid
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-07
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode="auto") |
| **Config file** | backend/pyproject.toml (existing) |
| **Quick run command** | `cd backend && pytest tests/test_context_aware_hybrid.py -xvs` |
| **Full suite command** | `cd backend && pytest tests/ -xvs` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_context_aware_hybrid.py -xvs`
- **After every plan wave:** Run `cd backend && pytest tests/ -xvs`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | Hybrid State Management | unit | `pytest tests/test_graph_state_extension.py -xvs` | ⬜ pending |
| 08-01-02 | 01 | 1 | Embedding Similarity | unit | `pytest tests/test_followup_detection.py -xvs` | ⬜ pending |
| 08-02-01 | 02 | 2 | Confidence Scoring | unit | `pytest tests/test_confidence_scoring.py -xvs` | ⬜ pending |
| 08-02-02 | 02 | 2 | LLM Extraction | unit | `pytest tests/test_llm_extraction.py -xvs` | ⬜ pending |
| 08-03-01 | 03 | 1 | Deterministic Override | unit | `pytest tests/test_deterministic_override.py -xvs` | ⬜ pending |
| 08-03-02 | 03 | 1 | Conflict Resolution | unit | `pytest tests/test_conflict_resolution.py -xvs` | ⬜ pending |
| 08-04-01 | 04 | 1 | Fallback Ladder | integration | `pytest tests/test_fallback_ladder.py -xvs` | ⬜ pending |
| 08-04-02 | 04 | 2 | Context Recovery | integration | `pytest tests/test_context_recovery.py -xvs` | ⬜ pending |
| 08-05-01 | 05 | 1 | Query Caching | unit | `pytest tests/test_query_caching.py -xvs` | ⬜ pending |
| 08-05-02 | 05 | 2 | Observability | integration | `pytest tests/test_observability.py -xvs` | ⬜ pending |
| 08-06-01 | 06 | 1 | Semantic Layer Integration | integration | `pytest tests/test_semantic_integration.py -xvs` | ⬜ pending |
| 08-06-02 | 06 | 2 | End-to-End Hybrid Flow | integration | `pytest tests/test_hybrid_e2e.py -xvs` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_graph_state_extension.py` — stubs for extended GraphState tests
- [ ] `tests/test_followup_detection.py` — stubs for follow-up detection logic
- [ ] `tests/test_confidence_scoring.py` — stubs for confidence calculation
- [ ] `tests/test_llm_extraction.py` — stubs for LLM JSON extraction
- [ ] `tests/test_deterministic_override.py` — stubs for override rules
- [ ] `tests/test_conflict_resolution.py` — stubs for field conflict handling
- [ ] `tests/test_fallback_ladder.py` — stubs for 6-level fallback chain
- [ ] `tests/test_context_recovery.py` — stubs for context recovery logic
- [ ] `tests/test_query_caching.py` — stubs for caching mechanism
- [ ] `tests/test_observability.py` — stubs for logging/observability
- [ ] `tests/test_semantic_integration.py` — stubs for glossary/metrics/dict
- [ ] `tests/test_hybrid_e2e.py` — stubs for full hybrid flow tests
- [ ] `tests/conftest.py` — extend with hybrid mode fixtures

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Semantic similarity threshold tuning | Follow-up Detection | Requires real embedding data | Run queries with varying similarity scores, verify refine vs new classification |
| LLM fallback cost tracking | Observability | Requires production LLM calls | Set up monitoring, verify fallback counts per session |
| Production stress testing | End-to-End | Requires full load | Simulate 100+ concurrent sessions, verify graceful degradation |
| RBAC with new hybrid flow | Security | Requires authenticated context | Test user_self domain with hybrid mode, verify RBAC still enforced |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending