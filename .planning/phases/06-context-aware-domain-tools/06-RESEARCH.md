# Phase 6 Research: Context-Aware Domain Tools & Stateful Follow-Up

## Standard Stack (confirmed patterns to use)

- **Backend:** Python 3.12, FastAPI, LangGraph StateGraph (already in place)
- **TypedDict extension:** Add new optional fields to `GraphState` TypedDict using `| None` typing — existing node return dicts that omit the field don't cause errors (TypedDict fields with `None` default work as long as `initial_state` in `query_service.py` explicitly sets them to `None`)
- **Pydantic v2:** Used in `schemas/query.py` — `BaseModel` with `Field(default=None)` for optional backward-compatible fields
- **Regex:** Python `re` module already used in `param_extractor.py` — same pattern for follow-up detection
- **SQL Server parameterized queries:** `?` positional placeholders (pyodbc/aioodbc pattern, already established in Phase 5)
- **React state:** `useState` + `useMutation` already used in ChatPanel.tsx and StandaloneChatPage.tsx
- **TypeScript strict mode:** No `any` allowed — all new types must be fully typed

---

## Architecture Patterns

### Change 1: TurnContext Schema (Backend + Frontend Foundation)

**Python Pydantic (`schemas/query.py`):**
```python
class TurnContext(BaseModel):
    intent: str        # e.g. "benched_resources"
    domain: str        # e.g. "resource"
    params: dict       # e.g. {"skill": "Python"}
    columns: list[str] # e.g. ["EMPID", "Name", "EmailId", "TechCategoryName"]
    sql: str           # The SQL that was executed

# Add to QueryRequest:
last_turn_context: TurnContext | None = None

# Add to query_service.py return dict:
"turn_context": {
    "intent": final_state.get("intent"),
    "domain": final_state.get("domain"),
    "params": final_state.get("params", {}),
    "columns": final_state["result"].columns if final_state.get("result") else [],
    "sql": final_state.get("sql") or "",
} if final_state.get("intent") and final_state.get("domain") else None
```

**TypeScript (`types/api.ts`):**
```typescript
export interface TurnContext {
  intent: string
  domain: string
  params: Record<string, string>
  columns: string[]
  sql: string
}

// Add to QueryResult:
turn_context: TurnContext | null
```

**TypeScript (`api/queryApi.ts`):**
```typescript
execute: (data: {
  connection_id: string
  question: string
  session_id?: string
  conversation_history?: ConversationTurn[]
  last_turn_context?: TurnContext  // ADD THIS
}) => api.post<QueryResult>('/query', data).then((r) => r.data),
```

### Change 2: GraphState extension (`state.py`)

```python
# Add to GraphState TypedDict:
last_turn_context: dict | None  # Structured context from prior turn

# In query_service.py initial_state, add:
"last_turn_context": last_turn_context  # passed from QueryRequest
```

Also update `execute_nl_query()` signature:
```python
async def execute_nl_query(
    ...
    last_turn_context: dict | None = None,
) -> dict:
```

### Change 3: Follow-up detection in `intent_classifier.py`

```python
import re

_FOLLOWUP_PATTERNS = re.compile(
    r"""
    \b(
      which\s+of\s+these |
      which\s+of\s+those |
      among\s+them |
      among\s+these |
      from\s+them |
      from\s+these |
      of\s+those |
      of\s+these |
      filter\s+by |
      filter\s+them |
      only\s+those |
      only\s+these |
      same\s+ones |
      those\s+who |
      these\s+who
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_REFINEMENT_KEYWORDS = re.compile(
    r"\b(skill|know|python|java|who|filter|only|active|inactive|billable|assigned|available)\b",
    re.IGNORECASE,
)

def _is_refinement_followup(question: str, last_turn_context: dict | None) -> bool:
    """Return True if question is a thin follow-up that should inherit prior intent."""
    if not last_turn_context:
        return False
    # Must have a followup pattern
    if not _FOLLOWUP_PATTERNS.search(question):
        return False
    # Must also have some refinement keyword to be worth routing to domain tool
    if not _REFINEMENT_KEYWORDS.search(question):
        return False
    return True
```

