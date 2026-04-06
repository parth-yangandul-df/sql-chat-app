# DEPRECATED: superseded by QueryPlan compiler (Phase 7).
# Kept for feature flag rollback safety — still imported by _try_refinement() in the
# flag=OFF path (base_domain.py else branch). DO NOT delete until USE_QUERY_PLAN_COMPILER=true
# is confirmed stable in production and the flag=OFF rollback path is no longer needed.
"""Declarative refinement registry for all PRMS domain agents.

Each refinement template defines how to wrap a prior SQL result set as a
subquery with additional filter conditions (skill, name, date range, status,
numeric, boolean).  The registry is consulted by BaseDomainAgent.execute()
to determine whether a follow-up query can be handled as a subquery
refinement rather than re-running the base intent.

Usage:
    from app.llm.graph.domains.refinement_registry import (
        REFINEMENT_REGISTRY, get_refinement_templates, RefinementType
    )
    templates = get_refinement_templates("resource", "active_resources")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RefinementType(Enum):
    """Types of refinement filters supported."""
    SKILL_FILTER = "skill"           # JOIN PA_ResourceSkills/PA_Skills
    NAME_FILTER = "name"             # WHERE prev.[NameCol] LIKE ?
    DATE_RANGE = "date_range"        # WHERE prev.[DateCol] BETWEEN ? AND ?
    STATUS_FILTER = "status"         # WHERE prev.[StatusCol] LIKE ?
    NUMERIC_FILTER = "numeric"       # WHERE prev.[NumCol] >= ? or BETWEEN ? AND ?
    BOOLEAN_FILTER = "boolean"       # WHERE prev.[BoolCol] = ?
    TEXT_FILTER = "text"             # WHERE prev.[TextCol] LIKE ?


@dataclass(frozen=True)
class RefinementTemplate:
    """A single refinement capability for a domain intent."""
    domain: str
    intent: str
    refinement_type: RefinementType
    column: str                    # Column alias in the prior result set
    sql_template: str              # SQL pattern with {prior_sql} placeholder
    params_required: int           # Number of ? parameters
    param_keys: tuple[str, ...]    # Keys to read from params dict (in order)
    description: str

    def build_sql(self, prior_sql: str, params: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
        """Build the final SQL and parameter tuple for this refinement.

        Returns (sql, params) ready for connector.execute_query().
        Raises ValueError if required params are missing.
        """
        if "{prior_sql}" not in self.sql_template:
            raise ValueError(f"Template missing {{prior_sql}} placeholder: {self}")

        sql = self.sql_template.format(prior_sql=prior_sql)

        # Extract parameter values from params dict
        values = []
        for key in self.param_keys:
            val = params.get(key)
            if val is None:
                raise ValueError(
                    f"Missing required param '{key}' for {self.refinement_type.value} "
                    f"refinement on {self.domain}.{self.intent}"
                )
            # For LIKE filters, wrap with wildcards
            if self.refinement_type in (
                RefinementType.NAME_FILTER,
                RefinementType.STATUS_FILTER,
                RefinementType.TEXT_FILTER,
                RefinementType.SKILL_FILTER,
            ):
                values.append(f"%{val}%")
            else:
                values.append(val)

        return sql, tuple(values)


# ---------------------------------------------------------------------------
# REFINEMENT REGISTRY
# ---------------------------------------------------------------------------
# domain → intent → list of RefinementTemplate
# ---------------------------------------------------------------------------

REFINEMENT_REGISTRY: dict[str, dict[str, list[RefinementTemplate]]] = {}


def _register(template: RefinementTemplate) -> None:
    """Register a refinement template (called at module load time)."""
    REFINEMENT_REGISTRY.setdefault(template.domain, {}).setdefault(
        template.intent, []
    ).append(template)


# ===================================================================
# RESOURCE DOMAIN
# ===================================================================

# active_resources → skill filter (JOIN PA_ResourceSkills)
_register(RefinementTemplate(
    domain="resource",
    intent="active_resources",
    refinement_type=RefinementType.SKILL_FILTER,
    column="EMPID",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "JOIN Resource r2 ON r2.EmployeeId = prev.EMPID "
        "JOIN PA_ResourceSkills rs ON rs.ResourceId = r2.ResourceId "
        "JOIN PA_Skills s ON s.SkillId = rs.SkillId "
        "WHERE s.Name LIKE ? OR r2.PrimarySkill LIKE ? OR r2.SecondarySkill LIKE ?"
    ),
    params_required=3,
    param_keys=("skill", "skill", "skill"),
    description="Filter active resources by skill name",
))

# active_resources → name filter
_register(RefinementTemplate(
    domain="resource",
    intent="active_resources",
    refinement_type=RefinementType.NAME_FILTER,
    column="Name",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Name] LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter active resources by name",
))

# active_resources → designation filter
_register(RefinementTemplate(
    domain="resource",
    intent="active_resources",
    refinement_type=RefinementType.STATUS_FILTER,
    column="Designation",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Designation] LIKE ?"
    ),
    params_required=1,
    param_keys=("designation",),
    description="Filter active resources by designation",
))

# benched_resources → skill filter
_register(RefinementTemplate(
    domain="resource",
    intent="benched_resources",
    refinement_type=RefinementType.SKILL_FILTER,
    column="EMPID",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "JOIN Resource r2 ON r2.EmployeeId = prev.EMPID "
        "JOIN PA_ResourceSkills rs ON rs.ResourceId = r2.ResourceId "
        "JOIN PA_Skills s ON s.SkillId = rs.SkillId "
        "WHERE s.Name LIKE ? OR r2.PrimarySkill LIKE ? OR r2.SecondarySkill LIKE ?"
    ),
    params_required=3,
    param_keys=("skill", "skill", "skill"),
    description="Filter benched resources by skill name",
))

# benched_resources → name filter
_register(RefinementTemplate(
    domain="resource",
    intent="benched_resources",
    refinement_type=RefinementType.NAME_FILTER,
    column="Name",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Name] LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter benched resources by name",
))

# benched_resources → tech category filter
_register(RefinementTemplate(
    domain="resource",
    intent="benched_resources",
    refinement_type=RefinementType.STATUS_FILTER,
    column="TechCategoryName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.TechCategoryName LIKE ?"
    ),
    params_required=1,
    param_keys=("tech_category",),
    description="Filter benched resources by tech category",
))

# resource_by_skill → designation filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_by_skill",
    refinement_type=RefinementType.STATUS_FILTER,
    column="Designation",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Designation] LIKE ?"
    ),
    params_required=1,
    param_keys=("designation",),
    description="Filter resources by skill + designation",
))

# resource_availability → name filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_availability",
    refinement_type=RefinementType.NAME_FILTER,
    column="ResourceName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ResourceName LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter available resources by name",
))

# resource_availability → skill filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_availability",
    refinement_type=RefinementType.SKILL_FILTER,
    column="ResourceId",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "JOIN PA_ResourceSkills rs ON rs.ResourceId = prev.ResourceId "
        "JOIN PA_Skills s ON s.SkillId = rs.SkillId "
        "WHERE s.Name LIKE ?"
    ),
    params_required=1,
    param_keys=("skill",),
    description="Filter available resources by skill",
))

# resource_project_assignments → date range filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_project_assignments",
    refinement_type=RefinementType.DATE_RANGE,
    column="Start Date",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Start Date] >= ? AND prev.[End Date] <= ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter project assignments by date range",
))

# resource_project_assignments → billable filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_project_assignments",
    refinement_type=RefinementType.BOOLEAN_FILTER,
    column="Billab",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Billab = ?"
    ),
    params_required=1,
    param_keys=("billable",),
    description="Filter project assignments by billable status",
))

# resource_project_assignments → role filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_project_assignments",
    refinement_type=RefinementType.TEXT_FILTER,
    column="Role",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Role] LIKE ?"
    ),
    params_required=1,
    param_keys=("role",),
    description="Filter project assignments by role",
))

# resource_project_assignments → min allocation filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_project_assignments",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="Allocation",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Allocation] >= ?"
    ),
    params_required=1,
    param_keys=("min_allocation",),
    description="Filter project assignments by minimum allocation %",
))

# resource_skills_list → skill name filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_skills_list",
    refinement_type=RefinementType.TEXT_FILTER,
    column="Name",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Name LIKE ?"
    ),
    params_required=1,
    param_keys=("skill_name",),
    description="Filter resource skills by skill name",
))

# resource_skills_list → min experience filter
_register(RefinementTemplate(
    domain="resource",
    intent="resource_skills_list",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="SkillExperience",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.SkillExperience >= ?"
    ),
    params_required=1,
    param_keys=("min_experience",),
    description="Filter resource skills by minimum experience",
))


# ===================================================================
# CLIENT DOMAIN
# ===================================================================

# active_clients → name filter
_register(RefinementTemplate(
    domain="client",
    intent="active_clients",
    refinement_type=RefinementType.NAME_FILTER,
    column="ClientName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ClientName LIKE ?"
    ),
    params_required=1,
    param_keys=("client_name",),
    description="Filter active clients by name",
))

# active_clients → country filter
_register(RefinementTemplate(
    domain="client",
    intent="active_clients",
    refinement_type=RefinementType.STATUS_FILTER,
    column="CountryId",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.CountryId = ?"
    ),
    params_required=1,
    param_keys=("country_id",),
    description="Filter active clients by country ID",
))

# client_projects → date range filter
_register(RefinementTemplate(
    domain="client",
    intent="client_projects",
    refinement_type=RefinementType.DATE_RANGE,
    column="StartDate",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.StartDate BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter client projects by date range",
))

# client_projects → project name filter
_register(RefinementTemplate(
    domain="client",
    intent="client_projects",
    refinement_type=RefinementType.TEXT_FILTER,
    column="ProjectName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ProjectName LIKE ?"
    ),
    params_required=1,
    param_keys=("project_name",),
    description="Filter client projects by project name",
))

# client_status → status filter
_register(RefinementTemplate(
    domain="client",
    intent="client_status",
    refinement_type=RefinementType.STATUS_FILTER,
    column="StatusName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.StatusName LIKE ?"
    ),
    params_required=1,
    param_keys=("status",),
    description="Filter client status by status name",
))


# ===================================================================
# PROJECT DOMAIN
# ===================================================================

# active_projects → client name filter
_register(RefinementTemplate(
    domain="project",
    intent="active_projects",
    refinement_type=RefinementType.NAME_FILTER,
    column="ClientName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ClientName LIKE ?"
    ),
    params_required=1,
    param_keys=("client_name",),
    description="Filter active projects by client name",
))

# active_projects → project name filter
_register(RefinementTemplate(
    domain="project",
    intent="active_projects",
    refinement_type=RefinementType.TEXT_FILTER,
    column="ProjectName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ProjectName LIKE ?"
    ),
    params_required=1,
    param_keys=("project_name",),
    description="Filter active projects by project name",
))

# project_by_client → status filter
_register(RefinementTemplate(
    domain="project",
    intent="project_by_client",
    refinement_type=RefinementType.STATUS_FILTER,
    column="Status",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Status LIKE ?"
    ),
    params_required=1,
    param_keys=("status",),
    description="Filter projects by status",
))

# project_by_client → project manager filter
_register(RefinementTemplate(
    domain="project",
    intent="project_by_client",
    refinement_type=RefinementType.TEXT_FILTER,
    column="Project Manager",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Project Manager] LIKE ?"
    ),
    params_required=1,
    param_keys=("project_manager",),
    description="Filter projects by project manager name",
))

# project_by_client → date range filter
_register(RefinementTemplate(
    domain="project",
    intent="project_by_client",
    refinement_type=RefinementType.DATE_RANGE,
    column="Start date",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Start date] BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter projects by date range",
))

# project_budget → budget range filter
_register(RefinementTemplate(
    domain="project",
    intent="project_budget",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="Budget",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Budget >= ?"
    ),
    params_required=1,
    param_keys=("min_budget",),
    description="Filter projects by minimum budget",
))

# project_budget → utilization threshold
_register(RefinementTemplate(
    domain="project",
    intent="project_budget",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="BudgetUtilized",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.BudgetUtilized >= ?"
    ),
    params_required=1,
    param_keys=("min_utilization",),
    description="Filter projects by minimum budget utilization",
))

# project_resources → billable filter
_register(RefinementTemplate(
    domain="project",
    intent="project_resources",
    refinement_type=RefinementType.BOOLEAN_FILTER,
    column="Billable",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Billable = ?"
    ),
    params_required=1,
    param_keys=("billable",),
    description="Filter project resources by billable status",
))

# project_resources → role filter
_register(RefinementTemplate(
    domain="project",
    intent="project_resources",
    refinement_type=RefinementType.TEXT_FILTER,
    column="ResourceRole",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ResourceRole LIKE ?"
    ),
    params_required=1,
    param_keys=("role",),
    description="Filter project resources by role",
))

# project_resources → tech category filter
_register(RefinementTemplate(
    domain="project",
    intent="project_resources",
    refinement_type=RefinementType.STATUS_FILTER,
    column="TechCategoryName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.TechCategoryName LIKE ?"
    ),
    params_required=1,
    param_keys=("tech_category",),
    description="Filter project resources by tech category",
))

# project_resources → min allocation filter
_register(RefinementTemplate(
    domain="project",
    intent="project_resources",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="PercentageAllocation",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.PercentageAllocation >= ?"
    ),
    params_required=1,
    param_keys=("min_allocation",),
    description="Filter project resources by minimum allocation %",
))

# project_resources → resource name filter
_register(RefinementTemplate(
    domain="project",
    intent="project_resources",
    refinement_type=RefinementType.NAME_FILTER,
    column="ResourceName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ResourceName LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter project resources by resource name",
))

# project_resources → client filter
_register(RefinementTemplate(
    domain="project",
    intent="project_resources",
    refinement_type=RefinementType.NAME_FILTER,
    column="ClientId",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ClientId = ?"
    ),
    params_required=1,
    param_keys=("client_id",),
    description="Filter project resources by client ID",
))

# project_timeline → date range filter
_register(RefinementTemplate(
    domain="project",
    intent="project_timeline",
    refinement_type=RefinementType.DATE_RANGE,
    column="Start Date",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Start Date] BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter project timelines by date range",
))

# project_timeline → min duration filter
_register(RefinementTemplate(
    domain="project",
    intent="project_timeline",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="DurationDays",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.DurationDays >= ?"
    ),
    params_required=1,
    param_keys=("min_duration",),
    description="Filter project timelines by minimum duration (days)",
))

# overdue_projects → client name filter
_register(RefinementTemplate(
    domain="project",
    intent="overdue_projects",
    refinement_type=RefinementType.NAME_FILTER,
    column="ClientName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ClientName LIKE ?"
    ),
    params_required=1,
    param_keys=("client_name",),
    description="Filter overdue projects by client name",
))

# overdue_projects → days overdue filter
_register(RefinementTemplate(
    domain="project",
    intent="overdue_projects",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="EndDate",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE DATEDIFF(DAY, prev.EndDate, GETDATE()) >= ?"
    ),
    params_required=1,
    param_keys=("days_overdue",),
    description="Filter overdue projects by minimum days overdue",
))


# ===================================================================
# TIMESHEET DOMAIN
# ===================================================================

# approved_timesheets → resource name filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="approved_timesheets",
    refinement_type=RefinementType.NAME_FILTER,
    column="ResourceName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ResourceName LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter approved timesheets by resource name",
))

# approved_timesheets → date range filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="approved_timesheets",
    refinement_type=RefinementType.DATE_RANGE,
    column="WorkDate",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.WorkDate BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter approved timesheets by date range",
))

# approved_timesheets → min hours filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="approved_timesheets",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="Hours",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Hours >= ?"
    ),
    params_required=1,
    param_keys=("min_hours",),
    description="Filter approved timesheets by minimum hours",
))

# approved_timesheets → description filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="approved_timesheets",
    refinement_type=RefinementType.TEXT_FILTER,
    column="Description",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Description LIKE ?"
    ),
    params_required=1,
    param_keys=("description",),
    description="Filter approved timesheets by description text",
))

# timesheet_by_period → resource name filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="timesheet_by_period",
    refinement_type=RefinementType.NAME_FILTER,
    column="ResourceName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ResourceName LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter timesheets by period + resource name",
))

# timesheet_by_period → min hours filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="timesheet_by_period",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="Hours",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Hours >= ?"
    ),
    params_required=1,
    param_keys=("min_hours",),
    description="Filter timesheets by period + minimum hours",
))

# unapproved_timesheets → resource name filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="unapproved_timesheets",
    refinement_type=RefinementType.NAME_FILTER,
    column="ResourceName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ResourceName LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter unapproved timesheets by resource name",
))

# unapproved_timesheets → date range filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="unapproved_timesheets",
    refinement_type=RefinementType.DATE_RANGE,
    column="WorkDate",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.WorkDate BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter unapproved timesheets by date range",
))

# timesheet_by_project → resource name filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="timesheet_by_project",
    refinement_type=RefinementType.NAME_FILTER,
    column="ResourceName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ResourceName LIKE ?"
    ),
    params_required=1,
    param_keys=("resource_name",),
    description="Filter project timesheets by resource name",
))

# timesheet_by_project → date range filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="timesheet_by_project",
    refinement_type=RefinementType.DATE_RANGE,
    column="WorkDate",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.WorkDate BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter project timesheets by date range",
))

# timesheet_by_project → min hours filter
_register(RefinementTemplate(
    domain="timesheet",
    intent="timesheet_by_project",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="Hours",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Hours >= ?"
    ),
    params_required=1,
    param_keys=("min_hours",),
    description="Filter project timesheets by minimum hours",
))


# ===================================================================
# USER SELF DOMAIN
# ===================================================================

# my_projects → date range filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_projects",
    refinement_type=RefinementType.DATE_RANGE,
    column="Start Date",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Start Date] >= ?"
    ),
    params_required=1,
    param_keys=("start_date",),
    description="Filter my projects by start date",
))

# my_projects → end date filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_projects",
    refinement_type=RefinementType.DATE_RANGE,
    column="End Date",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[End Date] <= ?"
    ),
    params_required=1,
    param_keys=("end_date",),
    description="Filter my projects by end date",
))

# my_allocation → date range filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_allocation",
    refinement_type=RefinementType.DATE_RANGE,
    column="StartDate",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.StartDate >= ? AND prev.EndDate <= ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter my allocation by date range",
))

# my_allocation → min allocation filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_allocation",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="PercentageAllocation",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.PercentageAllocation >= ?"
    ),
    params_required=1,
    param_keys=("min_allocation",),
    description="Filter my allocation by minimum %",
))

# my_allocation → project name filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_allocation",
    refinement_type=RefinementType.TEXT_FILTER,
    column="ProjectName",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.ProjectName LIKE ?"
    ),
    params_required=1,
    param_keys=("project_name",),
    description="Filter my allocation by project name",
))

# my_timesheets → date range filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_timesheets",
    refinement_type=RefinementType.DATE_RANGE,
    column="File Date",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[File Date] BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter my timesheets by date range",
))

# my_timesheets → category filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_timesheets",
    refinement_type=RefinementType.TEXT_FILTER,
    column="Category",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Category LIKE ?"
    ),
    params_required=1,
    param_keys=("category",),
    description="Filter my timesheets by category",
))

# my_timesheets → min hours filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_timesheets",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="Effort Hours",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[Effort Hours] >= ?"
    ),
    params_required=1,
    param_keys=("min_hours",),
    description="Filter my timesheets by minimum hours",
))

# my_skills → skill name filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_skills",
    refinement_type=RefinementType.TEXT_FILTER,
    column="Name",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Name LIKE ?"
    ),
    params_required=1,
    param_keys=("skill_name",),
    description="Filter my skills by skill name",
))

# my_skills → min experience filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_skills",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="SkillExperience",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.SkillExperience >= ?"
    ),
    params_required=1,
    param_keys=("min_experience",),
    description="Filter my skills by minimum experience",
))

# my_utilization → date range filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_utilization",
    refinement_type=RefinementType.DATE_RANGE,
    column="File Date",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.[File Date] BETWEEN ? AND ?"
    ),
    params_required=2,
    param_keys=("start_date", "end_date"),
    description="Filter my utilization by date range",
))

# my_utilization → min hours filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_utilization",
    refinement_type=RefinementType.NUMERIC_FILTER,
    column="TotalHours",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.TotalHours >= ?"
    ),
    params_required=1,
    param_keys=("min_hours",),
    description="Filter my utilization by minimum hours",
))

# my_utilization → category filter
_register(RefinementTemplate(
    domain="user_self",
    intent="my_utilization",
    refinement_type=RefinementType.TEXT_FILTER,
    column="Title",
    sql_template=(
        "SELECT prev.* "
        "FROM ({prior_sql}) AS prev "
        "WHERE prev.Title LIKE ?"
    ),
    params_required=1,
    param_keys=("category",),
    description="Filter my utilization by title/category",
))


# ===================================================================
# Helper functions
# ===================================================================

def get_refinement_templates(domain: str, intent: str) -> list[RefinementTemplate]:
    """Get all refinement templates for a domain+intent.

    Returns empty list if no templates are registered.
    """
    return REFINEMENT_REGISTRY.get(domain, {}).get(intent, [])


def get_supported_domains() -> list[str]:
    """Get list of all domains with refinement templates."""
    return list(REFINEMENT_REGISTRY.keys())


def get_supported_intents(domain: str) -> list[str]:
    """Get list of all intents with refinement templates for a domain."""
    return list(REFINEMENT_REGISTRY.get(domain, {}).keys())


def supports_refinement(domain: str, intent: str) -> bool:
    """Check if a domain+intent has any refinement templates."""
    return intent in REFINEMENT_REGISTRY.get(domain, {})


def find_matching_template(
    domain: str,
    intent: str,
    params: dict[str, Any],
) -> RefinementTemplate | None:
    """Find the first refinement template whose required params are present.

    Iterates through templates for the domain+intent and returns the first
    one where all param_keys exist in the params dict.

    Returns None if no matching template is found.
    """
    for template in get_refinement_templates(domain, intent):
        if all(params.get(k) is not None for k in template.param_keys):
            return template
    return None
