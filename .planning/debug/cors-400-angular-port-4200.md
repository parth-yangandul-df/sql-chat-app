---
status: awaiting_human_verify
trigger: "Widget works on port 5173 but CORS preflight OPTIONS returns 400 Bad Request from port 4200"
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:02:00Z
---

## Current Focus

hypothesis: CONFIRMED AND FIXED — cors_origins was missing http://localhost:4200 and http://localhost:4000. Fix applied to .env. Backend restart required to pick up change.
test: python -c "from app.config import settings; print(settings.cors_origins)" → confirmed all 4 origins present
expecting: After backend restart, OPTIONS preflight from port 4200 will return 200 and subsequent POST will succeed
next_action: user verifies in browser after restarting backend

## Symptoms

expected: Query from the Angular page (port 4200) should succeed just like it does on port 5173
actual: OPTIONS /api/v1/query returns HTTP 400 Bad Request from the backend
errors: INFO:     172.20.0.1:36492 - "OPTIONS /api/v1/query HTTP/1.1" 400 Bad Request
reproduction: Open Angular app at localhost:4200, open the QueryWise chat widget, submit any query
started: Port 5173 always worked; port 4200 has never worked

## Eliminated

- hypothesis: The preflight request itself is malformed (bad headers from the widget)
  evidence: The widget's client.ts sends only Content-Type and optionally Authorization — both standard headers. The same widget JS is used from port 5173 (which works), so the request construction is not at fault. The difference is purely the browser's Origin header value.
  timestamp: 2026-03-30T00:01:00Z

- hypothesis: A custom exception handler intercepts OPTIONS before CORS middleware
  evidence: exception_handlers.py only registers handlers for AppError, HTTPException, RequestValidationError, and generic Exception — none intercept OPTIONS. Middleware runs before route handlers and exception handlers in Starlette's stack. The 400 is produced by CORSMiddleware itself for disallowed origins on preflight.
  timestamp: 2026-03-30T00:01:00Z

## Evidence

- timestamp: 2026-03-30T00:00:00Z
  checked: symptom analysis
  found: 400 Bad Request (not 403) on OPTIONS preflight
  implication: 400 suggests the preflight request itself is malformed OR the backend rejects it before CORS middleware runs. 403 would be CORS rejection. This narrows suspects considerably.

- timestamp: 2026-03-30T00:01:00Z
  checked: backend/app/config.py
  found: cors_origins default = ["http://localhost:5173", "http://localhost:5174"]. http://localhost:4200 is NOT in the default list.
  implication: Unless overridden by env var, port 4200 is always rejected.

- timestamp: 2026-03-30T00:01:00Z
  checked: .env file
  found: Line 16 is a COMMENT: "#cors_origins: list[str] = [...]" — not an env var assignment, it's just documentation. CORS_ORIGINS is never actually set in .env.
  implication: The backend uses the hardcoded default from config.py — ["http://localhost:5173", "http://localhost:5174"]. Port 4200 is rejected.

- timestamp: 2026-03-30T00:01:00Z
  checked: backend/app/main.py CORSMiddleware setup
  found: allow_origins=settings.cors_origins — no special handling, no wildcard fallback
  implication: Exactly what's in the list is what's allowed. Port 4200 not in list → 400 on preflight.

- timestamp: 2026-03-30T00:01:00Z
  checked: Starlette CORSMiddleware behavior (known)
  found: When an OPTIONS preflight arrives with an Origin not in allow_origins, Starlette returns HTTP 400 Bad Request (not 403). This matches the observed error exactly.
  implication: This confirms the mechanism. The fix is simply adding http://localhost:4200 to cors_origins.

- timestamp: 2026-03-30T00:01:00Z
  checked: chatbot-frontend/src/api/client.ts
  found: No unusual headers; reads qw_api_url from sessionStorage per request. Standard axios setup.
  implication: Not the cause. Widget behaves identically regardless of which port the parent page is on.

- timestamp: 2026-03-30T00:01:00Z
  checked: angular-test/src/app/app.ts
  found: Sets sessionStorage qw_api_url = 'http://localhost:8000' in ngOnInit. No unusual headers injected.
  implication: Not the cause. The sessionStorage writes are correct.

## Resolution

root_cause: http://localhost:4200 is missing from the backend's CORS allowed origins list. The config.py default includes only ports 5173 and 5174. The .env file had the CORS_ORIGINS line commented out (it was Python-syntax documentation "#cors_origins: list[str] = [...]", not a real env var assignment), so the default was never overridden. Starlette's CORSMiddleware returns HTTP 400 Bad Request when a CORS preflight OPTIONS request arrives from an unlisted origin.
fix: Replaced the commented-out documentation line with a real env var: CORS_ORIGINS=["http://localhost:5173","http://localhost:5174","http://localhost:4200","http://localhost:4000"]. Verified pydantic-settings parses it correctly to all 4 origins.
verification: python -c "from app.config import settings; print(settings.cors_origins)" outputs ['http://localhost:5173', 'http://localhost:5174', 'http://localhost:4200', 'http://localhost:4000']
files_changed:
  - .env
