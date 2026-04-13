# 🚀 QueryWise v2 — Context-Aware Hybrid AI Query System (Implementation Prompt)

## 🎯 Objective

Upgrade the existing QueryWise system into a **production-grade conversational query engine** that:

* Maintains **robust multi-turn context**
* Uses **deterministic logic wherever possible**
* Uses **LLM only where necessary (controlled + structured)**
* Minimizes **cost and failure propagation**
* Handles **follow-ups, refinements, and new queries intelligently**
* Compiles **syntactically correct SQL via structured query plans (NOT raw LLM SQL)**

---

# 🧠 Core Design Principles

1. **LLM = Parser, NOT decision maker**
2. **System state = source of truth**
3. **Deterministic layers override LLM outputs**
4. **Graceful degradation > hard failure**
5. **Structured query plan → SQL compilation**
6. **Context = structured state, NOT raw chat**

---

# ⚙️ System Architecture Overview

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

---

# 🔷 1. State Management (`GraphState`)

### MUST include:

```python
GraphState = {
    "session_id": str,
    "last_query": str,
    "last_query_embedding": list[float],
    "last_intent": str,
    "last_filters": list[dict],
    "last_query_plan": dict,
    "last_base_sql": str,
}
```

---

# 🔷 2. Intent Classification (Embedding-Based)

### Model:

* `nomic-embed-text` (local via Ollama)

### Steps:

1. Precompute embeddings for:

   * intent descriptions
2. Compute cosine similarity with query
3. Select best match

```python
if similarity < 0.6:
    intent = "unknown"
```

---

# 🔷 3. Follow-up Detection (CRITICAL)

### Inputs:

* current query embedding
* previous query embedding
* previous intent

---

### Logic:

```python
if intent != last_intent:
    follow_up_type = "new"

elif same_field_detected:
    follow_up_type = "replace"

elif semantic_similarity > 0.7:
    follow_up_type = "refine"

else:
    follow_up_type = "new"
```

---

### Definitions:

| Type    | Meaning                  |
| ------- | ------------------------ |
| refine  | add new filters          |
| replace | replace existing filters |
| new     | discard previous context |

---

# 🔷 4. LLM Extraction (Single Call Only)

### Model:

* Llama 3.3 70B Versatile

---

### Prompt Requirements:

* STRICT JSON output
* NO explanation
* NO hallucinated fields

---

### Output Schema:

```json
{
  "filters": [
    {
      "field": "skill",
      "operator": "contains",
      "value": "python"
    }
  ],
  "sort": [
    {"field": "experience", "order": "desc"}
  ],
  "limit": 50,
  "follow_up_type": "refine"
}
```

---

# 🔷 5. Deterministic Override Layer

### NEVER trust LLM blindly

---

### Rules:

#### 1. Intent mismatch override

```python
if current_intent != last_intent:
    follow_up_type = "new"
```

---

#### 2. Same field → REPLACE

```python
if new_filter.field == existing_filter.field:
    remove(existing_filter)
```

---

#### 3. Different field → ADD

```python
filters.append(new_filter)
```

---

#### 4. Field validation

* Must exist in semantic layer
* Must match intent schema

---

# 🔷 6. Query Plan Builder

### Build structured plan:

```json
{
  "intent": "active_resources",
  "filters": [...],
  "sort": [...],
  "limit": 50
}
```

---

### Merge logic:

```python
if follow_up_type == "new":
    plan = new_plan

elif follow_up_type == "refine":
    plan.filters += new_filters

elif follow_up_type == "replace":
    plan.filters = replace_same_fields(plan.filters, new_filters)
```

---

# 🔷 7. SQL Compilation (CRITICAL)

### DO NOT use LLM for SQL

---

### Use:

* base query registry
* join registry
* filter mapping

---

### Example:

```python
SELECT r.*
FROM Resource r
JOIN PA_ResourceSkills rs ON ...
WHERE r.IsActive = 1
AND s.Name LIKE '%Python%'
```

---

### MUST ensure:

* valid joins
* correct aliases
* no duplicate joins
* proper WHERE clause chaining

---

# 🔷 8. Filter Extraction Fallback Ladder

### MUST implement multi-level fallback:

---

## 🥇 Level 1: Retry LLM

* stronger prompt
* stricter formatting

---

## 🥈 Level 2: Heuristic Extraction

```python
KNOWN_SKILLS = ["python", "java", ".net"]

if token in KNOWN_SKILLS:
    extract skill filter
```

---

## 🥉 Level 3: Context Recovery

```python
if no_filters and last_filters:
    infer from query tokens
```

---

## 🧠 Level 4: Partial Execution

```python
if partial filters:
    run partial query
```

---

## 🧨 Level 5: Clarification

Ask user instead of failing

---

## 💣 Level 6: Full LLM Fallback

ONLY when:

* intent unknown
* extraction completely failed

---

# 🔷 9. Confidence Scoring

### Compute:

```python
confidence = 0

if valid_json: +0.3
if valid_fields: +0.3
if matches_schema: +0.4
```

---

### Decision:

```python
if confidence >= 0.7:
    accept
elif >= 0.4:
    partial fallback
else:
    fallback ladder
```

---

# 🔷 10. Conflict Resolution (CRITICAL)

### Example:

```
Python → .NET
```

---

### Rule:

```python
if same_field:
    REPLACE

if different_field:
    ADD
```

---

# 🔷 11. Sorting & Ranking Layer

### Extract:

* order by
* top N

---

### Apply:

```sql
ORDER BY Experience DESC
LIMIT 10
```

---

# 🔷 12. Semantic Layer Integration

### MUST use:

* glossary
* metrics
* dictionary

---

### Map:

| User Term | DB Column      |
| --------- | -------------- |
| "dev"     | ResourceName   |
| "skill"   | PA_Skills.Name |

---

### LLM must output canonical field names

---

# 🔷 13. Query Caching

### Cache:

```python
key = hash(intent + filters + sort)
```

---

### Reuse:

* identical queries
* repeated follow-ups

---

# 🔷 14. Observability

### Log EVERYTHING:

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

# 🚨 Critical Requirements

### MUST:

* Never trust LLM output blindly
* Never generate SQL via LLM (except fallback)
* Always validate filters
* Always maintain base query integrity
* Always preserve context correctly

---

# 🔥 Final Goal

Transform system from:

❌ rigid + fragile
❌ regex dependent
❌ high LLM cost

---

Into:

✅ adaptive + context-aware
✅ deterministic + controllable
✅ cost-efficient
✅ production-ready

---

# 🚀 End of Prompt
