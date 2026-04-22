"""route_after_domain_tool — conditional edge after run_domain_tool.

Routes to interpret_result when rows were returned, llm_fallback otherwise
(0 rows or any SQL error).
"""

from __future__ import annotations

import logging

from app.llm.graph.state import GraphState

logger = logging.getLogger(__name__)


def route_after_domain_tool(state: GraphState) -> str:
    """Conditional edge after run_domain_tool.

    - rows > 0          → interpret_result
    - 0 rows or error   → llm_fallback  (LLM generates SQL from scratch)
    """
    error = state.get("error")
    if error:
        logger.warning("route_after_domain_tool: error=%r → llm_fallback", error)
        return "llm_fallback"

    result = state.get("result")
    if result and result.row_count > 0:
        logger.info("route_after_domain_tool: rows=%d → interpret_result", result.row_count)
        return "interpret_result"

    logger.warning("route_after_domain_tool: rows=0 → llm_fallback")
    return "llm_fallback"
