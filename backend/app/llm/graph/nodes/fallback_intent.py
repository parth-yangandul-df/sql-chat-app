"""run_fallback_intent node — re-runs a sibling intent's SQL when primary returns 0 rows.

Maximum 1 hop — never chains fallback_intent to another fallback_intent.
"""

from __future__ import annotations

from typing import Any

from app.llm.graph.intent_catalog import INTENT_CATALOG
from app.llm.graph.domains.registry import DOMAIN_REGISTRY
from app.llm.graph.state import GraphState


def _get_fallback_intent_name(intent_name: str) -> str | None:
    """Return the fallback_intent name for the given intent, or None."""
    for entry in INTENT_CATALOG:
        if entry.name == intent_name:
            return entry.fallback_intent
    return None


async def run_fallback_intent(state: GraphState) -> dict[str, Any]:
    """Run the fallback intent SQL for the current domain (1 hop max)."""
    fallback_name = _get_fallback_intent_name(state["intent"] or "")
    if not fallback_name:
        # No fallback configured — return 0-row result so routing continues to llm_fallback
        from app.connectors.base_connector import QueryResult
        empty = QueryResult(
            columns=[], column_types=[], rows=[], row_count=0,
            execution_time_ms=0.0, truncated=False,
        )
        return {"result": empty, "sql": None}

    # Re-run using the same domain agent with the fallback intent name
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        "0-row result for intent=%s, trying fallback_intent=%s",
        state["intent"], fallback_name,
    )

    # Build a modified state with the fallback intent name substituted
    fallback_state = {**state, "intent": fallback_name}
    domain = state["domain"]
    if not domain or domain not in DOMAIN_REGISTRY:
        from app.connectors.base_connector import QueryResult
        empty = QueryResult(
            columns=[], column_types=[], rows=[], row_count=0,
            execution_time_ms=0.0, truncated=False,
        )
        return {"result": empty, "sql": None}

    agent = DOMAIN_REGISTRY[domain]()
    updates = await agent.execute(fallback_state)  # type: ignore[arg-type]
    # Keep llm_model reflecting the fallback intent that actually ran
    return updates


def route_after_domain_tool(state: GraphState) -> str:
    """Conditional edge after run_domain_tool."""
    result = state.get("result")
    if result and result.row_count > 0:
        return "interpret_result"
    # 0 rows — check for fallback_intent
    fallback_name = _get_fallback_intent_name(state.get("intent") or "")
    if fallback_name:
        return "run_fallback_intent"
    return "llm_fallback"


def route_after_fallback_intent(state: GraphState) -> str:
    """Conditional edge after run_fallback_intent (1 hop max — no further chaining)."""
    result = state.get("result")
    if result and result.row_count > 0:
        return "interpret_result"
    return "llm_fallback"
