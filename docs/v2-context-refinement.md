# QueryWise V2 — Full Implementation Prompt (Production-Grade)

---

# 1. Objective

Implement a **context-aware conversational query system** that:

* Supports **multi-turn refinement**
* Uses **deterministic SQL compilation (primary path)**
* Uses **LLM fallback only when required**
* Produces **valid, optimized SQL always**
* Scales across domains without exponential complexity

---

# 2. System Architecture

## 2.1 Execution Flow

### Primary Path (Deterministic)

```id="flow1"
User Query
→ Intent Classification
→ Structured Filter Extraction (LLM-assisted + rules)
→ QueryPlan Update
→ Conflict Resolution
→ Validation
→ SQL Compilation
→ Execution
```

---

### Fallback Path (LLM)

```id="flow2"
User Query
→ No intent OR low confidence
→ Context enrichment
→ LLM SQL generation
→ SQL validation
→ Execution
```

---

# 3. Core Design Principle

> SQL is **compiled from state**, never mutated or wrapped.

---

# 4. State Model

## 4.1 QueryPlan

```python
class QueryPlan:
    domain: str
    intent: str
    filters: list[Filter]
    sort: list[Sort]
    limit: int | None
```

---

## 4.2 Filter Object

```python
class Filter:
    field: str
    op: str          # =, LIKE, >=, <=, BETWEEN, IN
    value: Any       # str | int | list | tuple
```

---

## 4.3 Sort Object

```python
class Sort:
    field: str
    direction: str   # "asc" | "desc"
```

---

# 5. Metadata Layer (MANDATORY)

---

## 5.1 Base Query Registry

```python
BASE_QUERIES = {
    "active_resources": {
        "select": [...],
        "from": "...",
        "joins": {...},
        "base_filters": [...],
        "default_sort": [...]
    }
}
```

---

## 5.2 Field Registry

```python
FIELD_REGISTRY = {
    "skill": {
        "column": "s.Name",
        "type": "string",
        "joins": ["resource_skills", "skills"]
    }
}
```

---

## 5.3 Join Registry

```python
JOIN_REGISTRY = {
    "skills": "JOIN PA_Skills s ON ..."
}
```

---

## 5.4 Operator Rules

```python
ALLOWED_OPERATORS = {"=", "LIKE", ">=", "<=", "BETWEEN", "IN"}
```

---

# 6. Structured Filter Extraction (LLM-Assisted)

---

## 6.1 Objective

Convert natural language into structured filters **strictly aligned with schema**.

---

## 6.2 Input

```python
{
    "question": str,
    "available_fields": list[str],
    "conversation_history": list[dict]
}
```

---

## 6.3 Output (STRICT)

```json
[
  {"field": "skill", "op": "LIKE", "value": "python"}
]
```

---

## 6.4 LLM Prompt Requirements

The LLM MUST:

* Only use fields from `available_fields`
* Only use allowed operators
* Normalize values (case-insensitive)
* Avoid hallucinating fields

---

## 6.5 Post-Processing (MANDATORY)

```python
def normalize_filters(filters):
    for f in filters:
        f["field"] = f["field"].lower().strip()
        if isinstance(f["value"], str):
            f["value"] = f["value"].lower().strip()
    return filters
```

---

## 6.6 Validation

Reject filter if:

* field not in FIELD_REGISTRY
* operator not allowed

---

## 6.7 Fallback

```python
try:
    filters = llm_extract(...)
    validate(filters)
except:
    filters = regex_extract(...)
```

---

# 7. QueryPlan Update Logic

---

## 7.1 Rules

| Case              | Action          |
| ----------------- | --------------- |
| No previous state | Create new plan |
| Same intent       | Merge filters   |
| Different intent  | Reset plan      |

---

## 7.2 Implementation

```python
def update_plan(existing, intent, filters):
    if not existing or existing.intent != intent:
        plan = QueryPlan()
        plan.intent = intent
        plan.filters = filters
        return plan

    existing.filters.extend(filters)
    return existing
```

---

# 8. Conflict Resolution Layer

