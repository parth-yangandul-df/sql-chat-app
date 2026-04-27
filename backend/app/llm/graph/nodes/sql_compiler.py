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
from dataclasses import dataclass
from typing import Any

from app.llm.graph.nodes.field_registry import DOMAIN_STATUS_IDS, FIELD_REGISTRY, FieldConfig
from app.llm.graph.query_plan import FilterClause, QueryPlan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NO_FILTER_INTENTS — intents with fully self-contained SQL (no dynamic filters)
# ---------------------------------------------------------------------------
NO_FILTER_INTENTS: frozenset[str] = frozenset({
    "benched_resources",      # hardcoded WHERE p.ProjectId = 119
    "benched_by_skill",       # skill handled via {skill_filter} token; ProjectId=119 hardcoded
    "active_resources",       # hardcoded WHERE r.IsActive = 1 AND r.statusid = 8
    "resource_availability",   # hardcoded subquery exclusion
    "resource_by_skill",       # status filter maps to c.IsActive alias; not valid in this query
    "active_projects",        # hardcoded WHERE p.IsActive = 1 AND p.ProjectStatusId = 4
    "overdue_projects",       # hardcoded WHERE p.EndDate < GETDATE()
    "active_clients",         # hardcoded WHERE c.IsActive = 1 AND c.StatusId = 2
    "approved_timesheets",    # hardcoded approval flags
    "unapproved_timesheets",  # hardcoded unapproved flags
    "my_utilization",         # self-contained SQL; EmployeeId param (string)
    "reports_to",             # manager name baked into WHERE via param; no extra filters
})

# Intents that use EmployeeId (string) instead of ResourceId (integer PK)
_EMPLOYEE_ID_INTENTS: frozenset[str] = frozenset({"my_timesheets", "my_utilization"})


# ---------------------------------------------------------------------------
# MetricFragment — injectable metric SQL for SELECT / JOIN / GROUP BY
# ---------------------------------------------------------------------------

