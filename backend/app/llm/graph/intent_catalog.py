"""Static 27-intent catalog for PRMS domain tool routing.

Intents are pre-embedded at startup via ensure_catalog_embedded() so
the first query does not pay the embedding cost.

Active domains (27 entries):
  resource   (8) — org-wide resource data
  client     (3) — client/account data
  project    (7) — project data
  timesheet  (4) — timesheet data
  user_self  (5) — data scoped to the authenticated user's resource_id

fallback_intent: when a parameterized domain tool returns 0 rows, the
pipeline retries with this broader intent (1 hop max) before escalating
to the LLM fallback. Broadest entries per domain keep fallback_intent=None.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.services.embedding_service import embed_text


@dataclass
class IntentEntry:
    name: str          # Snake-case identifier, e.g. "active_resources"
    domain: str        # "resource" | "client" | "project" | "timesheet"
    description: str   # Natural-language phrase used for embedding
    embedding: list[float] = field(default_factory=list, repr=False)
    # Placeholder fields — not wired in this phase; reserved for future use
    sql_fallback_template: str | None = None  # Run when param extraction fails but confidence is high
    fallback_intent: str | None = None         # Broader/related intent to try on 0-row result (CTX-04)


INTENT_CATALOG: list[IntentEntry] = [
    # ── Resource (7 active) ───────────────────────────────────────────────
    # Broadest entries keep fallback_intent=None (nothing broader to fall back to)
    IntentEntry("active_resources", "resource",
        "show all active resources employees or staff members — list everyone currently active in the organization",
        fallback_intent=None),
    IntentEntry("benched_resources", "resource",
        "show all benched resources or employees on the bench — complete list of ALL staff not currently assigned, no skill filter",
        fallback_intent=None),
    IntentEntry("benched_by_skill", "resource",
        "find benched resources who have a specific skill — benched employees who know Python Java .NET React Angular SQL or any named technology",
        fallback_intent="benched_resources"),

    IntentEntry("resource_by_skill", "resource",
        "find resources employees or developers who know a specific programming language framework or tool — Python Java React Angular SQL .NET",
        fallback_intent="active_resources"),
    #IntentEntry("resource_utilization", "resource", "resource utilization rate or billable hours"),
    #IntentEntry("resource_billing_rate", "resource", "resource billing rate or cost rate"),
    IntentEntry("resource_availability", "resource",
        "find available or unallocated resources employees not assigned to any project — free or open for new work",
        fallback_intent="active_resources"),
    IntentEntry("resource_project_assignments", "resource",
        "show which projects a specific named resource or employee is currently working on or assigned to",
        fallback_intent="active_resources"),
    #IntentEntry("resource_timesheet_summary", "resource", "timesheet hours logged by a resource"),
    IntentEntry("resource_skills_list", "resource",
        "list all the technical skills and experience of one specific named resource person or employee",
        fallback_intent="active_resources"),
    IntentEntry("reports_to", "resource",
        "show who reports to a specific manager or person — direct reports subordinates team under a manager",
        fallback_intent="active_resources"),

    # ── Client (3 active) ─────────────────────────────────────────────────
    IntentEntry("active_clients", "client",
        "show all active clients list all current client accounts or customer names",
        fallback_intent=None),
    IntentEntry("client_projects", "client",
        "list projects for a specific named client — what projects does this particular client have running",
        fallback_intent="active_clients"),
    IntentEntry("client_status", "client",
        "check whether a specific client or account is active or inactive — client status lookup",
        fallback_intent="active_clients"),

    # ── Project (7 active) ────────────────────────────────────────────────
    IntentEntry("active_projects", "project",
        "show all active ongoing projects across the organization — full project list not filtered by client",
        fallback_intent=None),
    IntentEntry("project_by_client", "project",
        "show all projects belonging to a specific named client or company — filter projects by client name",
        fallback_intent="active_projects"),
    IntentEntry("project_budget", "project",
        "show the budget spend cost or financial utilization for a specific named project — how much budget is used",
        fallback_intent="active_projects"),
    IntentEntry("project_resources", "project",
        "list all employees team members or staff assigned to a specific project — who is working on this project with their role and allocation",
        fallback_intent="active_projects"),
    IntentEntry("project_timeline", "project",
        "show the start date end date and duration timeline schedule for a specific named project",
        fallback_intent="active_projects"),
    IntentEntry("project_status", "project",
        "what is the current status of a specific named project — check if a project is active completed on hold or its health",
        fallback_intent="active_projects"),
    IntentEntry("overdue_projects", "project",
        "show overdue late or delayed projects that are past their end date and still not completed — projects running behind schedule",
        fallback_intent="active_projects"),

    # ── Timesheet (4 active) ──────────────────────────────────────────────
    IntentEntry("approved_timesheets", "timesheet",
        "show approved timesheet entries — hours that have been reviewed and approved by a manager",
        fallback_intent=None),
    IntentEntry("timesheet_by_period", "timesheet",
        "show timesheet hours logged during a specific date range period week or month — filter by dates",
        fallback_intent="approved_timesheets"),
    IntentEntry("unapproved_timesheets", "timesheet",
        "show pending unapproved or unreviewed timesheets — entries waiting for manager approval",
        fallback_intent="approved_timesheets"),
    IntentEntry("timesheet_by_project", "timesheet",
        "show timesheet hours logged for a specific named project — how many hours were worked on this project",
        fallback_intent="approved_timesheets"),

    # ── User Self (5 active) — scoped to the authenticated user's own data ─
    IntentEntry("my_projects", "user_self",
        "which projects am I personally assigned to — show my own current project assignments, projects I myself am working on",
        fallback_intent=None),
    IntentEntry("my_allocation", "user_self",
        "what is my allocation percentage — how much am I allocated across my projects or what is my utilization capacity",
        fallback_intent="my_projects"),
    IntentEntry("my_timesheets", "user_self",
        "show my timesheet entries — hours I have logged my activities categories and effort across projects",
        fallback_intent="my_projects"),
    IntentEntry("my_skills", "user_self",
        "what are my skills — list my technical skills and years of experience my skill set",
        fallback_intent="my_projects"),
    IntentEntry("my_utilization", "user_self",
        "what is my total effort or hours logged per project — my utilization rate and how I spend my time",
        fallback_intent="my_timesheets"),
]

_embed_lock = asyncio.Lock()
_catalog_embedded = False


async def ensure_catalog_embedded() -> None:
    """Pre-embed all catalog entries. Idempotent; safe to call multiple times."""
    global _catalog_embedded
    async with _embed_lock:
        if _catalog_embedded:
            return
        for entry in INTENT_CATALOG:
            if not entry.embedding:
                entry.embedding = await embed_text(entry.description)
        _catalog_embedded = True


def get_catalog_embeddings() -> list[list[float]]:
    """Return embeddings for all catalog entries (must call ensure_catalog_embedded first)."""
    return [e.embedding for e in INTENT_CATALOG]
