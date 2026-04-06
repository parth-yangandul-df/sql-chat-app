# Dockerize All Services with Optimization

- **Area:** tooling
- **Created:** 2026-04-06T08:02:21.688Z
- **Status:** pending

## Problem

No `.dockerignore` files exist in any service directory, causing bloated build contexts (node_modules, .venv, __pycache__, dist, etc. all copied). Backend installs unused `bigquery` and `databricks` extras. `chatbot-widget` (port 4000) and `angular-test` (port 4200) must be started manually — they are not in docker-compose. `angular-test` has no Dockerfile at all.

## Solution

1. Create `.dockerignore` for `frontend/`, `chatbot-frontend/`, `backend/`, `angular-test/`
2. Edit `backend/Dockerfile` line 17: remove `bigquery,databricks` from pip install extras
3. Create `angular-test/Dockerfile` (node:20-slim, npm ci, npx @angular/cli@21 serve)
4. Add `chatbot-widget` service to docker-compose.yml (port 4000, `npx serve dist-widget --cors -p 4000`)
5. Add `angular-test` service to docker-compose.yml (port 4200, `npx @angular/cli@21 serve --port 4200 --host 0.0.0.0`)
6. Do NOT replace or modify any existing docker-compose services

## Files

- `frontend/Dockerfile`
- `chatbot-frontend/Dockerfile`
- `chatbot-frontend/vite.config.ts`
- `angular-test/package.json`
- `angular-test/angular.json`
- `backend/Dockerfile:17`
- `docker-compose.yml`

## Tasks

- [ ] Create `frontend/.dockerignore`
- [ ] Create `chatbot-frontend/.dockerignore`
- [ ] Create `backend/.dockerignore`
- [ ] Create `angular-test/.dockerignore`
- [ ] Edit `backend/Dockerfile` — remove `bigquery,databricks` from pip install extras
- [ ] Create `angular-test/Dockerfile` (node:20-slim base)
- [ ] Add `chatbot-widget` service to `docker-compose.yml` (port 4000)
- [ ] Add `angular-test` service to `docker-compose.yml` (port 4200)
