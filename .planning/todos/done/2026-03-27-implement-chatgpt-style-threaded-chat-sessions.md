---
created: 2026-03-27T08:46:18.763Z
title: Implement ChatGPT-style threaded chat sessions
area: general
files:
  - backend/app/db/models/chat_session.py
  - backend/app/db/models/query_history.py
  - backend/app/db/models/__init__.py
  - backend/alembic/versions/005_add_chat_sessions.py
  - backend/app/api/v1/schemas/session.py
  - backend/app/api/v1/schemas/query.py
  - backend/app/api/v1/endpoints/sessions.py
  - backend/app/api/v1/router.py
  - backend/app/llm/graph/state.py
  - backend/app/services/query_service.py
  - backend/app/llm/graph/nodes/history_writer.py
  - backend/app/llm/graph/nodes/llm_fallback.py
  - backend/app/llm/agents/query_composer.py
  - chatbot-frontend/src/types/api.ts
  - chatbot-frontend/src/api/sessionApi.ts
  - chatbot-frontend/src/api/queryApi.ts
  - chatbot-frontend/src/hooks/useThreads.ts
  - chatbot-frontend/src/App.tsx
  - chatbot-frontend/src/components/layout/ChatLayout.tsx
  - chatbot-frontend/src/pages/ChatQueryPage.tsx
  - chatbot-frontend/src/pages/HistoryPage.tsx
---

## Problem

`chatbot-frontend` has no session/thread concept — all chat history is in-memory and lost on refresh. The backend `POST /api/v1/query` is fully stateless (no `session_id`, no `conversation_history`). There is no way to have context-aware follow-up questions or return to a previous conversation.

## Solution

Full-stack implementation of ChatGPT-style threading across 21 files in backend and chatbot-frontend.

### Backend (13 changes)
1. New `ChatSession` ORM model (`id`, `connection_id`, `title`, `created_at`, `updated_at`)
2. Add nullable `session_id` FK column to `QueryExecution`
3. Register `ChatSession` in `db/models/__init__.py`
4. Alembic migration `005_add_chat_sessions.py` (new table + new column)
5. New Pydantic schemas in `schemas/session.py` (`SessionCreate`, `SessionResponse`, `SessionMessageResponse`)
6. Add `ConversationTurn` model + `session_id`/`conversation_history` fields to `QueryRequest`
7. New sessions endpoints: `POST /sessions`, `GET /sessions`, `GET /sessions/{id}/messages`, `DELETE /sessions/{id}`
8. Register sessions router in `router.py`
9. Add `session_id: str | None` and `conversation_history: list[dict]` to `GraphState`
10. Update `execute_nl_query()` to accept + thread `session_id` and `conversation_history`; auto-set session title from first question
11. Update `write_history` node to write `session_id` on `QueryExecution`
12. Update `llm_fallback` node to inject `conversation_history` into composer call
13. Update `QueryComposerAgent.compose()` to accept optional `conversation_history` param and prepend prior turns

### Frontend (8 changes)
14. Add `ChatSession`, `ChatSessionMessage` types to `api.ts`
15. New `sessionApi.ts` (`create`, `list`, `messages`, `delete`)
16. Update `queryApi.ts` execute payload (add `session_id`, `conversation_history`)
17. New `useThreads.ts` React Query hook (`GET /sessions?connection_id=`)
18. Add `/query/:threadId` route in `App.tsx`; `/query` redirects to most recent or creates new
19. Redesign `ChatLayout.tsx` sidebar: thread list with "+ New Chat" button, session titles, timestamps, delete on hover
20. Rewrite `ChatQueryPage.tsx`: reads `threadId` from params, loads history on mount, sends last 6 messages as conversation context (`CONVERSATION_HISTORY_TURNS = 3`)
21. Rewrite `HistoryPage.tsx`: sessions list view (title, connection, message count, last activity), clicking opens `/query/:threadId`

### Key constraints
- Backend DB persistence (PostgreSQL) — not localStorage
- Context window: last 3 turns (6 messages) — `CONVERSATION_HISTORY_TURNS = 3` constant
- Conversation history only injected in `llm_fallback` path (domain tool path unchanged)
- Changes only in `chatbot-frontend/` and `backend/` — `frontend/` (Mantine) is NOT touched
