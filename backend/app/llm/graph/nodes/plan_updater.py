"""plan_updater node — filter accumulation rules across conversation turns.

Receives the current domain, intent, and newly extracted filters (from filter_extractor),
then creates or updates the QueryPlan in GraphState.

Accumulation rules (driven by FieldRegistry multi_value flag):
  - multi_value=True (e.g. skill):   append new values to existing list
  - multi_value=False (e.g. date):   replace with new value (last-wins)
  - Topic switch (domain or intent changes): fresh QueryPlan, old filters discarded
  - No domain/intent (LLM fallback): query_plan remains None
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.graph.nodes.field_registry import lookup_field
from app.llm.graph.query_plan import FilterClause, QueryPlan
from app.llm.graph.state import GraphState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NO_FILTER_INTENTS — intents with fully self-contained SQL (no dynamic filters)
# ---------------------------------------------------------------------------
NO_FILTER_INTENTS: frozenset[str] = frozenset({
    "benched_resources",      # hardcoded WHERE p.ProjectId = 119
    "active_resources",       # hardcoded WHERE r.IsActive = 1 AND r.statusid = 8
    "resource_availability",  # hardcoded subquery exclusion
    "active_projects",        # hardcoded WHERE p.IsActive = 1 AND p.ProjectStatusId = 4
    "overdue_projects",       # hardcoded WHERE p.EndDate < GETDATE()
    "active_clients",         # hardcoded WHERE c.IsActive = 1 AND c.StatusId = 2
    "approved_timesheets",    # hardcoded approval flags
    "unapproved_timesheets",  # hardcoded unapproved flags
})

# ---------------------------------------------------------------------------
# Lazy import for semantic_resolver value_map normalization
# ---------------------------------------------------------------------------
try:
    from app.llm.graph.nodes.semantic_resolver import (
        get_cached_value_map,
        normalize_values_batch,
    )
except ImportError:
    get_cached_value_map = None  # type: ignore[assignment]
    normalize_values_batch = None  # type: ignore[assignment]


async def update_query_plan(state: GraphState) -> dict[str, Any]:
    """Create or update QueryPlan with accumulated filter state.

    Logic:
    1. If no domain/intent (LLM fallback path) → return {"query_plan": None}
    2. If no existing plan OR domain/intent differs (topic switch) → fresh QueryPlan
    3. Existing plan with same domain/intent → merge new filters:
       - multi_value=True: append new values to existing field's values list
       - multi_value=False: replace existing field entry with new filter (last-wins)
       - New field not in existing plan: add it
    4. (Plan 04) Normalize filter values through cached value_map before accumulation
    """
    domain: str | None = state.get("domain")
    intent: str | None = state.get("intent")
    existing_plan_dict: dict | None = state.get("query_plan")
    new_filters: list[FilterClause] = state.get("filters") or []

    # ── 1. LLM fallback path ─────────────────────────────────────────────
    if not domain or not intent:
        logger.debug("plan_updater: no domain/intent (LLM fallback path), returning None plan")
        return {"query_plan": None}
    
    # ── 1b. Self-contained intents with hardcoded WHERE clauses ───────────────
    # These intents already contain complete WHERE clauses and should not
    # receive additional filters from the pipeline
    if intent in NO_FILTER_INTENTS:
        logger.debug(
            "plan_updater: intent '%s' is self-contained with hardcoded WHERE clause, forcing empty filters",
            intent
        )
        
        # Get base SQL from params if available (e.g. _prior_sql from param_extractor)
        params: dict = state.get("params") or {}
        base_intent_sql: str = params.get("_prior_sql", "")
        
        plan = QueryPlan(
            domain=domain,
            intent=intent,
            filters=[],  # Empty filters for self-contained intents
            base_intent_sql=base_intent_sql,
            schema_version=1,
        )
        
        return {"query_plan": plan.to_api_dict()}

    # ── Plan 04: Normalize filter values through cached value_map ─────────
    if new_filters and get_cached_value_map is not None and normalize_values_batch is not None:
        try:
            value_map = get_cached_value_map()
            if value_map:
                new_filters = normalize_values_batch(new_filters, value_map)
                logger.debug(
                    "plan_updater: normalized %d filter(s) through value_map",
                    len(new_filters),
                )
        except Exception:
            logger.warning(
                "plan_updater: value_map normalization failed — using raw filter values",
                exc_info=True,
            )

    # ── 2. Topic switch detection ─────────────────────────────────────────
    if existing_plan_dict:
        existing_domain = existing_plan_dict.get("domain")
        existing_intent = existing_plan_dict.get("intent")
        topic_switch = (existing_domain != domain) or (existing_intent != intent)
    else:
        topic_switch = False

    # ── 3a. Fresh plan (no existing or topic switch) ──────────────────────
    if not existing_plan_dict or topic_switch:
        if topic_switch:
            logger.info(
                "plan_updater: topic switch detected (%s.%s → %s.%s) — fresh QueryPlan",
                existing_plan_dict.get("domain"), existing_plan_dict.get("intent"),
                domain, intent,
            )

        # Get base SQL from params if available (e.g. _prior_sql from param_extractor)
        params: dict = state.get("params") or {}
        base_intent_sql: str = params.get("_prior_sql", "")

        plan = QueryPlan(
            domain=domain,
            intent=intent,
            filters=list(new_filters),
            base_intent_sql=base_intent_sql,
            schema_version=1,
        )
        logger.debug(
            "plan_updater: created fresh QueryPlan for %s.%s with %d filter(s)",
            domain, intent, len(plan.filters),
        )
        
        # ── Log QueryPlan details ───────────────────────────────────────────
        filter_summary = ", ".join(
            f"{f.field}={f.op}:{f.values}" for f in plan.filters
        ) if plan.filters else "none"
        logger.info(
            "plan_updater: QueryPlan domain=%s intent=%s filters=[%s]",
            domain, intent, filter_summary,
        )
        
        return {"query_plan": plan.to_api_dict()}

    # ── 3b. Merge new filters into existing plan ──────────────────────────
    try:
        existing_plan = QueryPlan.from_untrusted_dict(existing_plan_dict)
    except Exception as exc:
        logger.warning(
            "plan_updater: failed to deserialize existing plan (will rebuild): %s", exc
        )
        plan = QueryPlan(
            domain=domain,
            intent=intent,
            filters=list(new_filters),
            base_intent_sql="",
            schema_version=1,
        )
        return {"query_plan": plan.to_api_dict()}

    if not new_filters:
        # No new filters this turn — return existing plan unchanged
        logger.debug("plan_updater: no new filters, preserving existing plan")
        return {"query_plan": existing_plan.to_api_dict()}

    # Merge: build a mutable dict of field_name → FilterClause for existing filters
    existing_by_field: dict[str, FilterClause] = {
        f.field: f for f in existing_plan.filters
    }

    for new_fc in new_filters:
        field_name = new_fc.field
        fc_meta = lookup_field(field_name, domain)

        if fc_meta is None:
            # Should not happen (filter_extractor validates), but be safe
            logger.warning(
                "plan_updater: field '%s' not in registry for domain '%s' — skipping",
                field_name, domain,
            )
            continue

        if field_name in existing_by_field:
            existing_fc = existing_by_field[field_name]
            if fc_meta.multi_value:
                # Append new values (no duplicates)
                combined = list(existing_fc.values)
                for v in new_fc.values:
                    if v not in combined:
                        combined.append(v)
                existing_by_field[field_name] = FilterClause(
                    field=field_name, op=existing_fc.op, values=combined
                )
                logger.debug(
                    "plan_updater: appended values to multi-value field '%s': %s",
                    field_name, combined,
                )
            else:
                # Replace (last-wins) — keep new filter as-is
                existing_by_field[field_name] = new_fc
                logger.debug(
                    "plan_updater: replaced scalar field '%s' with new value: %s",
                    field_name, new_fc.values,
                )
        else:
            # New field — add to plan
            existing_by_field[field_name] = new_fc
            logger.debug("plan_updater: added new field '%s' to plan", field_name)

    # Reconstruct plan preserving existing field order + appended new fields
    all_field_names: list[str] = list(dict.fromkeys(
        [f.field for f in existing_plan.filters] +
        [f.field for f in new_filters]
    ))
    merged_filters: list[FilterClause] = [
        existing_by_field[fn] for fn in all_field_names if fn in existing_by_field
    ]

    updated_plan = QueryPlan(
        domain=existing_plan.domain,
        intent=existing_plan.intent,
        filters=merged_filters,
        base_intent_sql=existing_plan.base_intent_sql,
        schema_version=1,
    )
    logger.debug(
        "plan_updater: merged plan for %s.%s — %d filter(s) total",
        domain, intent, len(updated_plan.filters),
    )
    return {"query_plan": updated_plan.to_api_dict()}