Modified `classify_intent()`:
```python
async def classify_intent(state: GraphState) -> dict[str, Any]:
    last_turn_context = state.get("last_turn_context")
    question = state["question"]

    # Follow-up fast path: inherit prior domain/intent
    if _is_refinement_followup(question, last_turn_context):
        logger.info(
            "intent=classify followup_detected q=%r → inheriting intent=%s domain=%s",
            question[:80], last_turn_context["intent"], last_turn_context["domain"],
        )
        return {
            "domain": last_turn_context["domain"],
            "intent": last_turn_context["intent"],
            "confidence": 0.95,  # Above threshold — routes to extract_params
        }

    # Normal embedding path (existing code unchanged)
    ...
```

### Change 4: Param merging in `extract_params.py`

```python
async def extract_params(state: GraphState) -> dict[str, Any]:
    question = state["question"]

    # Start with inherited params from prior turn (carry-forward)
    last_turn_context = state.get("last_turn_context") or {}
    params: dict[str, Any] = dict(last_turn_context.get("params") or {})

    # THEN overlay with newly extracted params (new params win over inherited)
    skill_match = _SKILL_KW_RE.search(question) or _SKILL_TECH_RE.search(question)
    if skill_match:
        params["skill"] = skill_match.group(1)
    # ... rest of extraction unchanged
    
    # Signal refine mode if we inherited from prior turn
    if last_turn_context.get("sql") and last_turn_context.get("intent") == state.get("intent"):
        params["_refine_mode"] = True
        params["_prior_sql"] = last_turn_context["sql"]
        params["_prior_columns"] = last_turn_context.get("columns", [])

    return {"params": params}
```

### Change 5: Domain tool subquery refinement (`base_domain.py` + agents)

```python
# base_domain.py
def _is_refine_mode(params: dict) -> bool:
    return bool(params.get("_refine_mode") and params.get("_prior_sql"))

def _get_prior_sql(params: dict) -> str:
    return params.get("_prior_sql", "")

# Each agent implements _run_refinement():
async def _run_refinement(
    self,
    prior_sql: str,
    params: dict[str, Any],
    connector: Any,
    state: GraphState,
) -> tuple[str, Any]:
    """Override in each domain agent to wrap prior SQL as subquery with new filter."""
    raise NotImplementedError
```

Modified `execute()`:
```python
async def execute(self, state: GraphState) -> dict[str, Any]:
    intent = state["intent"] or ""
    params = state.get("params") or {}
    connector = await get_or_create_connector(...)

    if _is_refine_mode(params):
        prior_sql = _get_prior_sql(params)
        sql, result = await self._run_refinement(prior_sql, params, connector, state)
    else:
        sql, result = await self._run_intent(intent, params, connector, state)
    ...
```

### Change 6: fallback_intent wiring (`intent_catalog.py`)

Set `fallback_intent` on all catalog entries (see mapping below).

### Change 7: Frontend lastTurnContext tracking

**ChatPanel.tsx pattern:**
```tsx
// In ChatPanel or ChatWidget (lifted state):
const [lastTurnContext, setLastTurnContext] = useState<TurnContext | null>(null)

// In sendMessage:
mutation.mutate({ question: trimmed, history, lastTurnContext })

// In mutationFn:
queryApi.execute({
  connection_id: connectionId,
  question,
  session_id: sessionId,           // ADD session_id
  conversation_history: history,
  last_turn_context: lastTurnContext ?? undefined,
})

// In onSuccess:
setLastTurnContext(result.turn_context)  // store for next turn
setMessages((prev) => [...prev, { ..., turn_context: result.turn_context }])
```

---

## SQL Subquery Compatibility (SQL Server)

SQL Server fully supports subquery aliasing:
```sql
SELECT * FROM (SELECT ...) AS prev_result WHERE ...
```

**This is the confirmed SQL Server syntax — `AS` alias is REQUIRED for subqueries.**

