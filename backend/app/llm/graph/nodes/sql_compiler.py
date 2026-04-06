"""SQL compiler — deterministically compiles QueryPlan + filters into SQL Server SQL.

This module is the core of the QueryPlan compiler pipeline (Phase 7).
It replaces the 1150-line subquery-wrapping refinement_registry.py with a
deterministic single-level SQL compiler that produces clean SQL for all 24
active PRMS intents.

Usage:
    sql, params = compile_query(plan, resource_id=user.resource_id)
    result = await connector.execute_query(sql, params=params, ...)

Feature flag: only reached when settings.use_query_plan_compiler == True.
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.graph.nodes.field_registry import FIELD_REGISTRY, FieldConfig
from app.llm.graph.query_plan import FilterClause, QueryPlan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BASE_QUERIES — all 24 active PRMS intent SQL templates
# ---------------------------------------------------------------------------
# Every template has {select_extras} and {join_extras} named tokens that
# default to empty string. These allow metric fragments to be injected at
# compile time without string surgery.
#
# SQL Server syntax: ? positional params, bracketed column names for spaces.
# Bare table names (no dbo. prefix) — consistent with existing domain agents.
# ---------------------------------------------------------------------------

BASE_QUERIES: dict[str, str] = {

    # ═══════════════════════════════════════════════════════════════════════
    # RESOURCE DOMAIN (6 active intents)
    # ═══════════════════════════════════════════════════════════════════════

    "active_resources": (
        "SELECT r.EmployeeId as [EMPID], r.ResourceName as [Name], r.EmailId, "
        "dr.designationname as [Designation]{select_extras} "
        "FROM Resource r "
        "JOIN Designation dr ON r.designationid = dr.designationid{join_extras} "
        "WHERE r.IsActive = 1 and r.statusid = 8"
    ),

    "benched_resources": (
        "SELECT DISTINCT r.employeeid as [EMPID], r.ResourceName as [Name], r.EmailId, "
        "t.TechCategoryName{select_extras} "
        "FROM Resource r "
        "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
        "JOIN Project p ON pr.ProjectId = p.ProjectId "
        "JOIN TechCatagory t ON t.TechCategoryId = r.TechCategoryId{join_extras} "
        "WHERE p.ProjectId = 119"  # hardcoded bench project; confirmed constant
    ),

    "resource_by_skill": (
        "SELECT distinct r.EmployeeId as [EMPID], r.ResourceName as [Name], r.EmailId, "
        "dr.designationname as [Designation]{select_extras} "
        "FROM Resource r "
        "JOIN Designation dr ON r.designationid = dr.designationid "
        "JOIN TechCatagory tc ON tc.TechCategoryId = r.TechCategoryId "
        "JOIN PA_ResourceSkills par ON par.ResourceId = r.ResourceId "
        "JOIN PA_Skills psk ON psk.SkillId = par.SkillId{join_extras} "
        "WHERE r.IsActive = 1"
    ),

    "resource_availability": (
        "SELECT ResourceId, ResourceName, EmailId{select_extras} "
        "FROM Resource{join_extras} "
        "WHERE IsActive = 1 "
        "AND ResourceId NOT IN (SELECT DISTINCT ResourceId FROM ProjectResource WHERE IsActive = 1)"
    ),

    "resource_project_assignments": (
        "SELECT r.EmployeeId as [EMPID], r.ResourceName as [Employee Name], "
        "p.ProjectName as [Project Name], "
        "CAST(pr.StartDate AS DATE) AS [Start Date], "
        "CAST(pr.EndDate AS DATE) AS [End Date], "
        "pr.resourcerole as [Role], pr.PercentageAllocation as [Allocation], "
        "pr.Billab{select_extras} "
        "FROM Resource r "
        "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
        "JOIN Project p ON pr.ProjectId = p.ProjectId{join_extras}"
    ),

    "resource_skills_list": (
        "SELECT DISTINCT r.ResourceName, s.Name, rs.SkillExperience{select_extras} "
        "FROM Resource r "
        "JOIN PA_ResourceSkills rs ON r.ResourceId = rs.ResourceId "
        "JOIN PA_Skills s ON rs.SkillId = s.SkillId{join_extras}"
    ),

    # Deferred intents — #baadme (not yet production-ready)
    # "resource_utilization": ...,   #baadme
    # "resource_billing_rate": ...,  #baadme
    # "resource_timesheet_summary": ..., #baadme

    # ═══════════════════════════════════════════════════════════════════════
    # CLIENT DOMAIN (3 active intents)
    # ═══════════════════════════════════════════════════════════════════════

    "active_clients": (
        "SELECT distinct c.ClientName, c.Description, c.CountryId{select_extras} "
        "FROM Client c "
        "JOIN Status st ON c.StatusId = st.StatusId AND st.ReferenceId = 1{join_extras} "
        "WHERE st.StatusName = 'Active'"
    ),

    "client_projects": (
        "SELECT c.ClientName, p.ProjectName, p.StartDate, p.EndDate{select_extras} "
        "FROM Client c "
        "JOIN Project p ON c.ClientId = p.ClientId{join_extras}"
    ),

    "client_status": (
        "SELECT c.ClientName, st.StatusName{select_extras} "
        "FROM Client c "
        "JOIN Status st ON c.StatusId = st.StatusId AND st.ReferenceId = 1{join_extras}"
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # PROJECT DOMAIN (6 active intents)
    # ═══════════════════════════════════════════════════════════════════════

    "active_projects": (
        "SELECT p.ProjectId, p.ProjectName, c.ClientName{select_extras} "
        "FROM Project p "
        "JOIN Client c ON p.ClientId = c.ClientId "
        "JOIN Status st ON p.ProjectStatusId = st.StatusId AND st.ReferenceId = 2{join_extras} "
        "WHERE st.StatusName = 'Active'"
    ),

    "project_by_client": (
        "SELECT p.ProjectName as [Project Name], c.clientname as [Client Name], "
        "cast(p.StartDate as date) as [Start date], cast(p.EndDate as date) as [End date], "
        "r.ResourceName as [Project Manager], s.StatusName as Status{select_extras} "
        "FROM Project p "
        "JOIN Client c ON p.ClientId = c.ClientId "
        "JOIN Status s ON s.StatusId = p.ProjectStatusId "
        "JOIN Resource r ON r.ResourceId = p.ProjectManagerId{join_extras}"
    ),

    "project_budget": (
        "SELECT p.ProjectName, p.Budget, p.BudgetUtilized{select_extras} "
        "FROM Project p{join_extras}"
    ),

    "project_resources": (
        "SELECT p.ProjectName, c.ClientId, r.ResourceName, tc.TechCategoryName, "
        "pr.Billable, pr.ResourceRole, pr.PercentageAllocation{select_extras} "
        "FROM Project p "
        "JOIN ProjectResource pr ON p.ProjectId = pr.ProjectId "
        "JOIN Resource r ON pr.ResourceId = r.ResourceId "
        "JOIN TechCategory tc ON tc.TechCategoryId = r.TechCategoryId "
        "JOIN Client c ON c.ClientId = pr.ClientId{join_extras} "
        "WHERE pr.IsActive = 1"
    ),

    "project_timeline": (
        "SELECT ProjectName, "
        "cast(StartDate as Date) as [Start Date], "
        "COALESCE(CONVERT(VARCHAR(10), EndDate, 120), 'NA') AS [End Date], "
        "COALESCE(CAST(DATEDIFF(DAY, StartDate, EndDate) AS VARCHAR(10)), 'NA') AS DurationDays"
        "{select_extras} "
        "FROM Project{join_extras}"
    ),

    "overdue_projects": (
        "SELECT p.ProjectId, p.ProjectName, p.EndDate, c.ClientName{select_extras} "
        "FROM Project p "
        "JOIN Client c ON p.ClientId = c.ClientId "
        "JOIN Status st ON p.ProjectStatusId = st.StatusId AND st.ReferenceId = 2{join_extras} "
        "WHERE p.EndDate < GETDATE() AND st.StatusName != 'Completed'"
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # TIMESHEET DOMAIN (4 active intents)
    # ═══════════════════════════════════════════════════════════════════════

    "approved_timesheets": (
        "SELECT ts.TimesheetId, r.ResourceName, ts.WorkDate, ts.Hours, ts.Description{select_extras} "
        "FROM Timesheet ts "
        "JOIN Resource r ON ts.ResourceId = r.ResourceId{join_extras} "
        "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0"
    ),

    "timesheet_by_period": (
        "SELECT r.ResourceName, ts.WorkDate, ts.Hours, ts.Description{select_extras} "
        "FROM Timesheet ts "
        "JOIN Resource r ON ts.ResourceId = r.ResourceId{join_extras} "
        "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0"
    ),

    "unapproved_timesheets": (
        "SELECT ts.TimesheetId, r.ResourceName, ts.WorkDate, ts.Hours{select_extras} "
        "FROM Timesheet ts "
        "JOIN Resource r ON ts.ResourceId = r.ResourceId{join_extras} "
        "WHERE ts.IsApproved = 0 AND ts.IsDeleted = 0 AND ts.IsRejected = 0"
    ),

    "timesheet_by_project": (
        "SELECT p.ProjectName, r.ResourceName, ts.WorkDate, ts.Hours{select_extras} "
        "FROM Timesheet ts "
        "JOIN Resource r ON ts.ResourceId = r.ResourceId "
        "JOIN Project p ON ts.ProjectId = p.ProjectId{join_extras} "
        "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0"
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # USER SELF DOMAIN (5 active intents — all require resource_id)
    # ═══════════════════════════════════════════════════════════════════════

    "my_projects": (
        "SELECT p.ProjectName, r.ResourceName AS [Employee Name], "
        "COALESCE(CAST(p.StartDate AS DATE), 'NA') AS [Start Date], "
        "COALESCE(CAST(p.EndDate AS DATE), 'NA') AS [End Date]{select_extras} "
        "FROM Project p "
        "JOIN ProjectResource pr ON p.ProjectId = pr.ProjectId "
        "JOIN Resource r ON r.ResourceId = pr.ResourceId{join_extras} "
        "WHERE pr.ResourceId = ? AND r.IsActive = 1"
    ),

    "my_allocation": (
        "SELECT p.ProjectName, pr.PercentageAllocation, pr.StartDate, pr.EndDate{select_extras} "
        "FROM ProjectResource pr "
        "JOIN Project p ON pr.ProjectId = p.ProjectId{join_extras} "
        "WHERE pr.ResourceId = ? AND pr.IsActive = 1"
    ),

    "my_timesheets": (
        "SELECT ts.Title, ts.Category, ts.Activity, ts.[Effort Hours], ts.[File Date]{select_extras} "
        "FROM TS_Timesheet_Report ts "
        "JOIN Resource r ON r.EmployeeId = ts.[Emp ID]{join_extras} "
        "WHERE r.ResourceId = ?"
    ),

    "my_skills": (
        "SELECT s.Name, rs.SkillExperience{select_extras} "
        "FROM PA_ResourceSkills rs "
        "JOIN PA_Skills s ON rs.SkillId = s.SkillId{join_extras} "
        "WHERE rs.ResourceId = ?"
    ),

    "my_utilization": (
        "SELECT ts.Title, SUM(ts.[Effort Hours]) AS TotalHours, ts.[File Date]{select_extras} "
        "FROM TS_Timesheet_Report ts "
        "JOIN Resource r ON r.EmployeeId = ts.[Emp ID]{join_extras} "
        "WHERE r.ResourceId = ? "
        "GROUP BY ts.Title, ts.[File Date]"
    ),
}


# ---------------------------------------------------------------------------
# build_in_clause — safe IN clause builder with SQL Server 2000-item limit
# ---------------------------------------------------------------------------

def build_in_clause(column: str, values: list[str]) -> tuple[str, tuple]:
    """Build a SQL IN clause for the given column and values.

    Args:
        column: The SQL column reference (may include brackets for spaces).
        values: List of parameter values.

    Returns:
        (clause_sql, params_tuple)

    Raises:
        ValueError: If values exceeds 2000 items (SQL Server limit).
    """
    if not values:
        return "1=0", ()
    if len(values) == 1:
        return f"{column}=?", (values[0],)
    if len(values) > 2000:
        raise ValueError(
            f"IN clause exceeds 2000 values ({len(values)} given) — "
            "split into batches or use a temp table"
        )
    placeholders = ", ".join("?" for _ in values)
    return f"{column} IN ({placeholders})", tuple(values)


# ---------------------------------------------------------------------------
# build_filter_clause — single FilterClause → SQL fragment + params
# ---------------------------------------------------------------------------

def build_filter_clause(
    filter_clause: FilterClause,
    field_config: FieldConfig,
) -> tuple[str, tuple]:
    """Compile a single FilterClause to a SQL WHERE fragment and param tuple.

    Type-aware behaviour:
    - text fields: wrap values with %value% for LIKE-based matching
    - date fields: use exact values (BETWEEN / =)
    - numeric fields: use exact values (>= / < / = / BETWEEN)
    - boolean fields: coerce "true"/"false" → 1/0

    Args:
        filter_clause: The FilterClause to compile.
        field_config: The FieldConfig for the field (provides column name, sql_type).

    Returns:
        (fragment_sql, params_tuple) — ready to append to WHERE clause.
    """
    col = field_config.column_name
    sql_type = field_config.sql_type
    op = filter_clause.op
    values = filter_clause.values

    # ── Boolean coercion ──────────────────────────────────────────────────
    if sql_type == "boolean":
        coerced = []
        for v in values:
            if str(v).lower() in ("true", "1", "yes"):
                coerced.append(1)
            else:
                coerced.append(0)
        values = [str(c) for c in coerced]
        # Boolean always uses eq
        return f"{col} = ?", (coerced[0] if len(coerced) == 1 else coerced[0],)

    # ── Text fields: wrap with % for LIKE ─────────────────────────────────
    if sql_type == "text":
        if op == "eq":
            v = values[0] if values else ""
            return f"{col} LIKE ?", (f"%{v}%",)
        if op == "in":
            # For text IN: each value gets its own LIKE (OR chain is safer
            # for text search than IN which requires exact match)
            if not values:
                return "1=0", ()
            like_parts = " OR ".join(f"{col} LIKE ?" for _ in values)
            params = tuple(f"%{v}%" for v in values)
            return f"({like_parts})", params
        if op == "lt":
            return f"{col} < ?", (values[0],)
        if op == "gt":
            return f"{col} >= ?", (values[0],)
        if op == "between":
            return f"{col} BETWEEN ? AND ?", (values[0], values[1])

    # ── Date / Numeric fields: exact values ───────────────────────────────
    if sql_type in ("date", "numeric"):
        if op == "eq":
            return f"{col} = ?", (values[0],)
        if op == "lt":
            return f"{col} < ?", (values[0],)
        if op == "gt":
            return f"{col} >= ?", (values[0],)
        if op == "between":
            return f"{col} BETWEEN ? AND ?", (values[0], values[1])
        if op == "in":
            clause, params = build_in_clause(col, values)
            return clause, params

    # ── Fallback: unknown type or op ──────────────────────────────────────
    logger.warning(
        "build_filter_clause: unhandled sql_type=%r op=%r for field=%r — skipping",
        sql_type, op, filter_clause.field,
    )
    return "1=1", ()  # no-op clause


# ---------------------------------------------------------------------------
# compile_query — main entry point
# ---------------------------------------------------------------------------

def compile_query(
    plan: QueryPlan,
    resource_id: int | None = None,
    select_extras: str = "",
    join_extras: str = "",
    metrics: list[Any] | None = None,
) -> tuple[str, tuple]:
    """Compile a QueryPlan into executable SQL Server SQL with parameters.

    Args:
        plan: The validated QueryPlan (domain, intent, filters).
        resource_id: Required for user_self domain (RBAC guard).
        select_extras: Additional SELECT columns to inject at {select_extras} token.
        join_extras: Additional JOIN clauses to inject at {join_extras} token.
        metrics: Reserved for future metric injection (Phase 7.4+).

    Returns:
        (sql, params_tuple) — ready for connector.execute_query().

    Raises:
        ValueError: If plan.domain == "user_self" and resource_id is None.
        ValueError: If plan.intent is not found in BASE_QUERIES.
    """
    # ── RBAC guard: user_self requires resource_id ─────────────────────────
    if plan.domain == "user_self" and resource_id is None:
        raise ValueError(
            "compile_query: user_self domain requires resource_id — "
            "this should only be reached by authenticated 'user' role accounts."
        )

    # ── Look up base SQL template ──────────────────────────────────────────
    base_sql = BASE_QUERIES.get(plan.intent)
    if base_sql is None:
        raise ValueError(
            f"compile_query: unknown intent '{plan.intent}' — "
            f"not found in BASE_QUERIES. Available: {list(BASE_QUERIES.keys())}"
        )

    # ── Build filter WHERE clauses ─────────────────────────────────────────
    where_fragments: list[str] = []
    filter_params: list[Any] = []

    for f in plan.filters:
        # Look up field config for this field in this domain
        field_config = FIELD_REGISTRY.get(f.field)
        if field_config is None:
            logger.warning(
                "compile_query: field '%s' not found in FIELD_REGISTRY — skipping filter",
                f.field,
            )
            continue

        fragment, params = build_filter_clause(f, field_config)
        if fragment and fragment not in ("1=1",):
            where_fragments.append(fragment)
            filter_params.extend(params)

    # ── Assemble final SQL ─────────────────────────────────────────────────
    # 1. Replace {select_extras} and {join_extras} tokens
    sql = base_sql.replace("{select_extras}", select_extras).replace("{join_extras}", join_extras)

    # 2. For user_self intents: the base SQL already contains "WHERE ... = ?"
    #    with resource_id as the first param. We need to inject resource_id
    #    as the first parameter, then append any filter WHERE conditions.
    if plan.domain == "user_self":
        # Base params: resource_id goes first
        base_params: tuple = (resource_id,)

        # If we have additional filters, we need to append them to the WHERE clause
        if where_fragments:
            # The base SQL ends with "WHERE pr.ResourceId = ?" or similar.
            # We append AND conditions after.
            additional = " AND ".join(where_fragments)
            sql = sql + " AND " + additional

        all_params = base_params + tuple(filter_params)
        logger.debug(
            "compile_query: domain=%s intent=%s filters=%d params=%d",
            plan.domain, plan.intent, len(plan.filters), len(all_params),
        )
        return sql, all_params

    # 3. For other domains: append WHERE filters if any
    if where_fragments:
        additional = " AND ".join(where_fragments)
        # Check if the base SQL already has a WHERE clause
        if " WHERE " in sql.upper() or " WHERE\n" in sql.upper():
            sql = sql + " AND " + additional
        else:
            sql = sql + " WHERE " + additional

    all_params = tuple(filter_params)
    logger.debug(
        "compile_query: domain=%s intent=%s filters=%d params=%d",
        plan.domain, plan.intent, len(plan.filters), len(all_params),
    )
    return sql, all_params
