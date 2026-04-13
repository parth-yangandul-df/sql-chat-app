# Phase 07: QueryPlan Compiler — Research

**Researched:** 2026-04-02
**Researcher:** Orchestrator (inline codebase audit)

## 1. Complete Intent Inventory (24 Active)

### Resource Domain (6 intents)
| Intent | Description | Key Columns | Param Keys |
|--------|-------------|-------------|------------|
| `active_resources` | Active resource list | EMPID, Name, EmailId, Designation | skill, resource_name, designation |
| `benched_resources` | Benched resources (ProjectId=119) | EMPID, Name, EmailId, TechCategoryName | skill, resource_name, tech_category |
| `resource_by_skill` | Filter by skill | EMPID, Name, EmailId, Designation | skill, designation |
| `resource_availability` | Unallocated resources | ResourceId, ResourceName, EmailId | resource_name, skill |
| `resource_project_assignments` | Project assignments | EMPID, Employee Name, Project Name, Start Date, End Date, Role, Allocation, Billab | resource_name, start_date, end_date, role, billable, min_allocation |
| `resource_skills_list` | Skills per resource | ResourceName, Name, SkillExperience | skill_name, min_experience |

### Client Domain (3 intents)
| Intent | Description | Key Columns | Param Keys |
|--------|-------------|-------------|------------|
| `active_clients` | Active client list | ClientName, CountryId | client_name, country_id |
| `client_projects` | Projects per client | StartDate, ProjectName | start_date, end_date, project_name |
| `client_status` | Client status | StatusName | status |

### Project Domain (6 intents)
| Intent | Description | Key Columns | Param Keys |
|--------|-------------|-------------|------------|
| `active_projects` | Active project list | ClientName, ProjectName | client_name, project_name |
| `project_by_client` | Projects by client | Status, Project Manager, Start date | status, project_manager, start_date, end_date |
| `project_budget` | Budget info | Budget, BudgetUtilized | min_budget, min_utilization |
| `project_resources` | Resources on project | Billable, ResourceRole, TechCategoryName, PercentageAllocation, ResourceName, ClientId | billable, role, tech_category, min_allocation, resource_name, client_id |
| `project_timeline` | Project dates | Start Date, DurationDays | start_date, end_date, min_duration |
| `overdue_projects` | Past-due projects | ClientName, EndDate | client_name, days_overdue |

### Timesheet Domain (4 intents)
| Intent | Description | Key Columns | Param Keys |
|--------|-------------|-------------|------------|
| `approved_timesheets` | Approved entries | ResourceName, WorkDate, Hours, Description | resource_name, start_date, end_date, min_hours, description |
| `timesheet_by_period` | Period-based hours | ResourceName, Hours | resource_name, min_hours |
| `unapproved_timesheets` | Pending entries | ResourceName, WorkDate | resource_name, start_date, end_date |
| `timesheet_by_project` | Project timesheets | ResourceName, WorkDate, Hours | resource_name, start_date, end_date, min_hours |

### User Self Domain (5 intents)
| Intent | Description | Key Columns | Param Keys |
|--------|-------------|-------------|------------|
| `my_projects` | My projects | Start Date, End Date | start_date, end_date |
| `my_allocation` | My allocation % | StartDate, EndDate, PercentageAllocation, ProjectName | start_date, end_date, min_allocation, project_name |
| `my_timesheets` | My timesheets | File Date, Category, Effort Hours | start_date, end_date, category, min_hours |
| `my_skills` | My skills | Name, SkillExperience | skill_name, min_experience |
| `my_utilization` | My utilization | File Date, TotalHours, Title | start_date, end_date, min_hours, category |

## 2. Field Registry Inventory (from refinement_registry.py mining)

All filterable columns across all domain-intent pairs:

### Resource Domain Fields
| Field | Column | Multi-Value | SQL Type | Aliases |
|-------|--------|-------------|----------|---------|
| `skill` | (JOIN-based) | Yes | text | — |
| `resource_name` | Name | No | text | — |
| `designation` | Designation | No | text | — |
| `tech_category` | TechCategoryName | No | text | — |
| `role` | Role | No | text | — |
| `start_date` | Start Date | No | date | — |
| `end_date` | End Date | No | date | — |
| `billable` | Billab | No | boolean | — |
| `min_allocation` | Allocation | No | numeric | — |
| `skill_name` | Name | No | text | — |
| `min_experience` | SkillExperience | No | numeric | — |

### Client Domain Fields
| Field | Column | Multi-Value | SQL Type | Aliases |
|-------|--------|-------------|----------|---------|
| `client_name` | ClientName | No | text | `resource_name` (project/timesheet fallback) |
| `country_id` | CountryId | No | text | — |
| `start_date` | StartDate | No | date | — |
| `end_date` | EndDate | No | date | — |
| `project_name` | ProjectName | No | text | `resource_name` (project/timesheet fallback) |
| `status` | StatusName | No | text | — |