### Resource domain refinement SQL patterns

**benched_resources → filter by skill:**
```sql
SELECT prev.*, s.Name AS FilteredSkill
FROM (
  SELECT DISTINCT r.employeeid, r.ResourceName, r.EmailId, t.TechCategoryName
  FROM Resource r
  JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId
  JOIN Project p ON pr.ProjectId = p.ProjectId
  JOIN TechCatagory t ON t.TechCategoryId = r.TechCategoryId
  WHERE p.ProjectId = 119
  ORDER BY r.ResourceName
) AS prev
JOIN Resource r2 ON r2.EmployeeId = prev.employeeid
JOIN PA_ResourceSkills rs ON rs.ResourceId = r2.ResourceId
JOIN PA_Skills s ON s.SkillId = rs.SkillId
WHERE s.Name LIKE ?
```

**IMPORTANT:** SQL Server does not allow `ORDER BY` in subqueries unless `TOP` or `OFFSET/FETCH` is used. The benched_resources SQL has `ORDER BY r.ResourceName` at the end — must be removed when used as a subquery. The param extractor should strip ORDER BY from prior_sql before wrapping.

**Helper function needed:**
```python
def _strip_order_by(sql: str) -> str:
    """Remove trailing ORDER BY clause for use as subquery."""
    return re.sub(r'\s+ORDER\s+BY\s+.+$', '', sql, flags=re.IGNORECASE | re.DOTALL).strip()
```

**active_resources → filter by skill:**
```sql
SELECT prev.*
FROM (<prior_sql_stripped>) AS prev
JOIN Resource r2 ON r2.EmployeeId = prev.[EMPID]
JOIN PA_ResourceSkills rs ON rs.ResourceId = r2.ResourceId
JOIN PA_Skills s ON s.SkillId = rs.SkillId
WHERE s.Name LIKE ? OR r2.PrimarySkill LIKE ? OR r2.SecondarySkill LIKE ?
```

**active_resources → filter by status (IsActive):**
```sql
SELECT * FROM (<prior_sql_stripped>) AS prev
WHERE prev.[EMPID] IN (
  SELECT EmployeeId FROM Resource WHERE IsActive = 1
)
```

**Column availability by intent:**

| Intent | Output columns |
|--------|---------------|
| benched_resources | employeeid, ResourceName, EmailId, TechCategoryName |
| active_resources | EMPID, Name, EmailId, Designation |
| resource_by_skill | EMPID, Name, EmailId, Designation |
| resource_availability | ResourceId, ResourceName, EmailId |
| resource_project_assignments | EMPID, Employee Name, Project Name, Start Date, End Date, Role, Allocation, Billab |
| resource_skills_list | ResourceName, Name (skill), SkillExperience |

### Project domain refinement
**project_resources → filter by name:**
```sql
SELECT * FROM (<prior_sql_stripped>) AS prev
WHERE prev.[Employee Name] LIKE ?
```

### Timesheet domain refinement
**approved_timesheets → filter by date range:**
```sql
SELECT * FROM (<prior_sql_stripped>) AS prev
WHERE prev.[File Date] BETWEEN ? AND ?
```

---

## Follow-Up Detection Patterns

**Primary patterns (deictic references):**
- `which of these`, `which of those`
- `among them`, `among these`, `among those`
- `from them`, `from these`, `from those`
- `of those`, `of these`
- `those who`, `these who`
- `filter by`, `filter them`
- `only those`, `only these`
- `same ones`

**Secondary validation (must also have a filter keyword):**
- `skill`, technology names (Python, Java, etc.)
- `who`, `know`, `with`
- `active`, `inactive`, `billable`, `assigned`, `available`
- `filter`, `only`

**Short question heuristic (< 8 words AND prior context exists):**
- "Who among them use Python?" → 5 words + deictic → refinement
- "Show Python developers" → 3 words BUT no deictic → NOT refinement (fresh query)

