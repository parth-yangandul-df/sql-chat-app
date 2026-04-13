# Data & Interface Contracts

## Overview

This document covers the database schema (app-db), API endpoint contracts, Pydantic request/response schemas, and the TypeScript types that mirror them in the frontend.

---

## App-DB Schema (PostgreSQL + pgvector)

Database name: `querywise` (from `docker-compose.yml`). All tables use UUID primary keys and `created_at`/`updated_at` timestamps. Vector columns use `VECTOR(settings.embedding_dimension)` — default `1536` for OpenAI, `768` for Ollama `nomic-embed-text`.

### `database_connections`

**Model:** `backend/app/db/models/connection.py` — `DatabaseConnection`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | VARCHAR | Display name |
| `db_type` | VARCHAR | `postgresql`, `bigquery`, `databricks`, `sqlserver` |
| `connection_string` | TEXT | Fernet-encrypted |
| `is_active` | BOOLEAN | Default `true` |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

Relationships (FK): one-to-many with `cached_tables`, `glossary_terms`, `metric_definitions`, `sample_queries`.

### `cached_tables`

**Model:** `backend/app/db/models/schema_cache.py` — `CachedTable`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `connection_id` | UUID FK → `database_connections` | |
| `schema_name` | VARCHAR | DB schema (e.g., `public`, `dbo`) |
| `table_name` | VARCHAR | |
| `description` | TEXT | Optional business description |
| `embedding` | VECTOR | For semantic table search |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `cached_columns`

**Model:** `backend/app/db/models/schema_cache.py` — `CachedColumn`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `table_id` | UUID FK → `cached_tables` | |
| `column_name` | VARCHAR | |
| `data_type` | VARCHAR | Native DB type |
| `is_nullable` | BOOLEAN | |
| `is_primary_key` | BOOLEAN | |
| `is_foreign_key` | BOOLEAN | |
| `referenced_table` | VARCHAR | For FK columns |
| `description` | TEXT | Optional business description |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `cached_relationships`

**Model:** `backend/app/db/models/schema_cache.py` — `CachedRelationship`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `table_id` | UUID FK → `cached_tables` | |
| `from_table` | VARCHAR | |
| `from_column` | VARCHAR | |
| `to_table` | VARCHAR | |
| `to_column` | VARCHAR | |
| `relationship_type` | VARCHAR | e.g., `FOREIGN KEY` |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `dictionary_entries`

**Model:** `backend/app/db/models/schema_cache.py` — `DictionaryEntry`

Maps column values to business-readable labels.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `table_id` | UUID FK → `cached_tables` | |
| `column_name` | VARCHAR | |
| `raw_value` | VARCHAR | Stored DB value |
| `display_label` | VARCHAR | Human-readable label |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `glossary_terms`

**Model:** `backend/app/db/models/glossary.py` — `GlossaryTerm`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `connection_id` | UUID FK → `database_connections` | |
| `term` | VARCHAR | Business term |
| `definition` | TEXT | Business definition |
| `related_tables` | TEXT[] | Table names referenced in definition |
| `embedding` | VECTOR | For semantic glossary lookup |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `metric_definitions`

**Model:** `backend/app/db/models/glossary.py` — `MetricDefinition`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `connection_id` | UUID FK → `database_connections` | |
| `metric_name` | VARCHAR | |
| `description` | TEXT | |
| `sql_expression` | TEXT | SQL fragment expressing the metric |
| `embedding` | VECTOR | For semantic metric lookup |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `sample_queries`

**Model:** `backend/app/db/models/glossary.py` — `SampleQuery`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `connection_id` | UUID FK → `database_connections` | |
| `question` | TEXT | Natural-language question |
| `sql` | TEXT | Known-good SQL answer |
| `embedding` | VECTOR | Embedded from `question` |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `knowledge_documents`

**Model:** `backend/app/db/models/` — `KnowledgeDocument`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `connection_id` | UUID FK → `database_connections` | |
| `title` | VARCHAR | |
| `source_url` | VARCHAR \| NULL | If imported from URL |
| `raw_content` | TEXT | Full original content |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `knowledge_chunks`