@dataclass
class MetricFragment:
    """A metric SQL fragment for injection into compile_query().

    Carries the three SQL elements needed to inject an aggregation metric:
    - select_expr: Additional SELECT expression (e.g. "SUM(Hours) AS total_hours")
    - join_clause: Additional JOIN clause (e.g. "JOIN Timesheets ON ...")
    - requires_group_by: Whether to inject a GROUP BY clause for non-aggregated columns
    """
    select_expr: str       # e.g. "SUM(Hours) AS total_hours"
    join_clause: str       # e.g. "JOIN Timesheets ON resources.id = timesheets.resource_id"
    requires_group_by: bool


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
    # RESOURCE DOMAIN (7 active intents)
    # ═══════════════════════════════════════════════════════════════════════

    "active_resources": (
        "SELECT r.EmployeeId as [EMPID], r.ResourceName as [Name], r.EmailId, "
        "dr.designationname as [Designation]{select_extras} "
        "FROM Resource r "
        "JOIN Designation dr ON r.designationid = dr.designationid{join_extras} "
        "WHERE r.IsActive = 1 AND r.statusid = 8 "
        "ORDER BY r.ResourceName ASC"
    ),

    "benched_resources": (
        "SELECT DISTINCT r.employeeid as [EMPID], r.ResourceName as [Name], r.EmailId, "
        "t.TechCategoryName{select_extras} "
        "FROM Resource r "
        "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
        "JOIN Project p ON pr.ProjectId = p.ProjectId "
        "JOIN TechCatagory t ON t.TechCategoryId = r.TechCategoryId{join_extras} "
        "WHERE p.ProjectId = 119 "
        "AND r.isactive = 1 and r.statusid = 8 "  # hardcoded bench project; confirmed constant
        "ORDER BY r.ResourceName"
    ),

    "benched_by_skill": (
        "SELECT DISTINCT r.employeeid as [EMPID], r.ResourceName as [Name], r.EmailId, "
        "t.TechCategoryName as [Tech Category]{select_extras} "
        "FROM Resource r "
        "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
        "JOIN Project p ON pr.ProjectId = p.ProjectId "
        "JOIN TechCatagory t ON t.TechCategoryId = r.TechCategoryId "
        "JOIN PA_ResourceSkills rs ON rs.ResourceId = r.ResourceId "
        "JOIN PA_Skills s ON s.SkillId = rs.SkillId{join_extras} "
        "WHERE p.ProjectId = 119 "
        "AND r.isactive = 1 and r.statusid = 8 "  # same bench project filter
        "AND ({skill_filter}) "
        "ORDER BY r.ResourceName"
    ),

    "resource_by_skill": (
        "SELECT distinct r.EmployeeId as [EMPID], r.ResourceName as [Name], r.EmailId, "
        "dr.designationname as [Designation]{select_extras} "
        "FROM Resource r "
        "JOIN Designation dr ON r.designationid = dr.designationid "
        "JOIN TechCatagory tc ON tc.TechCategoryId = r.TechCategoryId "
        "JOIN PA_ResourceSkills par ON par.ResourceId = r.ResourceId "
        "JOIN PA_Skills psk ON psk.SkillId = par.SkillId{join_extras} "
        "WHERE r.IsActive = 1 AND r.statusid = 8 AND ({skill_filter})"
    ),

    "resource_availability": (
        "SELECT ResourceId, ResourceName, EmailId{select_extras} "
        "FROM Resource{join_extras} "
        "WHERE IsActive = 1 and statusid != 7 "
        "AND ResourceId NOT IN (SELECT DISTINCT ResourceId FROM ProjectResource WHERE IsActive = 1)"
    ),

    "resource_project_assignments": (
        "SELECT r.EmployeeId as [EMPID], r.ResourceName as [Employee Name], "
        "p.ProjectName as [Project Name], "
        "CAST(pr.StartDate AS DATE) AS [Start Date], "
        "CAST(pr.EndDate AS DATE) AS [End Date], "
        "pr.resourcerole as [Role], pr.PercentageAllocation as [Allocation], "
        "pr.Billable{select_extras} "
        "FROM Resource r "
        "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
        "JOIN Project p ON pr.ProjectId = p.ProjectId{join_extras}"
    ),

    "resource_skills_list": (
        "SELECT DISTINCT r.ResourceName, s.Name, rs.SkillExperience{select_extras} "
        "FROM Resource r "
        "JOIN PA_ResourceSkills rs ON r.ResourceId = rs.ResourceId "
        "JOIN PA_Skills s ON rs.SkillId = s.SkillId{join_extras} "
        "WHERE r.IsActive = 1 AND r.statusid != 7"
    ),

    "reports_to": (
        "SELECT r.EmployeeId, r.ResourceName, pm.ResourceName as [Reporting To]{select_extras} "
        "FROM Resource r "
        "JOIN Resource pm ON pm.ResourceId = r.ReportingTo{join_extras} "
        "WHERE pm.ResourceName LIKE ? AND r.IsActive = 1 AND r.statusid != 7"
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
        "WHERE c.IsActive = 1"
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
        "JOIN TechCatagory tc ON tc.TechCategoryId = r.TechCategoryId "
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

    "project_status": (
        "SELECT p.ProjectName as [Project Name], c.ClientName as [Client], "
        "s.StatusName as [Status], "
        "cast(p.StartDate as date) as [Start Date], "
        "COALESCE(CONVERT(VARCHAR(10), p.EndDate, 120), 'NA') AS [End Date], "
        "r.ResourceName as [Project Manager]{select_extras} "
        "FROM Project p "
        "JOIN Client c ON p.ClientId = c.ClientId "
        "JOIN Status s ON s.StatusId = p.ProjectStatusId "
        "JOIN Resource r ON r.ResourceId = p.ProjectManagerId{join_extras}"
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
        "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
        "ORDER BY ts.WorkDate DESC"
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
        "WHERE ts.IsApproved = 0 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
        "ORDER BY ts.WorkDate DESC"
    ),

    "timesheet_by_project": (
        "SELECT p.ProjectName, r.ResourceName, ts.WorkDate, ts.Hours{select_extras} "
        "FROM Timesheet ts "
        "JOIN Resource r ON ts.ResourceId = r.ResourceId "
        "JOIN Project p ON ts.ProjectId = p.ProjectId{join_extras} "
        "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
        "ORDER BY ts.WorkDate DESC"
    ),

    # ═══════════════════════════════════════════════════════════════════════
    # USER SELF DOMAIN (5 active intents — all require resource_id)
    # ═══════════════════════════════════════════════════════════════════════

    "my_projects": (
        "SELECT p.ProjectName, r.ResourceName AS [Employee Name], "
        "COALESCE(CONVERT(VARCHAR(10), p.StartDate, 120), 'NA') AS [Start Date], "
        "COALESCE(CONVERT(VARCHAR(10), p.EndDate, 120), 'NA') AS [End Date]{select_extras} "
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
        "WHERE r.EmployeeId = ? "
        "ORDER BY ts.[File Date] DESC"
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
        "WHERE r.EmployeeId = ? "
        "GROUP BY ts.Title, ts.[File Date] "
        "ORDER BY ts.[File Date] DESC"
    ),
}