**NOT refinements (should go through normal embedding):**
- "Show all Java developers" — explicit new query, no deictic
- "What projects is Alice on?" — specific subject, no reference to prior
- "Who are the active resources?" — new standalone question

---

## TurnContext Schema Design

**Python (Pydantic v2):**
```python
class TurnContext(BaseModel):
    intent: str
    domain: str
    params: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    sql: str = ""
```

**TypeScript:**
```typescript
export interface TurnContext {
  intent: string
  domain: string
  params: Record<string, unknown>
  columns: string[]
  sql: string
}
```

**Backward compatibility:** `last_turn_context: TurnContext | None = None` in `QueryRequest` — existing API calls that don't send it receive `None` in `state["last_turn_context"]`.

**Response inclusion:** Only include `turn_context` in response when the domain tool path ran (when `intent` and `domain` are set). LLM fallback responses should also include it to enable follow-ups on LLM-generated queries.

---

## React State Pattern for lastTurnContext

**Pattern: Lifted state in ChatWidget, passed to ChatPanel as controlled props**

The cleanest approach keeps `lastTurnContext` colocated with `messages` in `ChatWidget` (already lifted there for overlay state):

```tsx
// ChatWidget.tsx — add to lifted state:
const [lastTurnContext, setLastTurnContext] = useState<TurnContext | null>(null)

// Pass to ChatPanel:
<ChatPanel
  ...
  lastTurnContext={lastTurnContext}
  setLastTurnContext={setLastTurnContext}
/>

// ChatPanel.tsx — use in sendMessage:
const mutation = useMutation({
  mutationFn: ({ question, history }: { question: string; history: ConversationTurn[] }) =>
    queryApi.execute({
      connection_id: connectionId,
      question,
      session_id: sessionId,
      conversation_history: history,
      last_turn_context: lastTurnContext ?? undefined,
    }),
  onSuccess: (result) => {
    setLastTurnContext(result.turn_context)
    setMessages((prev) => [...prev, { id: ..., role: 'assistant', result }])
  },
})
```

**StandaloneChatPage.tsx pattern (self-contained):**
```tsx
const [lastTurnContext, setLastTurnContext] = useState<TurnContext | null>(null)

// In mutation onSuccess:
setLastTurnContext(result.turn_context)

// In mutationFn:
queryApi.execute({ ..., last_turn_context: lastTurnContext ?? undefined })
```

**Reset on session change:** `setLastTurnContext(null)` when session_id changes (ChatQueryPage.tsx already resets messages on threadId change — add this alongside).

---

## fallback_intent Mapping

All 29 catalog entries with recommended fallback_intent:

| Intent | fallback_intent | Rationale |
|--------|----------------|-----------|
| active_resources | `None` | Broadest — nothing broader in domain |
| benched_resources | `None` | Specific bench pool — no meaningful broader fallback |
| resource_by_skill | `active_resources` | Skill not found → show all actives |
| resource_availability | `active_resources` | No unassigned → show all actives |
| resource_project_assignments | `active_resources` | Name not found → show all |
| resource_skills_list | `active_resources` | Name not found → show all |
| active_clients | `None` | Broadest client query |
| client_projects | `active_clients` | Client not found → show all clients |
| client_status | `active_clients` | Client not found → show all clients |
| active_projects | `None` | Broadest project query |
| project_by_client | `active_projects` | Client not found → show all projects |
| project_budget | `active_projects` | Project not found → show all |
| project_resources | `active_projects` | Project not found → show all |
| project_timeline | `active_projects` | Project not found → show all |
| overdue_projects | `active_projects` | No overdue → show all actives |
| approved_timesheets | `None` | Broadest timesheet query |
| timesheet_by_period | `approved_timesheets` | No entries in period → show all |
| unapproved_timesheets | `approved_timesheets` | None pending → show all approved |
| timesheet_by_project | `approved_timesheets` | Project not found → show all |
| my_projects | `None` | Broadest user_self query |
| my_allocation | `my_projects` | No allocation data → show projects |
| my_timesheets | `my_projects` | No timesheets → show projects |
| my_skills | `my_projects` | No skills → show projects |
| my_utilization | `my_timesheets` | No utilization → show timesheets |