**Model:** `backend/app/db/models/` — `KnowledgeChunk`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `document_id` | UUID FK → `knowledge_documents` | |
| `chunk_index` | INTEGER | Order within document |
| `content` | TEXT | Chunk text (≤450 words) |
| `embedding` | VECTOR | For vector search |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

Chunking parameters: 450 words per chunk, 80-word overlap. Auto-detects HTML and strips tags before chunking.

### `chat_sessions`

**Model:** `backend/app/db/models/chat_session.py` — `ChatSession`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `title` | VARCHAR \| NULL | Auto-set from first question |
| `connection_id` | UUID FK → `database_connections` | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `query_executions`

**Model:** `backend/app/db/models/query_history.py` — `QueryExecution`

Full audit trail for every query.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → `chat_sessions` | |
| `connection_id` | UUID FK → `database_connections` | |
| `question` | TEXT | |
| `sql` | TEXT \| NULL | Generated SQL |
| `answer` | TEXT \| NULL | Interpreted answer |
| `rows_returned` | INTEGER \| NULL | |
| `execution_time_ms` | INTEGER \| NULL | |
| `intent` | VARCHAR \| NULL | Matched intent name (template path only) |
| `intent_confidence` | FLOAT \| NULL | |
| `path` | VARCHAR | `template` or `llm` |
| `error` | TEXT \| NULL | Error message if failed |
| `created_at` | TIMESTAMP | |

---

## API Endpoints

Base prefix: `/api/v1`

### Query

| Method | Path | Description |
|---|---|---|
| `POST` | `/query` | Main NL query endpoint |
| `POST` | `/query/execute-sql` | Execute raw SQL (bypasses LLM pipeline) |
| `POST` | `/query/sql-only` | Generate SQL without executing |

#### `POST /query` — Request

**Schema:** `backend/app/api/v1/schemas/query.py` — `QueryRequest`

```json
{
  "question": "string (required)",
  "connection_id": "UUID (required)",
  "session_id": "UUID | null",
  "history": [
    {"role": "user|assistant", "content": "string"}
  ]
}
```

`history` max length: **6 turns** (enforced at schema level).

#### `POST /query` — Response

**Schema:** `QueryResponse`

```json
{
  "answer": "string | null",
  "sql": "string | null",
  "rows": [{"column": "value"}],
  "columns": ["col1", "col2"],
  "rows_returned": 0,
  "execution_time_ms": 0,
  "session_id": "UUID",
  "query_id": "UUID",
  "intent": "string | null",
  "intent_confidence": 0.0,
  "path": "template | llm",
  "error": "string | null"
}
```

#### `POST /query/execute-sql` — Request

```json
{
  "sql": "string (required)",
  "connection_id": "UUID (required)"
}
```

#### `POST /query/sql-only` — Request

Same as `QueryRequest`. Response omits `rows` and `answer`; only returns `sql`.

---

### Sessions

| Method | Path | Description |
|---|---|---|
| `GET` | `/sessions` | List all sessions |
| `POST` | `/sessions` | Create a new session |
| `DELETE` | `/sessions/{id}` | Delete a session and its history |
| `GET` | `/sessions/{id}/messages` | Get full message history for a session |

#### Session Object