---

## 8.1 Problem

Multiple values for same field:

* "Python and Java developers"
* "Mumbai and Pune"

---

## 8.2 Rules

| Field Type | Strategy    |
| ---------- | ----------- |
| string     | OR          |
| numeric    | range / AND |
| date       | BETWEEN     |
| boolean    | last wins   |

---

## 8.3 Implementation

```python
def resolve_conflicts(filters):
    grouped = {}

    for f in filters:
        grouped.setdefault(f["field"], []).append(f["value"])

    resolved = []

    for field, values in grouped.items():
        if len(values) == 1:
            resolved.append({
                "field": field,
                "op": "LIKE",
                "value": values[0]
            })
        else:
            resolved.append({
                "field": field,
                "op": "IN",
                "value": list(set(values))
            })

    return resolved
```

---

# 9. Sorting & Ranking Layer

---

## 9.1 QueryPlan Extension

```python
plan.sort = [
    {"field": "name", "direction": "asc"}
]
```

---

## 9.2 Natural Language Mapping

| Query Phrase | Mapping   |
| ------------ | --------- |
| "top"        | DESC      |
| "latest"     | date DESC |
| "lowest"     | ASC       |

---

## 9.3 Default Sorting

Defined in BASE_QUERIES

---

## 9.4 SQL Integration

```sql
ORDER BY column ASC|DESC
```

---

# 10. SQL Compiler

---

## 10.1 Responsibilities

* Construct SELECT, FROM, JOIN, WHERE
* Resolve joins
* Apply filters
* Handle IN, BETWEEN, LIKE
* Deduplicate joins

---

## 10.2 Implementation (Key Logic)

```python
def compile_query(plan):
    base = BASE_QUERIES[plan.intent]

    joins = dict(base["joins"])
    where = []
    params = []

    # base filters
    for col, op, val in base["base_filters"]:
        where.append(f"{col} {op} ?")
        params.append(val)

    for f in plan.filters:
        config = FIELD_REGISTRY[f["field"]]

        for j in config["joins"]:
            joins[j] = JOIN_REGISTRY[j]

        col = config["column"]

        if f["op"] == "IN":
            placeholders = ",".join(["?"] * len(f["value"]))
            where.append(f"{col} IN ({placeholders})")
            params.extend(f["value"])

        elif f["op"] == "LIKE":
            where.append(f"{col} LIKE ?")
            params.append(f"%{f['value']}%")

        elif f["op"] == "BETWEEN":
            where.append(f"{col} BETWEEN ? AND ?")
            params.extend(f["value"])

        else:
            where.append(f"{col} {f['op']} ?")
            params.append(f["value"])

    query = f"SELECT {', '.join(base['select'])} FROM {base['from']}"

    if joins:
        query += " " + " ".join(joins.values())

    if where:
        query += " WHERE " + " AND ".join(where)

    return query, tuple(params)
```

---

# 11. Validation Layer

---

## Must Validate

* Intent exists
* Fields valid
* Operators valid
* No empty filters
* No SQL injection vectors

---

# 12. LLM Fallback

---

## 12.1 Trigger Conditions

* No intent match
* Low confidence
* Unsupported query type

---

## 12.2 Flow

```python
resolved_question = enrich_with_history(question)

context = retrieve_schema_context()

sql = llm_generate(resolved_question, context)

validate(sql)

execute(sql)
```

---

## 12.3 Constraints

* Enforce RBAC
* Restrict tables
* Validate SQL before execution

---

# 13. Context Handling

---

## Deterministic Path

* Uses QueryPlan only

## LLM Path

* Uses conversation history

---

# 14. Performance Rules

* No nested queries
* Prefer joins
* Limit result size
* Use indexed columns

---

# 15. Migration Plan

1. Move SQL → BASE_QUERIES
2. Replace refinement → FIELD_REGISTRY
3. Add QueryPlan
4. Implement compiler
5. Integrate LLM extraction
6. Keep fallback intact

---

# 16. Success Criteria

