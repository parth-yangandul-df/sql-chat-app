---
created: 2026-03-31T10:26:49.167Z
title: Build standalone dedicated chatbot page for Angular redirect
area: ui
files:
  - chatbot-frontend/src/main.tsx
  - chatbot-frontend/src/App.tsx
  - chatbot-frontend/src/pages/StandaloneChatPage.tsx
  - chatbot-frontend/src/api/client.ts
  - chatbot-frontend/src/components/widget/RecentQuestions.tsx
  - chatbot-frontend/src/components/ui/multimodal-ai-chat-input.tsx
  - angular-test/src/app/dashboard.component.ts
---

## Problem

The chatbot-frontend SPA at port 5174 currently uses a full `ChatLayout` sidebar (threads, connections, history navigation). When Angular opens this in a new tab via `window.open('http://localhost:5174?token=<jwt>', '_blank')`, the page:

- Has no connection_id (reads stale UUID from localStorage → 401/500 on `POST /sessions`)
- Shows no chat input box or recent questions on load
- Has sidebar tabs for Connections, History, New Chat that don't work without valid localStorage state
- Receives 401s because the token timing isn't reliable before the thread auto-create fires

The user wants the dedicated page to be clean — just the chat UI, no sidebar, no thread management, no navigation — and have the same auth as the Angular dashboard login.

Key decisions made in conversation:
- **No sidebar, no thread list, no connections page, no history page** — just the chat input + conversation
- **Auth**: `?token=<jwt>` URL param → `sessionStorage['qw_auth_token']` (already works in `main.tsx`)
- **Connection**: Angular passes `?connection_id=<uuid>` alongside token → stored in `sessionStorage['qw_connection_id']`
- **Session persistence**: `sessionStorage['qw_session_id']` — if present on tab refresh, restore that session; if absent (new tab open), auto-create a new session
- **Widget untouched**: `ChatWidget.tsx`, `ChatPanel.tsx`, `widget.tsx`, `vite.widget.config.ts` must not change

Each user gets a **different token** (JWT is per-user), but the **same `connection_id`** (DB connections are shared, not per-user). Angular selects the connection from its own connection picker and passes it.

## Solution

### 4 surgical changes

**1. `angular-test/src/app/dashboard.component.ts`**
Change `openQueryWiseChat()` to pass both token and connection_id:
```ts
window.open(
  `http://localhost:5174?token=${encodeURIComponent(token)}&connection_id=${encodeURIComponent(this.connectionId)}`,
  '_blank'
)
```

**2. `chatbot-frontend/src/main.tsx`**
Alongside existing `?token=` extraction, also read `?connection_id=`:
```ts
const connectionIdParam = params.get('connection_id')
if (connectionIdParam) sessionStorage.setItem('qw_connection_id', connectionIdParam)
```

**3. `chatbot-frontend/src/App.tsx`**
Replace all routes with a single catch-all pointing to `StandaloneChatPage`:
```tsx
import { StandaloneChatPage } from '@/pages/StandaloneChatPage'
export default function App() {
  return (
    <Routes>
      <Route path="*" element={<StandaloneChatPage />} />
    </Routes>
  )
}
```

**4. `chatbot-frontend/src/pages/StandaloneChatPage.tsx`** *(new file)*
Self-contained page — no `ChatLayoutContext`, no outlet, no sidebar. Logic:
- Reads `qw_connection_id` from `sessionStorage` for all API calls
- Reads `qw_session_id` from `sessionStorage`; if present → restore existing session (load history with `useSessionMessages`); if absent → call `sessionApi.create({ connection_id })` once via `useRef` guard → store result in `sessionStorage['qw_session_id']`
- Renders a minimal top bar (Bot icon + "QueryWise" text, no navigation)
- Renders full chat UI: `WelcomeScreen` with `RecentQuestions`, message list, `PureMultimodalInput`
- On session create failure (e.g. bad connection_id): show error state with explanation

### What is NOT touched
- `ChatWidget.tsx`, `ChatPanel.tsx`, `widget.tsx`, `vite.widget.config.ts`
- `ChatLayout.tsx`, `ConnectionsPage.tsx`, `HistoryPage.tsx` (dead files in SPA but safe to keep)
- All backend code
