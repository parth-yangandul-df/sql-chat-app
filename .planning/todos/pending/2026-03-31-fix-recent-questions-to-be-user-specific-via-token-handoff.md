---
created: 2026-03-31T09:20:55.588Z
title: Fix recent questions to be user-specific via token handoff
area: ui
files:
  - chatbot-frontend/src/components/widget/RecentQuestions.tsx:1-50
  - chatbot-frontend/src/main.tsx
  - chatbot-frontend/src/pages/ChatQueryPage.tsx:375-393
  - angular-test/src/app/dashboard.component.ts
---

## Problem

`RecentQuestions.tsx` namespaces `localStorage` by JWT `sub` claim, reading the token from `sessionStorage['qw_auth_token']`. This works correctly inside the Angular-embedded widget (port 4200) because Angular sets `qw_auth_token` in that tab's `sessionStorage` before the widget loads.

However, `sessionStorage` is tab-isolated. When port 5174 is opened in a **new tab** (via the "Open QueryWise Chat" button on the Angular dashboard), the new tab has its own empty `sessionStorage` — so `getUserIdFromToken()` returns `null` and `storageKey()` falls back to the global shared key `qw_recent_questions`, making recent questions the same for all users.

Additionally, `ChatQueryPage.tsx` (port 5174 main SPA) does not call `saveRecentQuestion()` or render `<RecentQuestions>` at all — the welcome screen only shows hardcoded static example questions.

Two distinct issues:
1. Token not available in new tab → user ID not resolved → shared key used → questions are global
2. Port 5174 SPA never saves or displays recent questions at all

## Solution

**Step 1 — Token handoff from Angular to port 5174:**
When Angular's dashboard opens port 5174 in a new tab, append the JWT as a query param:
```ts
window.open(`http://localhost:5174?token=${encodeURIComponent(token)}`, '_blank')
```
In `chatbot-frontend/src/main.tsx`, before mounting React, read `?token=` from `URLSearchParams` and write it to `sessionStorage['qw_auth_token']` so `getUserIdFromToken()` resolves correctly.

**Step 2 — Wire recent questions into ChatQueryPage.tsx:**
- Call `saveRecentQuestion(content.trim())` inside `sendMessage()` in `ChatQueryPage.tsx`
- Render `<RecentQuestions onSelect={sendMessage} />` inside the `WelcomeScreen` component in `ChatQueryPage.tsx`
- Remove or replace the hardcoded IFRS9 static example buttons

Token to read from Angular dashboard component: `sessionStorage.getItem('qw_auth_token')` (already stored there by the Angular login flow).
