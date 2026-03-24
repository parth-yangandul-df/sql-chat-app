---
created: 2026-03-23T13:57:12.905Z
title: Improve SQL Server retrieval and seeded semantic context
area: api
files:
  - backend/app/semantic/relevance_scorer.py:1
  - backend/app/semantic/schema_linker.py:1
  - backend/app/semantic/context_builder.py:1
  - backend/app/semantic/prompt_assembler.py:1
  - backend/app/semantic/glossary_resolver.py:1
  - backend/app/connectors/sqlserver/connector.py:141
  - backend/app/services/schema_service.py:14
  - backend/app/services/query_service.py:20
  - backend/scripts/seed_sqlserver_metadata.py:1
---

## Problem

Natural-language SQL generation against the SQL Server connection is inconsistent even when schema caching and embeddings are present and working. Explicit schema-aware prompts such as `show ClientName and StatusId from Client` work, but semantically equivalent natural-language prompts such as `show all clients with their status` can select the wrong tables or invent the wrong join path.

Observed issues during the session:
- The system sometimes claims required tables are missing even though `Client`, `Project`, `Resource`, and `Status` are present in cached schema metadata.
- The generated SQL for client status used the wrong join: `Client.ClientId = Status.ReferenceId` instead of using `Client.StatusId`.
- The natural-language query `show all clients with their status` returned incorrect SQL while the explicit query `show ClientName and StatusId from Client` worked, confirming that table/column metadata exists and the main weakness is retrieval plus join inference.
- Reporting-manager queries depend on a Resource self-join, and the confirmed intended relationship is `Resource.ReportingTo -> Resource.ResourceId`.
- SQL Server schemas often have sparse or missing enforced foreign keys, so relying only on declared relationships is not enough.
- SQL Server foreign key introspection has already been added to the connector, but the live database still exposes only a small number of cached relationships and does not provide the key `Client -> Status` relationship as an enforced FK.
- Seeded semantic metadata exists, but it is not yet strong enough to guide retrieval and join selection for common business questions.

This is primarily a retrieval and relationship-inference problem, not a cache storage problem and not mainly an embeddings-generation problem.

## Solution

### Retrieval improvements
- Add column-aware scoring to semantic retrieval so tables are boosted not only by table-name similarity but also by high-signal columns such as `ClientName`, `StatusId`, `StatusName`, `ProjectStatusId`, `ResourceName`, and `ReportingTo`.
- Improve `schema_linker` candidate generation to merge embedding hits, table-name keyword hits, column-name hits, glossary-referenced tables, and relationship-based candidates before final trimming.
- Increase or adapt `max_context_tables` for SQL Server-sized schemas so the top-N cutoff does not exclude obvious anchor tables.
- Force-include anchor tables for strong signals such as `client`, `project`, `resource`, `status`, `manager`, and `reporting`.

### Relationship inference
- Add a relationship inference layer for SQL Server when hard foreign keys are missing or incomplete.
- Support inferred joins such as:
  - `Client.StatusId -> Status.StatusId`
  - `Project.ProjectStatusId -> Status.StatusId`
  - `Project.ClientId -> Client.ClientId`
  - `Resource.ReportingTo -> Resource.ResourceId`
- Prefer these inferred joins over weak alternatives such as `Client.ClientId -> Status.ReferenceId`.
- Distinguish declared relationships from inferred relationships in prompt assembly so the LLM receives structured join hints instead of guessing.

### Context assembly and prompt guidance
- Update context assembly to actually pull in glossary-referenced tables and inferred lookup tables.
- Add explicit inferred-relationship guidance to the assembled prompt, especially for `Status` lookups and `Resource` self-joins.
- Prefer returning raw IDs over inventing unsafe joins when no confident label lookup is available.

### Seed metadata improvements
- Expand `seed_sqlserver_metadata.py` so seeded glossary, dictionary, knowledge, and sample-query content actively reinforces the intended business semantics.
- Reflect the confirmed join rules in seeded metadata so the LLM receives the same guidance from business context that retrieval and inference use internally.
- Add or strengthen glossary entries for:
  - `Client Status`
  - `Project Status`
  - `Resource Status`
  - `Reporting Manager`
  - `Direct Reports`
  - `Client Name`
  - `Resource Name`
- Add knowledge guidance that explicitly states:
  - client status comes from `Client.StatusId` via `Status`
  - project status comes from `Project.ProjectStatusId` via `Status`
  - do not confuse `IsActive` with lifecycle status
  - reporting-manager queries require a self-join on `Resource` using `ReportingTo -> ResourceId`
  - prefer `Client.ClientName` over `Project_Details_PRMS.DFINT_ClientName` for entity-level client questions
- Add dictionary/value-mapping guidance for status interpretation, including when `Status.ReferenceId` differentiates status domains versus when joins should use `StatusId` on entity tables.
- Add validated sample queries for real ask patterns such as:
  - `show all clients with their status`
  - `show all employees reporting to Ashutosh Pandey`
  - `list projects with client names`
  - `show active clients`

### Confirmed implementation constraints
- Treat retrieval as the primary bottleneck, with relationship inference as the secondary bottleneck.
- Do not spend effort on cache storage or embedding generation changes first; those are not the main source of the observed response errors.
- Use SQL Server-specific logic first before attempting broader connector-wide generalization.

### Observability and tests
- Log selected tables, match reasons, inferred joins, and whether vector search or keyword-only fallback was used.
- Add regression tests for the SQL Server semantic retrieval path so natural-language prompts select the expected tables and joins.