```json
{
  "id": "UUID",
  "title": "string | null",
  "connection_id": "UUID",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

#### Message Object

```json
{
  "id": "UUID",
  "session_id": "UUID",
  "question": "string",
  "answer": "string | null",
  "sql": "string | null",
  "rows_returned": 0,
  "execution_time_ms": 0,
  "path": "template | llm",
  "error": "string | null",
  "created_at": "datetime"
}
```

---

### Connections

| Method | Path | Description |
|---|---|---|
| `GET` | `/connections` | List all connections |
| `POST` | `/connections` | Create a connection |
| `GET` | `/connections/{id}` | Get connection details |
| `PUT` | `/connections/{id}` | Update a connection |
| `DELETE` | `/connections/{id}` | Delete a connection |
| `POST` | `/connections/{id}/test` | Test connection liveness |

#### Connection Create/Update Request

```json
{
  "name": "string",
  "db_type": "postgresql | bigquery | databricks | sqlserver",
  "connection_string": "string (plaintext — encrypted at rest)"
}
```

**Note:** Connection strings are encrypted with Fernet before storage. The key is derived from `ENCRYPTION_KEY` env var using SHA-256.

---

### Schema

| Method | Path | Description |
|---|---|---|
| `POST` | `/schemas/{connection_id}/introspect` | Trigger schema introspection |
| `GET` | `/schemas/{connection_id}/tables` | List cached tables |
| `GET` | `/schemas/{connection_id}/tables/{table_id}/columns` | List columns for a table |

---

### Glossary

| Method | Path | Description |
|---|---|---|
| `GET` | `/glossary` | List all terms (optionally filter by `connection_id`) |
| `POST` | `/glossary` | Create a term |
| `PUT` | `/glossary/{id}` | Update a term |
| `DELETE` | `/glossary/{id}` | Delete a term |

#### Glossary Term Object

```json
{
  "id": "UUID",
  "connection_id": "UUID",
  "term": "string",
  "definition": "string",
  "related_tables": ["table1", "table2"]
}
```

---

### Metrics

| Method | Path | Description |
|---|---|---|
| `GET` | `/metrics` | List all metrics |
| `POST` | `/metrics` | Create a metric |
| `PUT` | `/metrics/{id}` | Update a metric |
| `DELETE` | `/metrics/{id}` | Delete a metric |

#### Metric Object

```json
{
  "id": "UUID",
  "connection_id": "UUID",
  "metric_name": "string",
  "description": "string",
  "sql_expression": "string"
}
```

---

### Dictionary

| Method | Path | Description |
|---|---|---|
| `GET` | `/dictionary` | List entries (filter by `connection_id`, `table`, `column`) |
| `POST` | `/dictionary` | Create an entry |
| `PUT` | `/dictionary/{id}` | Update an entry |
| `DELETE` | `/dictionary/{id}` | Delete an entry |

---

### Knowledge

| Method | Path | Description |
|---|---|---|
| `GET` | `/knowledge` | List knowledge documents |
| `POST` | `/knowledge` | Import a document (text, HTML, or URL) |
| `DELETE` | `/knowledge/{id}` | Delete a document and its chunks |

#### Knowledge Import Request

```json
{
  "connection_id": "UUID",
  "title": "string",
  "content": "string | null",
  "source_url": "string | null"
}
```

If `source_url` is provided and `content` is null, the backend fetches the URL server-side via `httpx`.

---

### Query History

| Method | Path | Description |
|---|---|---|
| `GET` | `/query-history` | List query execution records (filter by `connection_id`, `session_id`) |
| `GET` | `/query-history/{id}` | Get a single execution record |

---

### Embeddings

| Method | Path | Description |
|---|---|---|
| `GET` | `/embeddings/status` | Get background embedding job progress |

#### Embedding Status Response

```json
{
  "total": 100,
  "completed": 72,
  "in_progress": true,
  "percent": 72.0
}
```

---

### Sample Queries

| Method | Path | Description |
|---|---|---|
| `GET` | `/sample-queries` | List sample queries |
| `POST` | `/sample-queries` | Create a sample query |
| `PUT` | `/sample-queries/{id}` | Update a sample query |
| `DELETE` | `/sample-queries/{id}` | Delete a sample query |

---

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check — returns `{"status": "ok"}` |

---

## Error Shape

All API errors normalize to:

```json
{
  "error": "human-readable error message"
}
```

HTTP status codes follow standard conventions (400 for validation, 404 for not found, 500 for server errors). Defined in `backend/app/core/exceptions.py` and `backend/app/core/exception_handlers.py`.

---

## Frontend TypeScript Types

**Location:** `frontend/src/types/`

TypeScript interfaces mirror the backend Pydantic schemas. Key interfaces:

| Interface | Mirrors |
|---|---|
| `QueryRequest` | `QueryRequest` |
| `QueryResponse` | `QueryResponse` |
| `Session` | `ChatSession` |
| `Message` | `QueryExecution` (message view) |
| `Connection` | `DatabaseConnection` |
| `GlossaryTerm` | `GlossaryTerm` |
| `MetricDefinition` | `MetricDefinition` |
| `DictionaryEntry` | `DictionaryEntry` |
| `KnowledgeDocument` | `KnowledgeDocument` |
| `SampleQuery` | `SampleQuery` |

All API calls go through Axios clients in `frontend/src/api/` (one file per resource). Data fetching uses React Query hooks in `frontend/src/hooks/`.
