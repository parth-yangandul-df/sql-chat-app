# Codebase Concerns

**Analysis Date:** 2026-04-07

## Tech Debt

### Migration Flags Not Removed
- **Issue:** Feature flags in config exist as migration remnants with no cleanup timeline
- **Files:** `app/config.py` (lines 82, 85)
- **Impact:** Features can't be permanently enabled without flag management
- **Fix approach:** After phase validation, remove flags or make them permanent

### Seed Data TODOs
- **Issue:** Placeholder TODOs in seed script that should be domain-specific
- **Files:** `scripts/seed_sqlserver_metadata.py` (lines 491, 773, 892, 1222)
- **Impact:** Dev/seed environment has generic placeholder data
- **Fix approach:** Replace examples with realistic domain-specific terms

### Hardcoded Fallbacks
- **Issue:** Many functions silently return empty collections without clear error signaling
- **Files:** `app/semantic/schema_linker.py`, `app/semantic/glossary_resolver.py`, `app/semantic/context_builder.py`
- **Impact:** Silent failures - upstream code can't distinguish "no results found" from "error occurred"
- **Fix approach:** Either log warnings when returning empty results, or use Optional return types with explicit error states

## Security Considerations

### Missing Required Config for Production
- **Issue:** `jwt_secret` has no default - app fails to start if not set in environment
- **Files:** `app/config.py` (line 35)
- **Impact:** Runtime failure in production if env vars misconfigured
- **Recommendations:** Ensure production deployment includes explicit jwt_secret

### Default Encryption Key
- **Issue:** Dev encryption key hardcoded as default, must be changed in production
- **Files:** `app/config.py` (line 26)
- **Current mitigation:** Fernet encryption for connection strings
- **Recommendations:** Fail startup if dev key detected in non-dev environment

### SQL Injection Prevention
- **Issue:** SQL sanitizer regex-based - could miss novel attack vectors
- **Files:** `app/utils/sql_sanitizer.py`
- **Current mitigation:** Pattern blocklist covers DDL, DML, admin commands, stacked queries
- **Recommendations:** Add additional validation in connector layer, consider parameterized queries only

### JWT Token Expiry
- **Issue:** Tokens expire after 1 hour by default - no refresh token mechanism
- **Files:** `app/api/v1/endpoints/auth.py`
- **Impact:** Users logged out after 1 hour of inactivity
- **Recommendations:** Implement refresh token flow or extend expiry for trusted clients

## Known Bugs

### Schema Cache Staleness
- **Issue:** Schema cache can become stale when target DB changes
- **Files:** `app/db/models/schema_cache.py`, `app/services/schema_service.py`
- **Trigger:** Manual DB schema changes not reflected until explicit re-introspection
- **Workaround:** Manual trigger via API endpoint

### Embedding Dimension Mismatch
- **Issue:** Switching embedding providers (e.g., OpenAI 1536d to Ollama 768d) requires column resize
- **Files:** `app/services/setup_service.py` (lines 81-82)
- **Trigger:** Provider switch in configuration
- **Workaround:** `ensure_embedding_dimensions()` runs at startup, but nulls existing embeddings

### Vector Search Fallback Handling
- **Issue:** Embedding service failures fall back to keyword search but don't indicate fallback in logs
- **Files:** `app/semantic/schema_linker.py`
- **Trigger:** Ollama unavailable or model not pulled
- **Workaround:** Should auto-recover once embedding service available

## Performance Bottlenecks

### Connection Pooling
- **Issue:** No visible connection pooling for target databases
- **Files:** `app/connectors/postgresql/connector.py`, `app/connectors/sqlserver/connector.py`
- **Cause:** Each query creates/closes connection
- **Improvement path:** Implement connection pooling per connector instance

### Background Embedding Generation
- **Issue:** Large embedding regeneration blocks queue
- **Files:** `app/services/embedding_service.py`
- **Cause:** Single background task processes sequentially
- **Improvement path:** Batch processing or parallel workers

### Semantic Resolver Multiple DB Calls
- **Issue:** Schema linker makes multiple sequential database calls
- **Files:** `app/semantic/schema_linker.py` (lines 162-357)
- **Cause:** Separate queries for columns, relationships, sample values
- **Improvement path:** Combine queries or use connection pooling

## Fragile Areas

### SQL Server Connector Lazy Loading
- **Issue:** SQL Server connector uses late imports to avoid ODBC dependency
- **Files:** `app/connectors/sqlserver/connector.py` (line 5)
- **Why fragile:** Missing ODBC driver causes runtime failure, not startup
- **Safe modification:** Test with and without driver present

### Error Handling in Graph Pipeline
- **Issue:** LangGraph pipeline catches exceptions but may lose error context
- **Files:** `app/llm/graph/graph.py`, `app/llm/agents/error_handler.py`
- **Why fragile:** Complex multi-stage pipeline, errors can propagate incorrectly
- **Test coverage:** Ensure error paths tested

### Connection String Encryption
- **Issue:** Fernet key derivation uses SHA-256 of config key
- **Files:** `app/services/connection_service.py` (line 20)
- **Why fragile:** Key derivation is deterministic - could be brute forced if config leaked
- **Safe modification:** Use proper key generation for production keys

## Dependencies at Risk

### Ollama Availability
- **Issue:** No graceful handling if Ollama server is down at startup
- **Files:** `app/llm/providers/ollama_provider.py`
- **Impact:** Backend fails to start without Ollama
- **Migration plan:** Add startup detection, warn but continue with fallback providers

### aioodbc Dependency
- **Issue:** SQL Server requires aioodbc with ODBC driver
- **Files:** `app/connectors/sqlserver/connector.py`
- **Impact:** Windows-specific, driver installation required
- **Migration plan:** Document driver requirements clearly

## Test Coverage Gaps

### Integration Tests
- **Issue:** Tests use mocks for connectors, not hitting real databases
- **Files:** `tests/` (most test files)
- **What's not tested:** Actual PostgreSQL/SQL Server query execution
- **Risk:** Real-world execution differences not caught
- **Priority:** Medium

### Error Paths
- **Issue:** Fewer tests for error handling scenarios
- **Files:** `tests/test_graph_nodes.py`, `tests/test_intent_classifier.py`
- **What's not tested:** Network failures, timeout handling, invalid SQL recovery
- **Risk:** Production errors not gracefully handled
- **Priority:** High

### Frontend Testing
- **Issue:** No visible tests for React frontend code
- **Files:** `frontend/src/`
- **What's not tested:** All frontend logic, API error handling, edge cases
- **Risk:** UI bugs in production
- **Priority:** Medium

## Scaling Limits

### In-Memory Embedding Progress
- **Issue:** Progress tracking in-memory only, lost on restart
- **Files:** `app/services/embedding_progress.py`
- **Current capacity:** Limits to tracking current batch only
- **Scaling path:** Persist progress to database with resume capability

### Max Rows Limitation
- **Issue:** Query results capped at 1000 by default
- **Files:** `app/config.py` (line 41)
- **Current capacity:** 1000 rows per query
- **Limit:** Users can't retrieve larger result sets
- **Scaling path:** Make configurable per-connection or paginated

---

*Concerns audit: 2026-04-07*