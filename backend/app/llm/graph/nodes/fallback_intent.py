"""run_fallback_intent node — re-runs a sibling intent's SQL when primary returns 0 rows.

Maximum 1 hop — never chains fallback_intent to another fallback_intent.
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.graph.nodes.sql_compiler import FALLBACK_INTENTS
from app.llm.graph.domains.registry import DOMAIN_REGISTRY
from app.llm.graph.state import GraphState

logger = logging.getLogger(__name__)


def _get_fallback_intent_name(intent_name: str) -> str | None:
    """Return the fallback_intent name for the given intent, or None."""
    return FALLBACK_INTENTS.get(intent_name)


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
    # NEW: Check for error first — permission_denied returns error, not empty result
    error = state.get("error")
    if error:
        logger.warning("route_after_domain_tool: error=%r → interpret_result", error)
        return "interpret_result"
    result = state.get("result")
    row_count = result.row_count if result else 0
    fallback_name = _get_fallback_intent_name(state.get("intent") or "")
    if result and result.row_count > 0:
        logger.info("route_after_domain_tool: rows=%d → interpret_result", row_count)
        return "interpret_result"
    # 0 rows — check for fallback_intent
    if fallback_name:
        logger.info("route_after_domain_tool: rows=0 fallback_intent=%s → run_fallback_intent", fallback_name)
        return "run_fallback_intent"
    logger.warning("route_after_domain_tool: rows=0 no fallback_intent → llm_fallback (domain tool returned empty result)")
    return "llm_fallback"


def route_after_fallback_intent(state: GraphState) -> str:
    """Conditional edge after run_fallback_intent (1 hop max — no further chaining)."""
    result = state.get("result")
    if result and result.row_count > 0:
        return "interpret_result"
    return "llm_fallback"