### Project Domain Fields
| Field | Column | Multi-Value | SQL Type | Aliases |
|-------|--------|-------------|----------|---------|
| `client_name` | ClientName | No | text | — |
| `project_name` | ProjectName | No | text | — |
| `status` | Status | No | text | — |
| `project_manager` | Project Manager | No | text | — |
| `start_date` | Start date | No | date | — |
| `end_date` | End date | No | date | — |
| `min_budget` | Budget | No | numeric | — |
| `min_utilization` | BudgetUtilized | No | numeric | — |
| `billable` | Billable | No | boolean | — |
| `role` | ResourceRole | No | text | — |
| `tech_category` | TechCategoryName | No | text | — |
| `min_allocation` | PercentageAllocation | No | numeric | — |
| `resource_name` | ResourceName | No | text | — |
| `client_id` | ClientId | No | text | — |
| `min_duration` | DurationDays | No | numeric | — |
| `days_overdue` | EndDate (computed) | No | numeric | — |

### Timesheet Domain Fields
| Field | Column | Multi-Value | SQL Type | Aliases |
|-------|--------|-------------|----------|---------|
| `resource_name` | ResourceName | No | text | — |
| `start_date` | WorkDate | No | date | — |
| `end_date` | WorkDate | No | date | — |
| `min_hours` | Hours | No | numeric | — |
| `description` | Description | No | text | — |

### User Self Domain Fields
| Field | Column | Multi-Value | SQL Type | Aliases |
|-------|--------|-------------|----------|---------|
| `start_date` | Start Date / StartDate / File Date | No | date | — |
| `end_date` | End Date / EndDate / File Date | No | date | — |
| `min_allocation` | PercentageAllocation | No | numeric | — |
| `project_name` | ProjectName | No | text | — |
| `category` | Category / Title | No | text | — |
| `min_hours` | Effort Hours / TotalHours | No | numeric | — |
| `skill_name` | Name | No | text | — |
| `min_experience` | SkillExperience | No | numeric | — |

## 3. Existing Regex Patterns (param_extractor.py)

| Pattern | Regex | Captures |
|---------|-------|----------|
| Skill (keyword) | `\b(?:with skills?\s+(?:in\s+)?|skilled in|who knows?|expertise in|work(?:ing)? on|using|proficient in|experience (?:with|in))\s*([A-Za-z0-9#+.\-]+)` | skill name |
| Skill (tech-word) | `\b([A-Z][A-Za-z0-9#+.\-]*)\s+(?:developers?|engineers?)\b` | tech before role |
| Date | `\b(\d{4}-\d{2}-\d{2})\b` | ISO dates |
| Resource name | `\b(?:for|by|assigned to|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)` | proper nouns |
| Project name | `\b(?:on project|for project|project named?|project called|about project)\s+([A-Za-z0-9][A-Za-z0-9\-\s]+?)(?:\s*[?]?\s*$)` | project names |
| Client name | `\b(?:for client|by client|client named?|client called)\s+([A-Za-z0-9][A-Za-z0-9\-\s]+?)(?:\s*[?]?\s*$)` | client names |

Additional patterns needed for filter_extractor.py:
- Designation: `(?i)\b(?:as|role|position|designation)\s+(?:a\s+)?([A-Z][A-Za-z\s]+)` 
- Status/billable: `\b(billable|non-billable|pending|approved)\b`
- Numeric thresholds: `\b(?:more than|at least|minimum|over|above|>=?)\s*(\d+)`

## 4. Graph Wiring Analysis

Current graph topology (`graph.py`):
```
classify_intent
  ├─ confidence >= threshold → extract_params → run_domain_tool
  │                              ├─ rows > 0 → interpret_result
  │                              └─ 0 rows + fallback? → run_fallback_intent
  │                                                          ├─ rows > 0 → interpret_result
  │                                                          └─ 0 rows → llm_fallback
  └─ confidence < threshold → llm_fallback
                                      │
                                interpret_result → write_history → END
```

New topology for Phase 7:
```
classify_intent
  ├─ confidence >= threshold → extract_filters → update_query_plan → run_domain_tool
  │                                                ├─ rows > 0 → interpret_result
  │                                                └─ 0 rows + fallback? → run_fallback_intent
  │                                                            ├─ rows > 0 → interpret_result
  │                                                            └─ 0 rows → llm_fallback
  └─ confidence < threshold → llm_fallback
                                      │
                                interpret_result → write_history → END
```

Key changes:
1. `extract_params` → `extract_filters` (new node, returns `list[FilterClause]`)
2. `update_query_plan` (new node, accumulates into `query_plan` dict)
3. `run_domain_tool` reads `query_plan` instead of `params` for filter construction