---

## ChatPanel session_id Solution

**Current state:** ChatPanel.tsx does NOT send session_id. The session_id is tracked in ChatWidget.tsx through the widget's session management — but looking at ChatWidget.tsx, it does NOT auto-create sessions (that's only StandaloneChatPage.tsx).

**The gap:** ChatWidget/ChatPanel (widget mode) doesn't have session management at all.

**Solution:** 
1. Add session creation to ChatWidget.tsx (auto-create on mount via `sessionApi.create()` when a connectionId is available)
2. Store session_id in component state (NOT sessionStorage — widget mode may have multiple instances)
3. Pass session_id down to ChatPanel as a prop
4. ChatPanel uses it in the API call

```tsx
// ChatWidget.tsx
const [sessionId, setSessionId] = useState<string | null>(null)

useEffect(() => {
  if (!connectionId || sessionId) return
  sessionApi.create({ connection_id: connectionId })
    .then(session => setSessionId(session.id))
    .catch(() => {}) // Non-fatal: session_id is optional
}, [connectionId, sessionId])
```

This is minimal — session creation failure doesn't break the widget (session_id is optional in the API).

---

## Implementation Order (Dependencies)

```
Phase 6 dependency graph:

Wave 1 (independent):
  Plan 01: Backend schema + GraphState + query_service (TurnContext foundation)
  Plan 02: fallback_intent wiring in intent_catalog.py (isolated change)

Wave 2 (depends on Plan 01):
  Plan 03: Context-aware classify_intent + extract_params (needs last_turn_context in state)
  
Wave 3 (depends on Plans 01 + 03):
  Plan 04: Domain tool subquery refinement — base_domain.py + resource.py + other agents
  
Wave 4 (depends on Plan 01 for types):
  Plan 05: Frontend — chatbot-frontend types, queryApi, ChatPanel, StandaloneChatPage

Wave 4 can run parallel with Wave 3 if frontend types are defined in Plan 01.
```

---

## Don't Hand-Roll

- **SQL ORDER BY stripping:** Use `re.sub(r'\s+ORDER\s+BY\s+.+$', '', sql, flags=re.IGNORECASE | re.DOTALL)` — don't write a parser
- **Pydantic optional fields:** Use `field_name: Type | None = None` — no custom validators needed
- **TypeScript optional types:** `field?: TurnContext` vs `field: TurnContext | null` — use `| null` for explicit nullability in response types, `?` for request params
- **React state reset:** Use `useEffect` with `sessionId` dependency array to reset `lastTurnContext` when session changes

---

## Common Pitfalls

1. **SQL Server ORDER BY in subqueries:** SQL Server does NOT allow `ORDER BY` in a subquery without `TOP`/`OFFSET`. Always strip `ORDER BY` from `prior_sql` before wrapping. Use `_strip_order_by()` helper.

2. **Column name aliasing:** The benched_resources query outputs `employeeid` (lowercase) but active_resources outputs `EMPID`. When JOINing back to Resource table for skill filtering, use the correct column and appropriate alias.

3. **TypedDict backward compatibility:** When adding `last_turn_context: dict | None` to `GraphState`, also set it to `None` in `initial_state` in `query_service.py`. Any node that returns a dict WITHOUT this field will cause a mypy error — only the service's `initial_state` needs to set it; LangGraph merges node returns with existing state.

4. **Follow-up pattern false positives:** "Show resources from the Alpha project" should NOT match `from them` — the word "from" appears without "them"/"these"/"those". Use word-boundary anchors and require the deictic pronoun, not just "from".

5. **ChatPanel session_id is optional:** The backend accepts `session_id: UUID | None = None`. If session creation fails in the widget, the query still works — just without session persistence.

6. **lastTurnContext reset on new sessions:** When the user starts a new chat (new thread in ChatQueryPage, or tab refresh in StandaloneChatPage), `lastTurnContext` must be reset to `null` to prevent stale context from being applied to the first question in the new session.

