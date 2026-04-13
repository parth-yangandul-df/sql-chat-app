# 🔷 QueryWise – Advanced Implementation Prompt (Semantic + Context-Aware Query Engine)

---

## 🎯 Objective

Build a **production-grade conversational query system** that:

* Uses **deterministic domain tools**
* Supports **multi-turn context-aware refinement**
* Falls back to **LLM when needed**
* Evolves into a **semantic query engine (NOT just a chatbot)**

---

# ⚠️ CRITICAL DESIGN CORRECTION (MUST IMPLEMENT)

## 🚨 Problem

The current system has:

* Glossary ✅
* Metrics ✅
* Dictionary ✅
* Knowledge Docs ✅

BUT:

> ❌ These are **passive metadata only**

They are:

* Read by LLM occasionally
* NOT used in deterministic execution
* NOT part of query construction

---

## ✅ Required Transformation

> Convert semantic layer from **descriptive → executable**

---

## 🔁 Correct Architecture

### ❌ Current Flow

```text
User Query
→ Intent Classification
→ Param Extraction (regex)
→ Domain Tool SQL
```

---

### ✅ Required Flow

```text
User Query
→ Semantic Resolution Layer  ← (NEW)
→ Structured Filter Extraction (LLM-assisted)
→ QueryPlan Builder
→ Conflict Resolution
→ Cache Check
→ SQL Compiler
→ Execution
→ Response
```

---

# 🧠 1. SEMANTIC LAYER (EXECUTABLE)

---

## 1.1 Glossary (Upgrade Required)

### ❌ Current

```python
"Resource Name" → "Resource.ResourceName"
```

### ✅ Required

```python
{
  "term": "developer",
  "aliases": ["engineer", "resource", "employee"],
  "maps_to": "resource_entity"
}

{
  "term": "active",
  "maps_to_filter": {
    "field": "Resource.IsActive",
    "op": "=",
    "value": 1
  }
}

{
  "term": "available",
  "maps_to_filter": {
    "field": "ResourceId",
    "op": "NOT_IN",
    "subquery": "ProjectResource WHERE IsActive = 1"
  }
}
```

---

## 1.2 Dictionary (Must Be Used in Execution)

### ❌ Current

* Only used for display

### ✅ Required

```python
{
  "field": "status",
  "values": {
    "active": 1,
    "inactive": 0
  }
}
```

---

### Integration

```python
def resolve_value(field, value):
    return dictionary[field].get(value, value)
```

---

## 1.3 Metrics (Executable)

### ❌ Current

* Defined but not enforced

### ✅ Required

```python
{
  "metric_name": "utilization",
  "sql_expression": "SUM(ts.Hours) / SUM(pr.Allocation)",
  "required_joins": ["ProjectResource", "Timesheet"],
  "default_filters": ["IsApproved = 1"]
}
```

---

### Usage

```python
if "utilization" in query:
    plan.select.append(metric.sql_expression)
```

---

## 🔥 KEY RULE

> Semantic layer MUST feed QueryPlan — NOT the LLM directly

---

# 🤖 2. STRUCTURED FILTER EXTRACTION (LLM-ASSISTED)

---

## Replace regex param extraction

---

### Input

```json
{
  "question": "Show active backend developers with 5+ years experience"
}
```

---

### Output

```json
{
  "filters": [
    {"field": "skill", "op": "LIKE", "value": "backend"},
    {"field": "experience", "op": ">=", "value": 5},
    {"field": "status", "op": "=", "value": "active"}
  ],
  "sort": [{"field": "experience", "order": "desc"}],
  "limit": 50
}
```

---

### Rules

* Only extract, DO NOT generate SQL
* Must align with semantic layer fields
* Must support:

  * AND / OR logic
  * numeric ops
  * date filters

---

# ⚖️ 3. CONFLICT RESOLUTION

---

### Example

User:

> “Python and Java developers”

---

### Logic

```python
if same_field_multiple_values:
    op = "OR"
```

---

### Output

```json
{
  "field": "skill",
  "op": "OR",
  "value": ["Python", "Java"]
}
```

---

# 🧱 4. QUERY PLAN

---

### Structure

```python
class QueryPlan:
    intent: str
    domain: str
    filters: list
    joins: list
    select: list
    sort: list
    limit: int
```

---

### Update Logic

```python
plan.filters += new_filters
plan.filters = resolve_conflicts(plan.filters)
```

---

# 🧮 5. SQL COMPILER

---

### Must be deterministic (NO LLM)

---

### Steps

```python
def compile_query(plan):
    base = get_base_query(plan.intent)

    joins = resolve_joins(plan)

    where = build_where(plan.filters)

    order = build_order(plan.sort)

    return f"{base} {joins} {where} {order}"
```

---

### Guarantee

* Parameterized SQL only
* No string injection
* Schema-validated fields only

---

# ⚡ 6. QUERY CACHING (NEW)

---

## Types

### 1. Result Cache

```python
RESULT_CACHE[hash(plan)] = result
```

---

### 2. Refinement Reuse

```python
if previous_result:
    return filter_in_memory(previous_result)
```

---

## Rules

* Cache only deterministic queries
* Skip LLM fallback results
* Add TTL (5–10 mins)

---

# 🔁 7. CONTEXT AWARENESS (UPDATED)

---

## Replace SQL refinement approach

### ❌ Current

* Wrap prior SQL

### ✅ Required

* Store QueryPlan
* Update QueryPlan

---

### Example

Turn 1:

```json
filters: []
```

Turn 2:

```json
filters: [{"skill": "Python"}]
```

Turn 3:

```json
filters: [{"skill": "Python"}, {"experience": ">5"}]
```

---

# 🤖 8. LLM FALLBACK (KEEP)

---

## When to trigger

* Intent unknown
* Schema mismatch
* Complex aggregation

---

## Rules

* Use semantic layer for grounding
* Apply RBAC filters
* Do NOT cache results

---

# 🧩 9. FINAL SYSTEM FLOW

```text
User Query
→ Semantic Resolution
→ LLM Filter Extraction
→ QueryPlan Update
→ Conflict Resolution
→ Cache Check
    → hit → return
    → miss → compile SQL
→ Execute
→ Cache result
→ Return response
```

---

# 💣 FINAL PRINCIPLE

> ❌ You are NOT building a chatbot
> ✅ You are building a semantic query engine

---

# 🏁 SUCCESS CRITERIA

System should handle:

* “Show active developers”
* “Which of these know Python”
* “Only senior ones”
* “Sort by experience”

WITHOUT:

* SQL wrapping
* Regex hacks
* LLM SQL generation

---

# 🚀 END GOAL

A system comparable in architecture (not scale) to:

* ThoughtSpot
* Looker

---
