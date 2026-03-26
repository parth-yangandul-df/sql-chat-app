"""DOMAIN_REGISTRY and run_domain_tool LangGraph node."""

from __future__ import annotations

import logging
from typing import Any

from app.llm.graph.domains.client import ClientAgent
from app.llm.graph.domains.project import ProjectAgent
from app.llm.graph.domains.resource import ResourceAgent
from app.llm.graph.domains.timesheet import TimesheetAgent
from app.llm.graph.state import GraphState

logger = logging.getLogger(__name__)

DOMAIN_REGISTRY: dict[str, type] = {
    "resource": ResourceAgent,
    "client": ClientAgent,
    "project": ProjectAgent,
    "timesheet": TimesheetAgent,
}


async def run_domain_tool(state: GraphState) -> dict[str, Any]:
    """LangGraph node: dispatch to the correct domain agent."""
    domain = state.get("domain")
    intent = state.get("intent")
    logger.info("domain_tool: domain=%s intent=%s", domain, intent)

    if domain not in DOMAIN_REGISTRY:
        raise ValueError(f"run_domain_tool: unknown domain '{domain}'")
    agent_class = DOMAIN_REGISTRY[domain]
    agent = agent_class()
    try:
        result = await agent.execute(state)
        row_count = result.get("result").row_count if result.get("result") else 0
        error = result.get("error")
        logger.info("domain_tool: domain=%s intent=%s rows=%d error=%r", domain, intent, row_count, error)
        return result
    except Exception as e:
        logger.error("domain_tool: domain=%s intent=%s EXCEPTION: %s", domain, intent, e, exc_info=True)
        raise
