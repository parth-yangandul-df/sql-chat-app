"""Static 24-intent catalog for PRMS domain tool routing.

Intents are pre-embedded at startup via ensure_catalog_embedded() so
the first query does not pay the embedding cost.

Active domains (24 entries):
  resource   (6) — org-wide resource data
  client     (3) — client/account data
  project    (6) — project data
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
    # ── Resource (6 active) ───────────────────────────────────────────────
    # Broadest entries keep fallback_intent=None (nothing broader to fall back to)
    IntentEntry("active_resources", "resource", "show active resources list", fallback_intent=None),
    IntentEntry("benched_resources", "resource", "show benched resources list", fallback_intent=None),

    IntentEntry("resource_by_skill", "resource", "find or filter resources by a specific skill or technology they know use or work with", fallback_intent="active_resources"),
    #IntentEntry("resource_utilization", "resource", "resource utilization rate or billable hours"),
    #IntentEntry("resource_billing_rate", "resource", "resource billing rate or cost rate"),
    IntentEntry("resource_availability", "resource", "resources not assigned to any active project or currently unallocated", fallback_intent="active_resources"),
    IntentEntry("resource_project_assignments", "resource", "which projects is a resource assigned to", fallback_intent="active_resources"),
    #IntentEntry("resource_timesheet_summary", "resource", "timesheet hours logged by a resource"),
    IntentEntry("resource_skills_list", "resource", "list all skills or technologies for a specific named resource", fallback_intent="active_resources"),

    # ── Client (3 active) ─────────────────────────────────────────────────
    IntentEntry("active_clients", "client", "show all active clients or list current client accounts", fallback_intent=None),
    IntentEntry("client_projects", "client", "list all projects associated with a specific client or account", fallback_intent="active_clients"),
    IntentEntry("client_status", "client", "check the active or inactive status of a specific client or account", fallback_intent="active_clients"),

    # ── Project (6 active) ────────────────────────────────────────────────
    IntentEntry("active_projects", "project", "show all active or currently ongoing projects with their client names", fallback_intent=None),
    IntentEntry("project_by_client", "project", "show projects for a specific client including project manager start date end date and status", fallback_intent="active_projects"),
    IntentEntry("project_budget", "project", "show budget or budget utilization for a specific project", fallback_intent="active_projects"),
    IntentEntry("project_resources", "project", "list all resources or employees assigned to a specific project with their role allocation and billable status", fallback_intent="active_projects"),
    IntentEntry("project_timeline", "project", "show start date end date and duration in days for a specific project", fallback_intent="active_projects"),
    IntentEntry("overdue_projects", "project", "show projects whose end date has passed and are not yet marked as completed", fallback_intent="active_projects"),

    # ── Timesheet (4 active) ──────────────────────────────────────────────
    IntentEntry("approved_timesheets", "timesheet", "approved timesheet entries", fallback_intent=None),
    IntentEntry("timesheet_by_period", "timesheet", "timesheet hours for a date range or period", fallback_intent="approved_timesheets"),
    IntentEntry("unapproved_timesheets", "timesheet", "pending or unapproved timesheet entries", fallback_intent="approved_timesheets"),
    IntentEntry("timesheet_by_project", "timesheet", "timesheet hours logged against a specific project", fallback_intent="approved_timesheets"),

    # ── User Self (5 active) — scoped to the authenticated user's own data ─
    IntentEntry("my_projects", "user_self", "which projects am I currently assigned to or working on", fallback_intent=None),
    IntentEntry("my_allocation", "user_self", "what is my percentage allocation or how much am I allocated across my projects", fallback_intent="my_projects"),
    IntentEntry("my_timesheets", "user_self", "show my timesheet entries or hours I have logged including activity category and effort hours", fallback_intent="my_projects"),
    IntentEntry("my_skills", "user_self", "what skills do I have or list my skill set and years of experience", fallback_intent="my_projects"),
    IntentEntry("my_utilization", "user_self", "what are my total hours logged per project or what is my effort utilization", fallback_intent="my_timesheets"),
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
