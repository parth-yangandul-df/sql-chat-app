---
created: 2026-03-30T06:43:51.378Z
title: Build QueryWise chat widget for Angular embedding
area: ui
files:
  - chatbot-frontend/package.json
  - chatbot-frontend/src/api/client.ts
  - chatbot-frontend/src/components/widget/RecentQuestions.tsx
  - chatbot-frontend/src/components/widget/ResultsModal.tsx
  - chatbot-frontend/src/components/widget/ChatPanel.tsx
  - chatbot-frontend/src/components/widget/ChatWidget.tsx
  - chatbot-frontend/src/widget.tsx
  - chatbot-frontend/vite.widget.config.ts
---

## Problem

The QueryWise React app needs to be embeddable in an Angular 21 dashboard as a floating chat widget. The Angular team needs a drop-in `<querywise-chat>` custom element they can load via a `<script>` tag with zero React knowledge required.

Key constraints decided in conversation:
- Single database — `connection-id` is a fixed UUID per environment, passed as HTML attribute
- JWT auth — Angular writes `sessionStorage('qw_auth_token')` after login; widget reads it on every API call via axios request interceptor
- API URL — Angular writes `sessionStorage('qw_api_url')` on app init; widget reads it on every API call
- No DB sessions — `session_id: undefined`, widget is ephemeral per browser tab (chat persists across panel open/close, gone on tab close)
- Recent questions stored in `localStorage('qw_recent_questions')`, max 3, deduped, shown as chips on empty state

## Solution

### Architecture decisions (finalised)

- **No r2wc** — manual Web Component class (~40 lines), avoids React 19 compatibility risk
- **No extra dependencies** — zero new packages
- **IIFE build** via second Vite config (`vite.widget.config.ts`) — single `querywise-chat.js`, CSS inlined via `cssCodeSplit: false`, output to `dist-widget/`
- **Panel always mounted** (never unmounts) — toggled via CSS (`hidden`/`flex`) so chat state survives open/close within tab session
- **Table view** — panel expands to centered full-screen overlay (not a new tab, not inline in chat). CSS fade+scale transition on mount. `ResultsModal.tsx` is a separate file.
- **Styling** — QueryWise's current Tailwind styling for now; theming deferred (Angular dashboard UI framework unknown)

### Files to create/modify

**Modify:**
1. `chatbot-frontend/package.json` — add `"build:widget": "vite build --config vite.widget.config.ts"` to scripts (no new deps)
2. `chatbot-frontend/src/api/client.ts` — add request interceptor: reads `qw_api_url` and `qw_auth_token` from sessionStorage on every request

**Create:**
3. `chatbot-frontend/src/components/widget/RecentQuestions.tsx` — localStorage chips, exported `saveRecentQuestion()` helper
4. `chatbot-frontend/src/components/widget/ResultsModal.tsx` — full-screen centered overlay, `position: fixed; inset: 0; z-index: 99999`, SpotlightTable, CSS fade+scale transition, header shows question + row count + X close
5. `chatbot-frontend/src/components/widget/ChatPanel.tsx` — adapted from `ChatQueryPage.tsx` (475 lines). Remove: useParams, useOutletContext, useSessionMessages, session_id, invalidateQueries, NoThreadSelected, SqlBlock, suggested followups, row count/time, inline SpotlightTable, hardcoded example chips. Add: `overlayResult` state, "View full results" button in AssistantMessage, RecentQuestions on welcome state, saveRecentQuestion on submit, X close button in top bar.
6. `chatbot-frontend/src/components/widget/ChatWidget.tsx` — floating bot button (fixed bottom-right), panel always mounted toggled by CSS, props: `{ connectionId: string }`
7. `chatbot-frontend/src/widget.tsx` — manual Web Component class, `observedAttributes: ['connection-id']`, wraps ChatWidget in QueryClientProvider, `customElements.define('querywise-chat', QueryWiseChat)`
8. `chatbot-frontend/vite.widget.config.ts` — IIFE format, entry: `src/widget.tsx`, `cssCodeSplit: false`, outDir: `dist-widget/`

### Angular team integration contract

```ts
// After login / token refresh
sessionStorage.setItem('qw_auth_token', jwt)
// App init (once)
sessionStorage.setItem('qw_api_url', environment.queryWiseApiUrl)
```
```ts
schemas: [CUSTOM_ELEMENTS_SCHEMA]
```
```html
<script src="https://your-host/querywise-chat.js"></script>
<querywise-chat connection-id="your-connection-uuid"></querywise-chat>
```

### What is NOT touched
- `ChatQueryPage.tsx`, `ChatLayout.tsx`, `App.tsx`, all existing pages/routes/hooks — untouched
- Backend — untouched
- Existing app build — untouched

### Deferred
- Widget theming / CSS custom properties — deferred until Angular dashboard UI framework is known
- Auth attribute exposure — sessionStorage approach chosen (no token in DOM)
