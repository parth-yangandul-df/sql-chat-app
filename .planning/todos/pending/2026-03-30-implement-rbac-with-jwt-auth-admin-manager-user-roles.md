---
created: 2026-03-30T09:28:20.302Z
title: Implement RBAC with JWT auth admin manager user roles
area: auth
files:
  - backend/pyproject.toml
  - backend/app/config.py
  - backend/app/db/models/user.py
  - backend/app/db/models/__init__.py
  - backend/alembic/versions/006_rbac.py
  - backend/app/api/deps.py
  - backend/app/api/v1/endpoints/auth.py
  - backend/app/api/v1/router.py
  - backend/app/llm/graph/state.py
  - backend/app/llm/graph/intent_catalog.py
  - backend/app/llm/graph/domains/user_self.py
  - backend/app/llm/graph/domains/registry.py
  - backend/app/llm/graph/nodes/intent_classifier.py
  - backend/app/llm/graph/nodes/llm_fallback.py
  - backend/app/llm/graph/nodes/history_writer.py
  - backend/app/services/query_service.py
  - backend/app/api/v1/endpoints/query.py
  - backend/app/api/v1/endpoints/connections.py
  - docs/rbac-design.md
---

## Problem

QueryWise has zero authentication. Every API endpoint is fully public — no login, no roles, no user identity. The `query_executions.user_id` column exists as `VARCHAR(255)` but is always `NULL`. The frontend widget already has a `sessionStorage['qw_auth_token']` → `Authorization: Bearer` Axios interceptor slot, but no backend to issue tokens.

The agreed design requires 3 global roles:

| Role | Query access | Metadata write | Manage connections | History |
|---|---|---|---|---|
| `admin` | All data, all domains | Yes | CRUD | All users |
| `manager` | All data, all domains | No | Read-only | All users |
| `user` | Own data only via `user_self` domain | No | Read-only | Own only |

The `user` role is scoped to a specific `resource_id` (integer, stored on the `User` model — NOT hardcoded, dynamic per user). This `resource_id` flows through JWT claims → `GraphState` → SQL templates in `UserSelfAgent`.

## Solution

### Phase 1 — Auth foundation
1. Add `PyJWT` + `passlib[bcrypt]` to `backend/pyproject.toml`
2. Add `jwt_secret`, `jwt_algorithm`, `jwt_expiry_seconds` to `backend/app/config.py`
3. Create `backend/app/db/models/user.py` — `User` ORM with `id (UUID)`, `email`, `hashed_password`, `role` (enum: admin/manager/user), `resource_id (int | None)`, `is_active`
4. Create `backend/alembic/versions/006_rbac.py` — creates `users` table, alters `query_executions.user_id` from `VARCHAR(255)` to `UUID FK → users.id` (nullable, existing rows unaffected), seeds 3 dev users (passwords: admin123/manager123/user123, user has resource_id=1)
5. Create `backend/app/api/deps.py` — `get_current_user` (HTTPBearer → JWT decode → User lookup), `require_role(roles)` helper
6. Create `backend/app/api/v1/endpoints/auth.py` — `POST /api/v1/auth/login` returning `{ access_token, token_type, role, resource_id }`
7. Register `auth` router in `backend/app/api/v1/router.py`

### Phase 2 — Query pipeline wiring
8. Add `user_id: str | None`, `user_role: str | None`, `resource_id: int | None` to `GraphState` TypedDict in `backend/app/llm/graph/state.py`
9. Add 5 `user_self` intents to `backend/app/llm/graph/intent_catalog.py`: `my_projects`, `my_allocation`, `my_timesheets`, `my_skills`, `my_utilization`
10. Create `backend/app/llm/graph/domains/user_self.py` — `UserSelfAgent` with SQL templates using `state["resource_id"]` (dynamic, not hardcoded)
11. Register `"user_self"` in `backend/app/llm/graph/domains/registry.py`
12. Modify `intent_classifier.py` — after cosine similarity, if `state["user_role"] == "user"` and best domain != `"user_self"`, return `confidence=0.0` to force `llm_fallback`
13. Modify `llm_fallback.py` — when `state["resource_id"]` is set, prepend scope constraint block to SYSTEM_PROMPT before `QueryComposerAgent.compose()`
14. Modify `history_writer.py` — pass `user_id=state.get("user_id")` when constructing `QueryExecution`
15. Modify `query_service.py` — add `current_user` param to `execute_nl_query`, thread `user_id`, `user_role`, `resource_id` into `GraphState`

### Phase 3 — Endpoint protection
16. `query.py` — all 3 routes get `Depends(get_current_user)`; `execute_query` passes `current_user` to service
17. `connections.py` — writes (POST/PUT/DELETE) require `admin`, GETs require any authenticated user
18. All other endpoints (glossary, metrics, dictionary, knowledge, sessions, query_history) — writes require `admin`, reads require any authenticated user

### Scope constraint (for llm_fallback when resource_id is set)
```
--- USER SCOPE CONSTRAINT (NON-NEGOTIABLE) ---
This query is scoped to a single user with ResourceId = {resource_id}.
You MUST add WHERE ResourceId = {resource_id} (or the equivalent FK column) on every
table in the query that contains a ResourceId column.
Tables known to have ResourceId: Resource, ProjectResource, TS_Timesheet_Report (via EmployeeId join), PA_ResourceSkills.
NEVER return data for other ResourceIds. This constraint overrides all other instructions.
--- END SCOPE CONSTRAINT ---
```

### Key constraints
- No refresh tokens in this phase
- No frontend login page in this phase (widget reads token from sessionStorage set by host app)
- `resource_id` is dynamic — stored on `User` model, included in JWT claims, NOT hardcoded
- Dev seed users go directly in Alembic migration (not a separate script — avoids chicken-and-egg with auth-protected API)
- `docs/rbac-design.md` must be rewritten before coding starts to reflect final 3-role global model (current doc describes older admin/editor/viewer + per-connection roles design)
