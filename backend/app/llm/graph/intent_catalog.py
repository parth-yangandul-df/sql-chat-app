"""Static 24-intent catalog for PRMS domain tool routing.

Intents are pre-embedded at startup via ensure_catalog_embedded() so
the first query does not pay the embedding cost.
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
    fallback_intent: str | None = None         # Broader/related intent to try on 0-row result


INTENT_CATALOG: list[IntentEntry] = [
    # ── Resource (9) ──────────────────────────────────────────────────────
    IntentEntry("active_resources", "resource", "show active resources list"),
    IntentEntry("resource_by_skill", "resource", "find resources with a specific skill"),
    IntentEntry("resource_utilization", "resource", "resource utilization rate or billable hours"),
    IntentEntry("resource_billing_rate", "resource", "resource billing rate or cost rate"),
    IntentEntry("resource_availability", "resource", "resource availability or bench resources"),
    IntentEntry("resource_project_assignments", "resource", "which projects is a resource assigned to"),
    IntentEntry("resource_timesheet_summary", "resource", "timesheet hours logged by a resource"),
    IntentEntry("overallocated_resources", "resource", "resources working more than capacity or overallocated"),
    IntentEntry("resource_skills_list", "resource", "list all skills for a resource"),

    # ── Client (5) ────────────────────────────────────────────────────────
    IntentEntry("active_clients", "client", "show active clients"),
    IntentEntry("client_projects", "client", "list projects for a specific client"),
    IntentEntry("client_revenue", "client", "revenue or billing amount for a client"),
    IntentEntry("client_status", "client", "client status or account status"),
    IntentEntry("top_clients_by_revenue", "client", "top clients ranked by revenue or billing"),

    # ── Project (6) ───────────────────────────────────────────────────────
    IntentEntry("active_projects", "project", "show active or ongoing projects"),
    IntentEntry("project_by_client", "project", "projects belonging to a specific client"),
    IntentEntry("project_budget", "project", "project budget or budget utilization"),
    IntentEntry("project_resources", "project", "resources assigned to a project"),
    IntentEntry("project_timeline", "project", "project start date end date or timeline"),
    IntentEntry("overdue_projects", "project", "projects past due date or overdue"),

    # ── Timesheet (4) ─────────────────────────────────────────────────────
    IntentEntry("approved_timesheets", "timesheet", "approved timesheet entries"),
    IntentEntry("timesheet_by_period", "timesheet", "timesheet hours for a date range or period"),
    IntentEntry("unapproved_timesheets", "timesheet", "pending or unapproved timesheet entries"),
    IntentEntry("timesheet_by_project", "timesheet", "timesheet hours logged against a specific project"),
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