# ---------------------------------------------------------------------------
# detect_metrics — keyword-based metric detection stub
# ---------------------------------------------------------------------------

def detect_metrics(
    question: str,
    available_metrics: list[dict],
) -> list[MetricFragment]:
    """Keyword-matching metric detection stub.

    Full LLM-based detection is deferred to a future phase.
    Currently returns empty list — structure ready for future implementation.

    Args:
        question: The user's natural language question.
        available_metrics: List of metric definition dicts from the DB.

    Returns:
        List of MetricFragment objects matching detected metrics. Currently always [].
    """
    # Stub — full implementation deferred to future phase (LLM-based detection)
    logger.debug("detect_metrics: keyword stub called — LLM detection deferred")
    return []


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
    domain: str = "",
) -> tuple[str, tuple]:
    """Compile a single FilterClause to a SQL WHERE fragment and param tuple.

    Type-aware behaviour:
    - text fields: wrap values with %value% for LIKE-based matching
    - date fields: use exact values (BETWEEN / =)
    - numeric fields: use exact values (>= / < / = / BETWEEN)
    - boolean fields: coerce "true"/"false" → 1/0
    - NULL checks: "missing", "incomplete", "null" → IS NULL / IS NOT NULL

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

    # ── Skip empty filters ──────────────────────────────────────────────────
    if not values or all(not str(v).strip() for v in values):
        return "", ()  # Skip empty filters entirely
    
    # ── Handle NULL checks for special values ────────────────────────────────
    # Check if the value indicates a NULL check (missing, incomplete, null, empty)
    NULL_INDICATORS = frozenset({"missing", "incomplete", "null", "empty", "blank", "undefined"})
    
    # Check first value for NULL indicators
    first_value = str(values[0]).lower().strip() if values else ""
    
    # If it's a NULL indicator and op is "eq", generate IS NULL (or empty string for description field)
    if first_value in NULL_INDICATORS and op == "eq":
        # For description field, check both NULL and empty string
        if field_config.field_name == "description":
            table_alias = field_config.table_alias or ''
            alias_prefix = f'{table_alias}.' if table_alias else ''
            return f"({alias_prefix}{col} IS NULL OR {alias_prefix}{col} = '')", ()
        table_alias = field_config.table_alias or ''
        alias_prefix = f'{table_alias}.' if table_alias else ''
        return f"{alias_prefix}{col} IS NULL", ()
    
    # If it's "not missing", "not null", "has value" etc., generate IS NOT NULL
    NOT_NULL_INDICATORS = frozenset({"not missing", "not null", "has value", "filled", "complete"})
    if first_value in NOT_NULL_INDICATORS and op == "eq":
        # For description field, check both NOT NULL AND not empty string
        if field_config.field_name == "description":
            table_alias = field_config.table_alias or ''
            alias_prefix = f'{table_alias}.' if table_alias else ''
            return f"({alias_prefix}{col} IS NOT NULL AND {alias_prefix}{col} != '')", ()
        table_alias = field_config.table_alias or ''
        alias_prefix = f'{table_alias}.' if table_alias else ''
        return f"{alias_prefix}{col} IS NOT NULL", ()
    
    # ── Boolean coercion ──────────────────────────────────────────────────
    if sql_type == "boolean":
        coerced = []
        for v in values:
            if str(v).lower() in ("true", "1", "yes"):
                coerced.append(1)
            else:
                coerced.append(0)
        values = [str(c) for c in coerced]
        table_alias = field_config.table_alias or ''
        alias_prefix = f'{table_alias}.' if table_alias else ''
        # Boolean always uses eq
        return f"{alias_prefix}{col} = ?", (coerced[0] if len(coerced) == 1 else coerced[0],)

    # ── Text fields: wrap with % for LIKE ─────────────────────────────────
    if sql_type == "text":
        table_alias = field_config.table_alias or ''
        alias_prefix = f'{table_alias}.' if table_alias else ''
        
        # Special case: status field in client/project domain uses Status table
        if field_config.field_name == "status" and field_config.column_name == "StatusName":
            if op == "eq":
                v = values[0] if values else ""
                # Use the Status table alias "st.StatusName"
                return f"st.StatusName = ?", (v,)
        
        # Regular text handling
        if op == "eq":
            v = values[0] if values else ""
            return f"{alias_prefix}{col} LIKE ?", (f"%{v}%",)
        if op == "in":
            # For text IN: each value gets its own LIKE (OR chain is safer
            # for text search than IN which requires exact match)
            if not values:
                return "1=0", ()
            like_parts = " OR ".join(f"{alias_prefix}{col} LIKE ?" for _ in values)
            params = tuple(f"%{v}%" for v in values)
            return f"({like_parts})", params
        if op == "lt":
            return f"{alias_prefix}{col} < ?", (values[0],)
        if op == "gt":
            return f"{alias_prefix}{col} >= ?", (values[0],)
        if op == "between":
            return f"{alias_prefix}{col} BETWEEN ? AND ?", (values[0], values[1])

    # ── Date / Numeric fields: exact values ───────────────────────────────
    if sql_type in ("date", "numeric"):
        table_alias = field_config.table_alias or ''
        alias_prefix = f'{table_alias}.' if table_alias else ''
        
        # Special handling for status field - use dual filter: IsActive + StatusId
        if field_config.field_name == "status" and op == "eq":
            status_value = str(values[0]).strip() if values else ""
            # Get domain from filter or default
            domain = getattr(filter_clause, 'domain', None) or "client"
            
            # Get StatusId mapping
            domain_status_map = DOMAIN_STATUS_IDS.get(domain, {})
            status_id = domain_status_map.get(status_value.capitalize(), domain_status_map.get(status_value))
            
            # Get IsActive column
            isactive_col = field_config.isactive_column
            
            if status_id and isactive_col:
                # Generate both filters: IsActive=1 AND StatusId=X
                return f"({alias_prefix}{isactive_col} = 1 AND {alias_prefix}{col} = ?)", (status_id,)
            elif status_id:
                # Fallback: just StatusId
                return f"{alias_prefix}{col} = ?", (status_id,)
        
        if op == "eq":
            v = values[0] if values else ""
            return f"{alias_prefix}{col} = ?", (v,)
        if op == "lt":
            return f"{alias_prefix}{col} < ?", (values[0],)
        if op == "gt":
            return f"{alias_prefix}{col} >= ?", (values[0],)
        if op == "between":
            return f"{alias_prefix}{col} BETWEEN ? AND ?", (values[0], values[1])
        if op == "in":
            clause, params = build_in_clause(f"{alias_prefix}{col}", values)
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
    employee_id: str | None = None,
    select_extras: str = "",
    join_extras: str = "",
    metrics: list[MetricFragment] | None = None,
) -> tuple[str, tuple]:
    """Compile a QueryPlan into executable SQL Server SQL with parameters.

    Args:
        plan: The validated QueryPlan (domain, intent, filters).
        resource_id: Required for user_self intents that join on ResourceId (int PK).
        employee_id: Required for user_self intents that join on EmployeeId (string column).
        select_extras: Additional SELECT columns to inject at {select_extras} token.
        join_extras: Additional JOIN clauses to inject at {join_extras} token.
        metrics: Optional list of MetricFragment for aggregation injection.
                 Each metric's select_expr and join_clause are combined (comma/space).
                 If any metric requires GROUP BY, a GROUP BY is appended.

    Returns:
        (sql, params_tuple) — ready for connector.execute_query().

    Raises:
        ValueError: If plan.domain == "user_self" and required ID is None.
        ValueError: If plan.intent is not found in BASE_QUERIES.
    """
    # ── RBAC guard: user_self requires resource_id or employee_id ─────────
    if plan.domain == "user_self":
        if plan.intent in _EMPLOYEE_ID_INTENTS and employee_id is None:
            raise ValueError(
                f"compile_query: user_self intent '{plan.intent}' requires employee_id — "
                "EmployeeId is a string column, not an integer ResourceId."
            )
        if plan.intent not in _EMPLOYEE_ID_INTENTS and resource_id is None:
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

    # ── Merge metric fragments into select_extras / join_extras ───────────
    needs_group_by = False
    if metrics:
        select_parts: list[str] = [select_extras] if select_extras else []
        join_parts: list[str] = [join_extras] if join_extras else []

        for mf in metrics:
            if mf.select_expr:
                select_parts.append(mf.select_expr)
            if mf.join_clause:
                join_parts.append(mf.join_clause)
            if mf.requires_group_by:
                needs_group_by = True

        select_extras = ", ".join(select_parts)
        join_extras = " ".join(join_parts)

    # ── Replace {select_extras} and {join_extras} tokens ──────────────────
    select_token = f", {select_extras}" if select_extras else ""
    join_token = f" {join_extras}" if join_extras else ""
    sql = base_sql.replace("{select_extras}", select_token).replace("{join_extras}", join_token)

    # ── Skill filter expansion: resource_by_skill 4-column OR search ──────
    # This expands {skill_filter} token before the generic filter loop runs.
    # Skill params are prepended so they align with the ? placeholders in the
    # WHERE clause, which appear before any additional filter conditions.
    skill_params: list[Any] = []
    remaining_filters = list(plan.filters)

    if "{skill_filter}" in sql:
        skill_clauses = [f for f in remaining_filters if f.field in ("skill", "skill_name")]
        if skill_clauses:
            sf = skill_clauses[0]
            v = f"%{sf.values[0]}%"
            # benched_by_skill uses s (PA_Skills alias) — 3 params
            # resource_by_skill uses tc (TechCatagory) and psk (PA_Skills) — 4 params
            if plan.intent == "benched_by_skill":
                skill_fragment = (
                    "s.Name LIKE ? OR r.PrimarySkill LIKE ? OR r.SecondarySkill LIKE ?"
                )
                skill_params = [v, v, v]
            else:
                skill_fragment = (
                    "r.PrimarySkill LIKE ? OR r.SecondarySkill LIKE ? "
                    "OR tc.TechCategoryName LIKE ? OR psk.Name LIKE ?"
                )
                skill_params = [v, v, v, v]
            sql = sql.replace("{skill_filter}", skill_fragment)
            # Remove both "skill" and "skill_name" variants so they aren't double-processed
            remaining_filters = [f for f in remaining_filters if f.field not in ("skill", "skill_name")]
        else:
            # No skill filter — return all (IsActive=1 still applies from base WHERE)
            logger.warning(
                "sql_compiler: {skill_filter} token unresolved for intent=%s — using 1=1 fallback",
                plan.intent,
            )
            sql = sql.replace("{skill_filter}", "1=1")

    # ── Skip filter application for self-contained intents ───────────────────
    # These intents have hardcoded WHERE clauses and should not receive 
    # additional filters to avoid SQL conflicts
    if plan.intent in NO_FILTER_INTENTS:
        logger.debug(
            "compile_query: intent '%s' has self-contained filters, skipping filter application",
            plan.intent
        )
        where_fragments: list[str] = []
        filter_params: list[Any] = []
    else:
        # ── Build filter WHERE clauses from remaining filters ─────────────────
        where_fragments: list[str] = []
        filter_params: list[Any] = []

        for f in remaining_filters:
            field_config = FIELD_REGISTRY.get(f.field)
            if field_config is None:
                logger.warning(
                    "compile_query: field '%s' not found in FIELD_REGISTRY — skipping filter",
                    f.field,
                )
                continue

            fragment, params = build_filter_clause(f, field_config, domain=plan.domain)
            if fragment and fragment not in ("1=1",):
                where_fragments.append(fragment)
                filter_params.extend(params)

    # ── reports_to: extract manager name param from filters ───────────────────
    # Base SQL has hardcoded WHERE pm.ResourceName LIKE ? — param must come from
    # the resource_name filter, not the generic filter loop (which is skipped).
    reports_to_params: tuple = ()
    if plan.intent == "reports_to":
        name_filter = next((f for f in plan.filters if f.field == "resource_name"), None)
        if name_filter and name_filter.values:
            name_val = f"%{name_filter.values[0]}%"
        else:
            name_val = "%"  # fallback: return all (no manager specified)
        reports_to_params = (name_val,)

    # ── Assemble final SQL ─────────────────────────────────────────────────
    # For user_self intents: the base SQL already contains "WHERE ... = ?"
    # with the appropriate ID (resource_id int or employee_id string) as the first param.
    if plan.domain == "user_self":
        user_self_id = employee_id if plan.intent in _EMPLOYEE_ID_INTENTS else resource_id
        base_params: tuple = (user_self_id,)

        if where_fragments:
            additional = " AND ".join(where_fragments)
            sql = sql + " AND " + additional

        all_params = base_params + tuple(filter_params)
        logger.debug(
            "compile_query: domain=%s intent=%s filters=%d params=%d",
            plan.domain, plan.intent, len(plan.filters), len(all_params),
        )

        if needs_group_by:
            sql = _inject_group_by(sql, plan)

        return sql, all_params

    # For other domains: skill_params first, then additional WHERE filters
    if where_fragments:
        additional = " AND ".join(where_fragments)
        if " WHERE " in sql.upper() or " WHERE\n" in sql.upper():
            sql = sql + " AND " + additional
        else:
            sql = sql + " WHERE " + additional

    if needs_group_by:
        sql = _inject_group_by(sql, plan)

    all_params = reports_to_params + tuple(skill_params) + tuple(filter_params)
    logger.debug(
        "compile_query: domain=%s intent=%s filters=%d params=%d",
        plan.domain, plan.intent, len(plan.filters), len(all_params),
    )
    return sql, all_params


# ---------------------------------------------------------------------------
# _inject_group_by — extract non-aggregated columns and append GROUP BY
# ---------------------------------------------------------------------------

def _inject_group_by(sql: str, plan: QueryPlan) -> str:
    """Inject a GROUP BY clause for the non-aggregated columns in the SELECT.

    Parses the SELECT list and extracts columns that are NOT wrapped in an
    aggregation function (SUM, COUNT, AVG, MIN, MAX). Returns the SQL with
    GROUP BY appended.

    This is a best-effort parser for the structured templates in BASE_QUERIES.
    It finds the first SELECT ... FROM and extracts individual items.
    """
    import re

    # Extract the SELECT list between SELECT and the first FROM
    select_match = re.search(r"SELECT\s+(.*?)\s+FROM\b", sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        logger.warning("_inject_group_by: could not parse SELECT list — skipping GROUP BY")
        return sql

    select_list_raw = select_match.group(1)

    # Split select items by comma (naive but sufficient for templates)
    items = [item.strip() for item in select_list_raw.split(",")]

    # Filter out aggregation expressions: SUM(...), COUNT(...), AVG(...), MIN(...), MAX(...)
    agg_pattern = re.compile(r"^\s*(SUM|COUNT|AVG|MIN|MAX)\s*\(", re.IGNORECASE)

    group_by_cols: list[str] = []
    for item in items:
        item = item.strip()
        if not item or agg_pattern.match(item):
            continue
        # Strip aliases (AS alias or just alias at end)
        alias_stripped = re.sub(r"\s+AS\s+\[?[A-Za-z0-9_ ]+\]?\s*$", "", item, flags=re.IGNORECASE).strip()
        alias_stripped = re.sub(r"\s+\[?[A-Za-z0-9_]+\]?\s*$", "", alias_stripped).strip()
        if alias_stripped:
            group_by_cols.append(alias_stripped)

    if not group_by_cols:
        logger.warning("_inject_group_by: no non-aggregated columns found — skipping GROUP BY")
        return sql

    group_by_clause = "GROUP BY " + ", ".join(group_by_cols)
    return sql + " " + group_by_clause