7. **turn_context in response when LLM fallback runs:** The `turn_context` field should be populated even when `llm_fallback` runs — this enables follow-ups on LLM-generated queries too. The LLM fallback already sets `state["intent"]` and `state["domain"]` (they may be None if confidence was too low). Only set `turn_context` when intent/domain are non-None.

---

## Validation Architecture

### Backend: Intent classifier follow-up detection

```python
# Tests to write:
def test_is_refinement_followup_detects_deictic():
    assert _is_refinement_followup("Which of these know Python?", {"intent": "benched_resources", ...}) is True

def test_is_refinement_followup_rejects_fresh_query():
    assert _is_refinement_followup("Show all Python developers", {"intent": "benched_resources", ...}) is False

def test_is_refinement_followup_requires_last_turn_context():
    assert _is_refinement_followup("Which of these know Python?", None) is False

def test_classify_intent_followup_inherits_prior():
    # When last_turn_context is set and question has deictic pattern,
    # classify_intent returns domain/intent from context with confidence=0.95
    state = {
        "question": "Which of these know Python?",
        "last_turn_context": {"intent": "benched_resources", "domain": "resource", ...},
        "conversation_history": [],
    }
    result = await classify_intent(state)
    assert result["intent"] == "benched_resources"
    assert result["confidence"] == 0.95
```

### Backend: Param merging

```python
def test_extract_params_inherits_prior_params():
    state = {
        "question": "Who know Python?",
        "params": {},
        "last_turn_context": {"params": {"project_name": "Alpha"}, "sql": "...", "intent": "benched_resources"},
        "intent": "benched_resources",
    }
    result = await extract_params(state)
    assert result["params"]["project_name"] == "Alpha"  # carried forward
    assert result["params"]["skill"] == "Python"         # newly extracted
    assert result["params"]["_refine_mode"] is True

def test_extract_params_new_overwrites_inherited():
    state = {
        "question": "Filter by Java",
        "params": {},
        "last_turn_context": {"params": {"skill": "Python"}, "sql": "...", "intent": "benched_resources"},
        "intent": "benched_resources",
    }
    result = await extract_params(state)
    assert result["params"]["skill"] == "Java"  # new wins over inherited
```

### Backend: Subquery refinement SQL

```python
def test_resource_agent_refinement_wraps_prior_sql():
    # Mock connector, set _refine_mode=True and _prior_sql in params
    # Verify the generated SQL contains "FROM (...) AS prev"
    # Verify ORDER BY is stripped from prior SQL
    ...
```

### Backend: fallback_intent routing

```python
def test_route_after_domain_tool_uses_fallback_intent():
    # Set fallback_intent on resource_by_skill = "active_resources"
    # Run resource_by_skill with unknown skill → 0 rows
    # Verify route_after_domain_tool returns "run_fallback_intent"
    # Verify run_fallback_intent runs active_resources SQL
```

### Frontend: Integration verification

1. Send "Show benched resources" → verify response has `turn_context.intent = "benched_resources"`
2. Send "Which of these know Python?" with `last_turn_context` from step 1 → verify `llm_provider = "domain_tool"` in response (not LLM fallback)
3. Verify ChatPanel sends `session_id` by inspecting network requests
4. Verify `lastTurnContext` resets to null when starting a new chat

### E2E verification (manual)

1. Open chatbot-frontend widget
2. Ask "Show benched resources" → should show results with `domain_tool` badge
3. Click "View full results" to see the data
4. Ask "Which of these know Python?" → should show filtered results, still with `domain_tool` badge (not `LLM generated`)
5. Ask "What are their project assignments?" → this is an intent switch (resource_project_assignments), should go through normal classification but inherit name params if available
6. Verify 0-row results trigger fallback_intent: ask "Show resources with skill XYZ999" → should try active_resources fallback before LLM

---

*Research completed: 2026-03-31*
*Phase: 06-context-aware-domain-tools*
