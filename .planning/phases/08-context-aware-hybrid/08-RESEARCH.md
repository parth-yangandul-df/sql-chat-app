# Phase 08: Context-Aware Hybrid AI Query System — Research

**Researched:** 2026-04-07
**Researcher:** Orchestrator (PRD analysis + codebase context)

## 1. PRD Design Summary

The v2-context-refinement.md PRD defines a hybrid system that:
- Uses deterministic logic wherever possible
- Uses LLM only where necessary (controlled + structured)
- Compiles SQL via structured query plans (NOT raw LLM SQL)

### Core Pipeline Flow
```
User Query
   ↓
[Preprocessing]
   ↓
[Intent Classification (Embeddings)]
   ↓
[Follow-up Detection (Deterministic + Embedding)]
   ↓
[LLM Structured Extraction (Single Call)]
   ↓
[Validation + Override Layer]
   ↓
[Query Plan Builder]
   ↓
[SQL Compiler]
   ↓
[Execution]
```

## 2. Required GraphState Extension

From PRD, must extend GraphState with:
```python
GraphState = {
    "session_id": str,
    "last_query": str,
    "last_query_embedding": list[float],
    "last_intent": str,
    "last_filters": list[dict],
    "last_query_plan": dict,  # Already exists from Phase 7
    "last_base_sql": str,    # Already exists from Phase 7
}
```

Plus new for hybrid mode:
- `current_query_embedding`: computed at classify_intent
- `semantic_similarity`: computed for follow-up detection
- `follow_up_type`: "refine" | "replace" | "new"
- `confidence_breakdown`: dict with valid_json, valid_fields, matches_schema scores

## 3. Follow-up Detection Logic

### Inputs Required
- Current query embedding (computed at classify_intent)
- Previous query embedding (from GraphState)
- Previous intent (from GraphState)

### Decision Matrix
| Condition | Follow-up Type |
|-----------|----------------|
| `current_intent != last_intent` | "new" (topic switch) |
| Same field detected | "replace" |
| `semantic_similarity > 0.7` | "refine" |
| Else | "new" |

**Note:** PRD specifies "same_field_detected" - need to define how to detect this.

## 4. LLM Extraction Design

### Single-Call Requirement
- One LLM call per query (not per filter)
- Strict JSON output, no explanation

### Output Schema
```json
{
  "filters": [{"field": "skill", "operator": "contains", "value": "python"}],
  "sort": [{"field": "experience", "order": "desc"}],
  "limit": 50,
  "follow_up_type": "refine"
}
```

### Provider
- PRD specifies "Llama 3.3 70B Versatile" (already configured in project as DEFAULT_LLM_MODEL)

## 5. Deterministic Override Layer

### Override Rules (in order)
1. **Intent mismatch**: If `current_intent != last_intent` → follow_up_type = "new"
2. **Same field**: Remove existing, add new
3. **Different field**: Append to filters
4. **Field validation**: Must exist in semantic layer, must match intent schema

## 6. Confidence Scoring

### Formula
```
confidence = 0
if valid_json: +0.3
if valid_fields: +0.3
if matches_schema: +0.4
```

### Decision Thresholds
- >= 0.7: accept
- >= 0.4: partial fallback
- < 0.4: fallback ladder

## 7. Fallback Ladder (6 Levels)

| Level | Method | When |
|-------|--------|------|
| 1 | Retry LLM | stronger prompt, stricter format |
| 2 | Heuristic Extraction | KNOWN_* constants (skills, dates) |
| 3 | Context Recovery | infer from query tokens |
| 4 | Partial Execution | run partial query |
| 5 | Clarification | ask user |
| 6 | Full LLM Fallback | intent unknown + extraction failed |

## 8. SQL Compilation (Deterministic)

- DO NOT use LLM for SQL (except fallback)
- Uses: base query registry, join registry, filter mapping
- Must ensure: valid joins, correct aliases, no duplicate joins, proper WHERE chaining

## 9. Semantic Layer Integration

- Must use: glossary, metrics, dictionary
- Map user terms to DB columns:
  - "dev" → ResourceName
  - "skill" → PA_Skills.Name
- LLM must output canonical field names (validated against FieldRegistry)

## 10. Query Caching

- Cache key: hash(intent + filters + sort)
- Reuse: identical queries, repeated follow-ups

## 11. Observability Requirements

Every query must log:
```json
{
  "query": "...",
  "intent": "...",
  "filters": [...],
  "follow_up_type": "...",
  "confidence": 0.82,
  "final_sql": "...",
  "fallback_used": "heuristic"
}
```

---

## Validation Architecture

### Test File Structure
```
backend/tests/
├── test_graph_state_extension.py      # Extended state fields
├── test_followup_detection.py         # Semantic similarity + type detection
├── test_confidence_scoring.py         # Confidence calculation
├── test_llm_extraction.py             # JSON extraction with fallback
├── test_deterministic_override.py     # Override rules
├── test_conflict_resolution.py        # Field conflict handling
├── test_fallback_ladder.py            # 6-level fallback chain
├── test_context_recovery.py           # Level 3 recovery
├── test_query_caching.py              # Cache hit/miss
├── test_observability.py              # Structured logging
├── test_semantic_integration.py      # Glossary/dict/metrics
└── test_hybrid_e2e.py                # Full hybrid flow
```

### Key Integration Points with Phase 7
- Reuse: FieldRegistry from 07-02
- Reuse: QueryPlan + FilterClause from 07-01
- Reuse: sql_compiler.py from 07-03
- Reuse: semantic_resolver.py from 07-04
- Extend: GraphState TypedDict
- Extend: intent_classifier node with embedding storage

### Regression Test Flows
1. **Hybrid flow**: "show active resources" → "with Python" → "add seniority filter" (all hybrid, no LLM SQL)
2. **Follow-up detection**: Verify refine vs replace vs new classification
3. **Fallback ladder**: Test each level triggers correctly
4. **Graceful degradation**: Embedding failure → LLM fallback → graceful
5. **Conflict resolution**: Add skill=Python, then skill=.NET (should replace, not add)

---

*Phase: 08-context-aware-hybrid*
*Researched: 2026-04-07 via PRD express path + codebase context*