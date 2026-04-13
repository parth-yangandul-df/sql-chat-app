---
name: docker-debug
description: "Debug Docker container startup issues for QueryWise. Handles: containers not responding, port binding failures, memory allocation errors, volume mount conflicts, build failures. Use for: docker compose issues, container crashes, port not accessible, memory errors, build errors, Dockerfile troubleshooting"
---

# Docker Debugging Skill for QueryWise

This skill diagnoses and fixes common Docker container issues in the QueryWise project.

## Common Issues & Solutions

### 1. "Cannot allocate memory" Error

**Symptoms:** 
- Backend crashes during alembic migration or uvicorn startup
- Error in watchfiles Rust watcher
- OSError: [Errno 12] Cannot allocate memory

**Root Cause:** 
- Uvicorn --reload flag on Windows Docker causes file watcher memory exhaustion
- Volume mounts causing excessive file system monitoring

**Solution:**
```yaml
# In docker-compose.yml - remove --reload
command: bash -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
# NOT: ... --reload
```

### 2. Frontend ESM Module Resolution Errors

**Symptoms:**
- ✘ [ERROR] Could not resolve "./cjs/react.development.js"
- ✘ [ERROR] Could not resolve "./lib/axios.js"
- Cannot read directory ".": cannot allocate memory

**Root Cause:**
- Volume mounts overwriting container's node_modules (Windows paths corrupt Linux binaries)
- The `./frontend:/app` mount replaces container's node_modules

**Solution - Option A (Recommended):** Remove volume mounts entirely
```yaml
# docker-compose.yml - remove all volumes from frontend services
frontend:
  volumes: []  # No mounts - rebuild on code changes
chatbot-frontend:
  volumes: []
```

**Solution - Option B:** Selective mounts (less reliable on Windows)
```yaml
volumes:
  - ./frontend/src:/app/src
  - ./frontend/public:/app/public
  # DON'T mount node_modules
```

### 3. Ports Not Responding After Build Success

**Symptoms:**
- Build completes successfully
- Containers show "running" in docker compose ps
- But localhost:5173, 5174, 8000 don't respond

**Diagnosis Steps:**
```bash
# 1. Check container status
docker compose ps -a

# 2. Check port binding
docker inspect querywise-frontend-1 --format '{{json .NetworkSettings.Ports }}'

# 3. Check logs for errors
docker compose logs --tail=100

# 4. Test from inside container
docker exec querywise-frontend-1 curl localhost:5173
```

**Common Fixes:**
- Restart Docker Desktop completely
- Run: `docker compose down && docker compose up --build -d`
- Clear Docker network: `docker network prune`

### 4. Database Connection Issues

**Symptoms:**
- Backend can't connect to app-db
- DATABASE_URL connection failures

**Check:**
```bash
# Verify database is healthy
docker compose ps app-db

# Check DATABASE_URL in container
docker compose exec backend env | grep DATABASE
```

**Fix in docker-compose.yml:**
```yaml
backend:
  environment:
    DATABASE_URL: "postgresql+asyncpg://parthy:querywise_app@app-db:5432/saras_metadata"
```

### 5. Volume Mount Path Issues

**Symptoms:**
- alembic: OSError: [Errno 12] Cannot allocate memory: '/app/app'
- Import failures during container startup

**Solution:** Remove ALL volume mounts from backend
```yaml
backend:
  volumes: []
```

## Quick Debug Workflow

### Step 1: Check Container Status
```bash
docker compose ps -a
```

### Step 2: Check Logs
```bash
docker compose logs --tail=50
```

### Step 3: Full Restart (Most Common Fix)
```bash
docker compose down
docker compose up --build -d
```

### Step 4: Verify Ports
```bash
# Check what's listening
netstat -ano | findstr "5173 5174 8000"

# Or test with curl
curl http://localhost:8000/docs
```

## Docker Compose for QueryWise

### Working Configuration (Production-Style)

```yaml
services:
  app-db:
    image: pgvector/pgvector:pg16
    # ...健康检查和端口

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql+asyncpg://parthy:querywise_app@app-db:5432/saras_metadata"
      PYTHONPATH: /app
    depends_on:
      app-db:
        condition: service_healthy
    volumes: []  # NO MOUNTS - rebuild on code changes
    command: bash -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000
    volumes: []  # NO MOUNTS
    command: npm run dev -- --host

  chatbot-frontend:
    build: ./chatbot-frontend
    ports:
      - "5174:5174"
    environment:
      VITE_API_URL: http://localhost:8000
    volumes: []  # NO MOUNTS
    command: npm run dev -- --host

volumes:
  app_db_data:  # Only preserve database volume
```

### For Code Changes

```bash
# Rebuild and restart all services
docker compose down && docker compose up --build

# Or in detached mode
docker compose up --build -d
```

### Common Commands

| Action | Command |
|--------|---------|
| Start all | `docker compose up --build -d` |
| Stop all | `docker compose down` |
| View logs | `docker compose logs -f` |
| View status | `docker compose ps -a` |
| Rebuild one | `docker compose up --build -d frontend` |
| Access container | `docker compose exec backend bash` |

## When to Use This Skill

Trigger this skill when:
- "Cannot allocate memory" error occurs
- Ports not responding after successful build
- Container crashes during startup
- ESM module resolution errors in frontend
- Volume mount issues on Windows
- Any docker compose related problems

## Known Windows Docker Issues

1. **File watching exhaustion** - Don't use --reload on Windows
2. **Volume mount corruption** - Don't mount node_modules from Windows
3. **Network driver issues** - May need Docker Desktop restart
4. **Memory limits** - Increase Docker Desktop memory to 4GB+

## Prevention

For production-style development (recommended):
- No volume mounts (volumes: [])
- No hot reload (no --reload flag)
- Rebuild on code changes: `docker compose up --build`

This avoids all Windows+Docker compatibility issues.
