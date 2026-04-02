---
created: 2026-03-30T07:19:26.352Z
title: Scaffold Angular 21 test app with widget integration
area: general
files:
  - angular-test/src/app/app.component.ts
  - angular-test/src/index.html
  - chatbot-frontend/dist-widget/querywise-chat.js
---

## Problem

Need a plain Angular 21 app to test the QueryWise chat widget integration end-to-end. No Angular app exists in the repo — it needs to be scaffolded from scratch. The widget bundle (`chatbot-frontend/dist-widget/querywise-chat.js`) is already built and ready.

The Angular test app should:
- Be at `angular-test/` at the repo root (alongside `chatbot-frontend/` and `backend/`)
- Have nothing on the page except a minimal header and the `<querywise-chat>` custom element
- Use `CUSTOM_ELEMENTS_SCHEMA` in the standalone component
- Set `sessionStorage('qw_api_url')` and `sessionStorage('qw_auth_token')` on `ngOnInit`
- Load the widget via `<script src="http://localhost:4000/querywise-chat.js">` in `index.html`
- Pass the real `connection-id` UUID as an attribute (fetched from `GET /api/v1/connections` when backend is running)

## Solution

### Step 1: Scaffold

```bash
# From repo root (not inside chatbot-frontend)
npx @angular/cli@21 new angular-test \
  --routing=false \
  --style=css \
  --skip-tests \
  --standalone \
  --skip-git
```

Angular CLI 21 is available via npx (confirmed: v21.2.2, Node v24.14.0).

### Step 2: Modify `angular-test/src/index.html`

Add before `</body>`:
```html
<script src="http://localhost:4000/querywise-chat.js"></script>
```

### Step 3: Replace `angular-test/src/app/app.component.ts`

```ts
import { Component, OnInit, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core'

@Component({
  selector: 'app-root',
  standalone: true,
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  template: `
    <div class="dashboard">
      <h1>Dashboard</h1>
      <querywise-chat connection-id="{{ connectionId }}"></querywise-chat>
    </div>
  `,
  styles: [`
    .dashboard { font-family: sans-serif; padding: 32px; background: #f8fafc; min-height: 100vh; }
    h1 { color: #1e293b; font-size: 1.5rem; margin: 0; }
  `]
})
export class AppComponent implements OnInit {
  connectionId = 'REPLACE-WITH-REAL-UUID'

  ngOnInit() {
    sessionStorage.setItem('qw_api_url', 'http://localhost:8000')
    sessionStorage.setItem('qw_auth_token', '')
  }
}
```

### Step 4: Get real connection UUID

```bash
curl http://localhost:8000/api/v1/connections
```

Replace `REPLACE-WITH-REAL-UUID` with the actual UUID from the response.

### Step 5: Serve both

```bash
# Terminal 1 — widget bundle
cd chatbot-frontend && npx serve dist-widget --cors -p 4000

# Terminal 2 — Angular
cd angular-test && npx @angular/cli@21 serve --port 4200
```

Open http://localhost:4200 — empty page, widget bottom-right.

### Blocked on

Backend (`docker compose up`) must be running to fetch the real connection UUID.