* Follow-ups refine correctly
* SQL always valid
* No nested queries
* Handles multi-value filters
* Sorting works
* LLM fallback works safely

---

# Final Principle

> This is a **query planner system**, not a chatbot

---

# 17. Semantic Layer Integration

---

## 17.1 Objective

Bridge **natural language → business concepts → database schema**

---

## 17.2 Components

### 1. Glossary

Maps user language → canonical concepts

```python
GLOSSARY = {
    "developer": ["resource", "engineer"],
    "backend": ["python", "java"],
    "frontend": ["react", "angular"]
}
```

---

### 2. Metrics

Defines computed fields

```python
METRICS = {
    "utilization": {
        "formula": "SUM(ts.Hours) / 160",
        "type": "numeric"
    }
}
```

---

### 3. Dictionary (Field Mapping)

```python
DICTIONARY = {
    "resource_name": {
        "aliases": ["name", "employee", "resource"],
        "column": "r.ResourceName"
    },
    "skill": {
        "aliases": ["tech", "technology", "stack"],
        "column": "s.Name"
    }
}
```

---

## 17.3 Semantic Resolution Pipeline

```python
def resolve_semantics(question):
    tokens = tokenize(question)

    resolved = []

    for token in tokens:
        # Step 1: glossary expansion
        expanded = GLOSSARY.get(token, [token])

        for term in expanded:
            # Step 2: dictionary mapping
            for field, config in DICTIONARY.items():
                if term in config["aliases"]:
                    resolved.append(field)

    return resolved
```

---

## 17.4 Integration with Filter Extraction

```python
fields = resolve_semantics(question)

filters = llm_extract(question, fields)
```

---

## 17.5 Metric Handling

If query contains metric:

```python
if "utilization" in question:
    plan.metrics.append("utilization")
```

Compiler must inject:

```sql
SUM(ts.Hours) / 160 AS utilization
```

---

## 17.6 Key Rule

> Semantic layer modifies **meaning**, not SQL directly

---

# 18. Query Caching & Result Reuse

---

## 18.1 Objective

Avoid re-running expensive queries across conversational turns

---

## 18.2 Cache Types

### 1. Plan Cache

```python
cache_key = hash(QueryPlan)

PLAN_CACHE[cache_key] = sql
```

---

### 2. Result Cache

```python
RESULT_CACHE[cache_key] = result_dataframe
```

---

## 18.3 Cache Key Design

```python
def build_cache_key(plan):
    return hash((
        plan.intent,
        tuple(sorted([(f["field"], str(f["value"])) for f in plan.filters]))
    ))
```

---

## 18.4 Reuse Strategy

### Case 1: Exact Match

```python
if cache_key in RESULT_CACHE:
    return RESULT_CACHE[cache_key]
```

---

### Case 2: Refinement (IMPORTANT)

If new plan = old plan + extra filters:

```python
if previous_result_exists:
    filtered = apply_in_memory_filter(previous_result, new_filters)
    return filtered
```

---

## 18.5 In-Memory Filtering

```python
def apply_in_memory_filter(df, filters):
    for f in filters:
        if f["op"] == "LIKE":
            df = df[df[f["field"]].str.contains(f["value"], case=False)]
    return df
```

---

## 18.6 When NOT to Cache

* Large datasets (> threshold)
* Queries with volatile data
* LLM fallback queries

---

## 18.7 Cache Invalidation

* TTL (e.g., 5 minutes)
* Data update trigger
* Manual clear

---

# 19. Combined Flow with Enhancements

```id="flow3"
User Query
→ Semantic Resolution
→ Filter Extraction
→ QueryPlan Update
→ Conflict Resolution
→ Cache Check
   → hit → return
   → miss → compile SQL
→ Execute
→ Store in cache
```

---

# 20. Performance Impact

| Feature        | Impact            |
| -------------- | ----------------- |
| Semantic Layer | + usability       |
| QueryPlan      | + correctness     |
| Caching        | + speed (10–100x) |

---

# Final Principle

> Semantic layer understands the user
> QueryPlan understands the query
> Compiler understands the database

---