Node signatures follow existing pattern: `async def node(state: GraphState) -> dict[str, Any]`

## 5. Test Infrastructure

- pytest with `asyncio_mode="auto"`
- `conftest.py`: `mock_db`, `mock_query_result`, `mock_embed_text` fixtures
- `_base_state(**overrides)` helper in `test_graph_nodes.py` — returns full GraphState dict
- Test files: `test_graph_nodes.py`, `test_subquery_refinement.py`, `test_domain_agents.py`, `test_context_aware_param_extractor.py`, `test_graph_pipeline.py`, `test_intent_catalog.py`, `test_turn_context_schema.py`
- Mocking pattern: `unittest.mock.AsyncMock`, `MagicMock`, `patch`
- Connector mocking: `get_or_create_connector` returns mock with `execute_query` AsyncMock

## 6. Semantic Layer Integration Points

### Glossary (Phase 4)
- `app/semantic/context_builder.py` — `build_context()` returns `prompt_context`
- Glossary terms stored in DB with embeddings
- For Phase 7: glossary terms need to be resolved BEFORE filter extraction to provide available-field hints

### Dictionary value_map
- Dictionary entries stored in DB with `value_map` JSON field
- Maps user-friendly values to DB values (e.g. "backend" → "Backend Developer")
- For Phase 7: load at startup, apply during filter value normalization

### Metrics
- Metric definitions stored in DB
- For Phase 4: `MetricFragment(select_expr, join_clause, requires_group_by)`
- For Phase 7: detect metric names in question, inject into `compile_query(plan, metrics=[...])`

## 7. SQL Template Patterns

All 24 intents use SQL Server syntax:
- `?` positional parameters (pyodbc/aioodbc)
- Bracketed column names for spaces: `[Start Date]`, `[Project Manager]`
- `LIKE ?` with `%value%` wrapping for text filters
- `BETWEEN ? AND ?` for date ranges
- `>= ?` for numeric thresholds
- `= ?` for booleans
- Subquery wrapping pattern: `SELECT prev.* FROM ({prior_sql}) AS prev WHERE ...`

Three intents are commented out (deferred):
- `resource_utilization` — `#baadme`
- `resource_billing_rate` — `#baadme`
- `resource_timesheet_summary` — `#baadme`

## Validation Architecture

### Test File Structure
```
backend/tests/
├── test_query_plan_model.py          # QueryPlan + FilterClause Pydantic tests
├── test_field_registry.py            # FieldRegistry completeness + validation
├── test_filter_extractor.py          # Regex + LLM fallback extraction
├── test_plan_updater.py              # Filter accumulation rules
├── test_sql_compiler.py              # SQL template compilation
├── test_queryplan_integration.py     # 5 regression flow end-to-end tests
├── test_semantic_wiring.py           # Glossary/dict/metric integration
└── test_retirement.py                # Verify old modules not imported
```

### Regression Test Flows (5 critical)
1. **Resource chain**: "active resources" → "with Python skill" → "named John"
   - Old: 2-level subquery nesting
   - New: single compiled SQL with WHERE + JOIN
2. **Project filter chain**: "active projects" → "for client Acme" → "budget > 100000"
   - Old: 2-level subquery nesting
   - New: single compiled SQL with WHERE clauses
3. **Timesheet date chain**: "approved timesheets" → "between 2024-01-01 and 2024-06-30" → "more than 8 hours"
   - Old: 2-level subquery nesting
   - New: single compiled SQL with BETWEEN + >=
4. **Topic switch recovery**: "active resources" → "show active projects" (clears plan)
   - Old: context carry-forward
   - New: fresh QueryPlan on domain switch
5. **LLM fallback → domain tool**: "complex question" (LLM) → "active resources" (domain)
   - Old: params carry
   - New: query_plan=None on LLM turn, fresh plan on domain turn

### Unit Test Cases
- `QueryPlan.from_untrusted_dict()` — rejects unknown keys, validates ops
- `FilterClause` — rejects invalid ops, sanitizes values
- `FieldRegistry.validate_registry_completeness()` — raises StartupIntegrityError on missing fields
- `build_in_clause()` — empty→`1=0`, single→`field=?`, >2000→ValueError
- `compile_query()` — RBAC guard (user_self + None resource_id → ValueError)
- `extract_filters()` — regex matches, LLM fallback, unknown field dropping
- `update_query_plan()` — multi-value append, date last-wins, boolean last-wins

### Edge Cases
- Empty filter list → base SQL unchanged
- Single value IN clause → collapses to `field=?`
- Date range with only start or only end → handled gracefully
- Special characters in filter values (SQL injection guard)
- Concurrent turns (asyncio.Lock for any shared state)
- Feature flag off → zero behavioral change (existing path unchanged)

---

*Phase: 07-queryplan-compiler*
*Researched: 2026-04-02 via inline codebase audit*