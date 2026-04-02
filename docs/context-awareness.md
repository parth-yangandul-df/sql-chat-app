# Context Awareness in QueryWise

## Overview

QueryWise maintains conversational context across multi-turn interactions so that follow-up queries like *"Which of these know Python?"* correctly refine prior results instead of being treated as standalone questions.

The system achieves this through a layered approach: **state threading**, **follow-up detection**, **topic switch detection**, **parameter carry-forward**, and **declarative SQL refinement**. No LLM is used for context management — everything is deterministic and fast.

---

## 1. The State Container: `GraphState`

Every query flows through a LangGraph `StateGraph` that threads a single shared state dict (`GraphState`) through all pipeline nodes. The context-relevant fields are:

| Field | Type | Purpose |
|---|---|---|
| `session_id` | `str \| None` | Chat thread identifier |
| `conversation_history` | `list[dict]` | Prior turns: `[{role, content}, ...]` |
| `last_turn_context` | `dict \| None` | Structured context from the previous turn |

`last_turn_context` is the key. It carries forward from the `query_service` response as `turn_context`:

```python
turn_context = {
    "intent": "active_resources",       # prior intent
    "domain": "resource",               # prior domain
    "params": {"skill": "Java"},        # prior extracted params
    "columns": ["EMPID", "Name", ...],  # result column names
    "sql": "SELECT ... FROM ...",       # base SQL (not refinement-wrapped)
}
```

This structured context — not raw conversation text — is what enables deterministic follow-up handling.

---

## 2. Follow-Up Detection

**File:** `backend/app/llm/graph/nodes/intent_classifier.py`

When a new question arrives, the intent classifier first checks whether it's a thin refinement follow-up:

```python
def _is_refinement_followup(question: str, last_turn_context: dict | None) -> bool:
```

A question is classified as a follow-up when:
1. `last_turn_context` exists (there was a prior result), **AND**
2. Either:
   - The question is **short** (≤3 content words after stripping stop words), **OR**
   - **≥30% of content words** overlap with prior column names or parameter values

This is **state-based detection**, not regex-based. It doesn't look for phrases like "these" or "those" — it looks at signal density.

### Follow-Up Fast Path

When a follow-up is detected, the system **skips embedding entirely** and inherits the prior domain and intent with `confidence=0.95`:

```python
return {
    "domain": inherited_domain,
    "intent": inherited_intent,
    "confidence": 0.95,  # forces extract_params → run_domain_tool
}
```

This means a question like *"filter by Java"* after *"show active resources"* immediately routes to the same domain agent with the same intent — no LLM, no embedding cost.

RBAC gates still apply: a `user`-role account cannot inherit a cross-user domain intent.

---

## 3. Topic Switch Detection

**File:** `backend/app/llm/graph/nodes/intent_classifier.py`

Not every subsequent question is a refinement. The system detects when the user has **changed subject** so that prior context is cleared rather than inherited.

```python
def _is_topic_switch(current_domain, current_intent, last_turn_context) -> bool:
```

A topic switch is detected when:
- **Domain changes** (e.g., `resource` → `project`) — always a switch
- **Major intent switch** within the same domain (e.g., `active_resources` → `benched_resources`)

The switch logic uses hardcoded pairs per domain:

```python
_RESOURCE_TOPIC_SWITCHES = frozenset({
    ("active_resources", "benched_resources"),
    ("active_resources", "resource_by_skill"),
    ("benched_resources", "active_resources"),
    # ...
})
```

When a topic switch is detected in `query_service.py`:
- `turn_context` is set to `None` in the response
- The frontend receives `topic_switch_detected: true`
- The next query arrives with `last_turn_context = None`, starting fresh

---

## 4. Parameter Carry-Forward

**File:** `backend/app/llm/graph/nodes/param_extractor.py`

The parameter extractor runs after intent classification. It merges prior params with newly extracted ones:

```python
# Start with inherited params from prior turn
params = dict(last_turn_context.get("params") or {})

# Strip internal refine keys so they don't cascade
params.pop("_refine_mode", None)
params.pop("_prior_sql", None)
params.pop("_prior_columns", None)

# Extract new params from the current question (regex-based)
# New values overlay inherited ones
```

This means if a prior turn had `{"skill": "Java", "start_date": "2024-01-01"}` and the follow-up says *"filter by Python"*, the merged params become `{"skill": "Python", "start_date": "2024-01-01"}` — the date persists, the skill updates.

### Refinement Mode Activation

When the current intent matches the prior intent and there's a prior SQL:

```python
if prior_sql and prior_intent == current_intent:
    params["_refine_mode"] = True
    params["_prior_sql"] = prior_sql
    params["_prior_columns"] = last_turn_context.get("columns", [])
```

This signals to the domain agent that it should **wrap the prior SQL as a subquery** with additional filters, not re-run the base query.

---

## 5. Declarative SQL Refinement

**File:** `backend/app/llm/graph/domains/refinement_registry.py`

The refinement registry is a declarative system of **templates** that define how to wrap a prior SQL result set with additional filter conditions.

### Template Structure

```python
RefinementTemplate(
    domain="resource",
    intent="active_resources",
    refinement_type=RefinementType.SKILL_FILTER,
    column="EMPID",
    sql_template="SELECT prev.* FROM ({prior_sql}) AS prev JOIN ... WHERE s.Name LIKE ?",
    params_required=3,
    param_keys=("skill", "skill", "skill"),
)
```

