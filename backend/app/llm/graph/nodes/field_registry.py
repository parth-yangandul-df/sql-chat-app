"""FieldRegistry — all PRMS filterable fields with column mappings and aliases.

This registry maps canonical field names to their SQL column names, data types,
multi-value flags (append vs replace), and domain scopes. Used by filter_extractor
to validate extracted filters and by plan_updater for merge rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class StartupIntegrityError(Exception):
    """Raised when the FieldRegistry is incomplete relative to the intent catalog."""


@dataclass(frozen=True)
class FieldConfig:
    """Configuration for a single filterable field in the PRMS domain."""

    field_name: str           # Canonical name (e.g. "skill", "client_name")
    column_name: str          # SQL Server column (e.g. "Name", "ClientName")
    multi_value: bool         # True → append new values; False → replace (last-wins)
    sql_type: str             # "text" | "date" | "numeric" | "boolean"
    domains: list[str]        # Domains this field applies to
    aliases: list[str] = field(default_factory=list)  # Alternate param keys
    # New fields for extraction guidance
    example_values: list[str] = field(default_factory=list)  # Example values for LLM
    extraction_hints: list[str] = field(default_factory=list)  # Phrases that indicate this field
    # Status field specific (for dual-filter: IsActive + StatusId)
    isactive_column: str | None = None  # e.g. "IsActive" for client, "IsActive" for project
    status_map: dict[str, dict[str, int]] = field(default_factory=dict)  # domain -> {status_name: status_id}


# ---------------------------------------------------------------------------
# STATUS ID MAPPINGS — Domain-specific status IDs
# ---------------------------------------------------------------------------
# Used for dual-filter approach: WHERE IsActive=1 AND StatusId=X
# Reference: User provided mappings
# ---------------------------------------------------------------------------

DOMAIN_STATUS_IDS: dict[str, dict[str, int]] = {
    "client": {
        "Active": 2,
        "Inactive": 1,
        "Closed": 12,
    },
    "project": {
        "Active": 4,
        "Inactive": 3,
        "On hold": 5,
        "Others": 6,
        "Closed": 13,
    },
    "resource": {
        "Active": 8,
        "Inactive": 7,
    },
}


# ---------------------------------------------------------------------------
# FIELD REGISTRY — canonical field_name → FieldConfig
# ---------------------------------------------------------------------------
# Fields shared across domains have their domains list populated with all
# applicable domains. The same FieldConfig object is referenced from
# FIELD_REGISTRY_BY_DOMAIN for per-domain lookups.
# ---------------------------------------------------------------------------

FIELD_REGISTRY: dict[str, FieldConfig] = {

    # ── SKILL (resource, user_self) ──────────────────────────────────────
    "skill": FieldConfig(
        field_name="skill",
        column_name="Name",             # PA_Skills.Name
        multi_value=True,               # Can filter by multiple skills
        sql_type="text",
        domains=["resource"],
        aliases=["skill_filter"],
        example_values=["Python", "Java", "React", "SQL", "Angular", ".NET", "NodeJS"],
        extraction_hints=["knows", "experienced", "proficient", "skills", "technology", "tech"],
    ),

    # ── RESOURCE NAME ─────────────────────────────────────────────────────
    "resource_name": FieldConfig(
        field_name="resource_name",
        column_name="Name",             # Resource.Name / ResourceName alias
        multi_value=False,
        sql_type="text",
        domains=["resource", "project", "timesheet"],
        aliases=["employee_name", "person", "resource"],
        example_values=["John Doe", "Harshal Yeole", "Jane Smith"],
        extraction_hints=["of", "skills of", "show me", "assigned to", "for"],
    ),

    # ── DESIGNATION ───────────────────────────────────────────────────────
    "designation": FieldConfig(
        field_name="designation",
        column_name="Designation",
        multi_value=False,
        sql_type="text",
        domains=["resource"],
        aliases=[],
        example_values=["Software Engineer", "Senior Developer", "Tech Lead", "Manager"],
        extraction_hints=["working as", "role", "designation", "position"],
    ),

    # ── TECH CATEGORY ─────────────────────────────────────────────────────
    "tech_category": FieldConfig(
        field_name="tech_category",
        column_name="TechCategoryName",
        multi_value=False,
        sql_type="text",
        domains=["resource", "project"],
        aliases=["category"],
        example_values=["Java", "Microsoft", "Open Source", "Data"],
        extraction_hints=["category", "tech category", "technology stack"],
    ),

    # ── ROLE ──────────────────────────────────────────────────────────────
    "role": FieldConfig(
        field_name="role",
        column_name="Role",
        multi_value=False,
        sql_type="text",
        domains=["resource", "project"],
        aliases=[],
        example_values=["Developer", "Tester", "Architect", "Lead"],
        extraction_hints=["role", "as", "working as"],
    ),

    # ── START DATE ────────────────────────────────────────────────────────
    "start_date": FieldConfig(
        field_name="start_date",
        column_name="StartDate",
        multi_value=False,              # Date ranges are last-wins
        sql_type="date",
        domains=["resource", "client", "project", "timesheet", "user_self"],
        aliases=[],
    ),

    # ── END DATE ──────────────────────────────────────────────────────────
    "end_date": FieldConfig(
        field_name="end_date",
        column_name="EndDate",
        multi_value=False,
        sql_type="date",
        domains=["resource", "client", "project", "timesheet", "user_self"],
        aliases=[],
    ),

    # ── BILLABLE ──────────────────────────────────────────────────────────
    "billable": FieldConfig(
        field_name="billable",
        column_name="Billab",           # PA_ProjectResources.Billab
        multi_value=False,              # Boolean — last-wins
        sql_type="boolean",
        domains=["resource", "project"],
        aliases=[],
    ),

    # ── MIN ALLOCATION ────────────────────────────────────────────────────
    "min_allocation": FieldConfig(
        field_name="min_allocation",
        column_name="PercentageAllocation",
        multi_value=False,
        sql_type="numeric",
        domains=["resource", "project", "user_self"],
        aliases=[],
    ),

    # ── SKILL NAME (for resource_skills_list / my_skills) ─────────────────
    "skill_name": FieldConfig(
        field_name="skill_name",
        column_name="Name",             # PA_Skills.Name column alias
        multi_value=False,
        sql_type="text",
        domains=["resource", "user_self"],
        aliases=[],
    ),

    # ── MIN EXPERIENCE ────────────────────────────────────────────────────
    "min_experience": FieldConfig(
        field_name="min_experience",
        column_name="SkillExperience",
        multi_value=False,
        sql_type="numeric",
        domains=["resource", "user_self"],
        aliases=[],
    ),

    # ── CLIENT NAME ───────────────────────────────────────────────────────
    "client_name": FieldConfig(
        field_name="client_name",
        column_name="ClientName",
        multi_value=False,
        sql_type="text",
        domains=["client", "project"],
        aliases=["account_name"],
        example_values=["Google", "Microsoft", "Amazon", "Apple"],
        extraction_hints=["for client", "projects for", "client"],
    ),

    # ── COUNTRY ID ────────────────────────────────────────────────────────
    "country_id": FieldConfig(
        field_name="country_id",
        column_name="CountryId",
        multi_value=False,
        sql_type="text",
        domains=["client"],
        aliases=[],
    ),

    # ── PROJECT NAME ──────────────────────────────────────────────────────
    "project_name": FieldConfig(
        field_name="project_name",
        column_name="ProjectName",
        multi_value=False,
        sql_type="text",
        domains=["client", "project", "user_self"],
        aliases=[],
        example_values=["Project Alpha", "Migration Project"],
        extraction_hints=["project", "named"],
    ),

    # ── STATUS ────────────────────────────────────────────────────────────
    "status": FieldConfig(
        field_name="status",
        column_name="StatusId",  # Use StatusId for filtering
        multi_value=False,
        sql_type="numeric",  # Changed from text to numeric
        domains=["client", "project", "resource"],
        aliases=[],
        example_values=["Active", "Inactive", "Closed", "On hold", "Others", "Completed"],
        extraction_hints=["status", "is", "state"],
        isactive_column="IsActive",  # Dual-filter: IsActive + StatusId
        status_map=DOMAIN_STATUS_IDS,  # Domain-specific StatusId mappings
    ),

    # ── PROJECT MANAGER ───────────────────────────────────────────────────
    "project_manager": FieldConfig(
        field_name="project_manager",
        column_name="Project Manager",
        multi_value=False,
        sql_type="text",
        domains=["project"],
        aliases=["pm"],
    ),

    # ── MIN BUDGET ────────────────────────────────────────────────────────
    "min_budget": FieldConfig(
        field_name="min_budget",
        column_name="Budget",
        multi_value=False,
        sql_type="numeric",
        domains=["project"],
        aliases=[],
    ),

    # ── MIN UTILIZATION ───────────────────────────────────────────────────
    "min_utilization": FieldConfig(
        field_name="min_utilization",
        column_name="BudgetUtilized",
        multi_value=False,
        sql_type="numeric",
        domains=["project"],
        aliases=[],
    ),

    # ── CLIENT ID ─────────────────────────────────────────────────────────
    "client_id": FieldConfig(
        field_name="client_id",
        column_name="ClientId",
        multi_value=False,
        sql_type="numeric",
        domains=["project"],
        aliases=[],
    ),

    # ── MIN DURATION ──────────────────────────────────────────────────────
    "min_duration": FieldConfig(
        field_name="min_duration",
        column_name="DurationDays",
        multi_value=False,
        sql_type="numeric",
        domains=["project"],
        aliases=[],
    ),

    # ── DAYS OVERDUE ──────────────────────────────────────────────────────
    "days_overdue": FieldConfig(
        field_name="days_overdue",
        column_name="EndDate",          # Derived: DATEDIFF(DAY, EndDate, GETDATE())
        multi_value=False,
        sql_type="numeric",
        domains=["project"],
        aliases=[],
    ),

    # ── MIN HOURS ─────────────────────────────────────────────────────────
    "min_hours": FieldConfig(
        field_name="min_hours",
        column_name="Hours",
        multi_value=False,
        sql_type="numeric",
        domains=["timesheet", "user_self"],
        aliases=[],
    ),

    # ── DESCRIPTION ───────────────────────────────────────────────────────
    "description": FieldConfig(
        field_name="description",
        column_name="Description",
        multi_value=False,
        sql_type="text",
        domains=["client", "timesheet"],
        aliases=[],
        example_values=["Client description", "Acme Corp partnership"],
        extraction_hints=["description", "about", "details"],
    ),

    # ── CATEGORY (user_self timesheets / utilization) ─────────────────────
    "category": FieldConfig(
        field_name="category",
        column_name="Category",
        multi_value=False,
        sql_type="text",
        domains=["user_self"],
        aliases=[],
    ),
}


# ---------------------------------------------------------------------------
# FIELD_REGISTRY_BY_DOMAIN — domain → { field_name → FieldConfig }
# ---------------------------------------------------------------------------
# Built at module load time from FIELD_REGISTRY. Each field appears in all
# domains listed in its domains list.
# ---------------------------------------------------------------------------

FIELD_REGISTRY_BY_DOMAIN: dict[str, dict[str, FieldConfig]] = {}

for _fc in FIELD_REGISTRY.values():
    for _domain in _fc.domains:
        FIELD_REGISTRY_BY_DOMAIN.setdefault(_domain, {})[_fc.field_name] = _fc


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def lookup_field(field_name: str, domain: str) -> FieldConfig | None:
    """Look up a FieldConfig by canonical field name and domain.

    Returns None if the field is not registered for the given domain.
    """
    return FIELD_REGISTRY_BY_DOMAIN.get(domain, {}).get(field_name)


def resolve_alias(param_key: str, domain: str) -> str | None:
    """Map a param key to a canonical field name for the given domain.

    Tries:
    1. Direct canonical field lookup in FIELD_REGISTRY_BY_DOMAIN[domain]
    2. Alias scan: checks if param_key appears in any field's aliases list
       for the domain.

    Returns the canonical field_name if found, None otherwise.
    """
    domain_fields = FIELD_REGISTRY_BY_DOMAIN.get(domain, {})

    # 1. Direct match
    if param_key in domain_fields:
        return param_key

    # 2. Alias scan
    for fc in domain_fields.values():
        if param_key in fc.aliases:
            return fc.field_name

    return None


def validate_registry_completeness() -> None:
    """Assert FieldRegistry covers every domain appearing in the intent catalog.

    Raises StartupIntegrityError if any domain from the intent catalog has no
    fields registered in FIELD_REGISTRY_BY_DOMAIN.

    Called at startup to catch accidental registry gaps early.
    """
    from app.llm.graph.intent_catalog import INTENT_CATALOG

    catalog_domains: set[str] = {entry.domain for entry in INTENT_CATALOG}

    for domain in catalog_domains:
        fields = FIELD_REGISTRY_BY_DOMAIN.get(domain, {})
        if not fields:
            raise StartupIntegrityError(
                f"FieldRegistry is incomplete: domain '{domain}' has no registered fields "
                f"but appears in INTENT_CATALOG. Add fields for this domain to field_registry.py."
            )
        logger.debug("FieldRegistry domain '%s' OK — %d fields registered", domain, len(fields))