Each template specifies:
- Which domain + intent it applies to
- What type of filter (skill, name, date range, status, numeric, boolean, text)
- The SQL pattern with `{prior_sql}` placeholder
- Which params to extract and how many

### Refinement Execution

**File:** `backend/app/llm/graph/domains/base_domain.py`

When `_refine_mode=True`, `BaseDomainAgent.execute()` tries refinement in priority order:

1. **Registry-based** — find a matching template whose required params are present
2. **Subclass override** — custom `_run_refinement()` logic (e.g., ResourceAgent's skill JOIN)
3. **Base fallback** — run the base intent unchanged (safe degradation)

The prior SQL is always the **base SQL** (stored via `_prior_sql`), not the refinement-wrapped version. This prevents parameter accumulation across chained refinements.

### Supported Refinement Types

| Type | SQL Pattern | Example |
|---|---|---|
| `SKILL_FILTER` | JOIN PA_ResourceSkills + PA_Skills | "which know Python" |
| `NAME_FILTER` | WHERE prev.[NameCol] LIKE ? | "filter by Alice" |
| `DATE_RANGE` | WHERE prev.[DateCol] BETWEEN ? AND ? | "from 2024-01 to 2024-06" |
| `STATUS_FILTER` | WHERE prev.[StatusCol] LIKE ? | "only benched ones" |
| `NUMERIC_FILTER` | WHERE prev.[NumCol] >= ? | "with more than 50 hours" |
| `BOOLEAN_FILTER` | WHERE prev.[BoolCol] = ? | "only billable" |
| `TEXT_FILTER` | WHERE prev.[TextCol] LIKE ? | "about migration" |

The registry covers **all 24 intents** across all 5 domains (resource, client, project, timesheet, user_self) with dozens of refinement templates.

---

## 6. Conversation History Enrichment

For the **LLM fallback path** (when intent confidence < threshold), the system enriches the question with prior context before embedding:

```python
def _resolve_question(question: str, history: list[dict]) -> str:
    prior = [t["content"] for t in history if t.get("role") == "user"][-2:]
    return " | ".join(prior + [question])
```

This transforms *"filter by active only"* into *"show me all resources | who are billable | filter by active only"* — giving the schema linker enough signal to select the right tables.

The **bare question** is still passed to the LLM for SQL generation; only the embedding uses the enriched version.

---

## 7. LLM Path: Context-Aware SQL Generation

When the query falls through to the LLM fallback path (`llm_fallback.py`):

1. **Resolved question** (enriched with prior turns) is used for `build_context()` — semantic retrieval gets the full conversational picture
2. **Bare question** is used for LLM routing and SQL generation
3. **Conversation history** (up to 6 turns) is passed to `QueryComposerAgent` so the LLM sees the full exchange
4. **Scope constraints** are injected for `user`-role accounts (non-negotiable ResourceId filter)

---

## 8. API Contract

The context awareness is exposed through the query API:

### Request (`QueryRequest`)

```python
session_id: UUID | None              # chat thread ID
conversation_history: list[Turn]     # prior turns (max 6)
last_turn_context: TurnContext | None  # structured context from prior response
clear_context: bool = False          # explicit context reset
```

### Response

```python
turn_context: dict | None            # structured context for next turn
topic_switch_detected: bool          # whether context was cleared
```

The frontend is responsible for:
- Passing `last_turn_context` from the previous response into the next request
- Detecting `topic_switch_detected` and clearing its local context
- Supporting a `clear_context` flag for user-initiated resets

---

## 9. End-to-End Example

### Turn 1
```
User: "Show active resources"
→ Intent: active_resources (confidence 0.82)
→ Domain agent executes base SQL
→ Response includes turn_context with intent, domain, params, columns, sql
```

### Turn 2
```
User: "Which know Python?"
→ _is_refinement_followup: True (short question + prior context)
→ Inherits intent=active_resources, domain=resource (confidence 0.95)
→ extract_params: skill="Python" (fallback extraction from bare content word)
→ _refine_mode activated (same intent + prior SQL)
→ BaseDomainAgent finds SKILL_FILTER template
→ Wraps prior SQL: SELECT prev.* FROM (base_sql) AS prev JOIN PA_ResourceSkills ...
→ Returns refined results
```

### Turn 3
```
User: "Show overdue projects"
→ Intent: overdue_projects, domain=project (confidence 0.78)
→ _is_topic_switch: True (domain changed resource→project)
→ query_service sets turn_context=None, topic_switch_detected=True
→ Fresh context for next turn
```

---

## 10. Design Principles

| Principle | Implementation |
|---|---|
| **State over LLM** | Context is managed deterministically via GraphState, not LLM reasoning |
| **Structured context** | `last_turn_context` carries typed data (intent, params, columns, SQL), not raw text |
| **Fast path first** | Follow-ups skip embedding and go directly to domain tools |
| **Graceful degradation** | If refinement fails, base intent runs unchanged |
| **Base SQL preservation** | `_prior_sql` always stores the original, preventing parameter accumulation |
| **Explicit reset** | `clear_context` flag and topic switch detection prevent stale context leakage |
| **RBAC-aware** | Context inheritance respects role-based access constraints |
