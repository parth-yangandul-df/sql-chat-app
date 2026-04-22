"""DOMAIN_REGISTRY and run_domain_tool LangGraph node."""

from __future__ import annotations

import logging
from typing import Any

from app.llm.graph.domains.client import ClientAgent
from app.llm.graph.domains.project import ProjectAgent
from app.llm.graph.domains.resource import ResourceAgent
from app.llm.graph.domains.timesheet import TimesheetAgent
from app.llm.graph.domains.user_self import UserSelfAgent
from app.llm.graph.state import GraphState

logger = logging.getLogger(__name__)

DOMAIN_REGISTRY: dict[str, type] = {
    "resource": ResourceAgent,
    "client": ClientAgent,
    "project": ProjectAgent,
    "timesheet": TimesheetAgent,
    "user_self": UserSelfAgent,
}


async def run_domain_tool(state: GraphState) -> dict[str, Any]:
    """LangGraph node: dispatch to the correct domain agent."""
    domain = state.get("domain")
    intent = state.get("intent")
    logger.info("domain_tool: domain=%s intent=%s", domain, intent)

    if not domain or domain not in DOMAIN_REGISTRY:
        logger.warning("run_domain_tool: domain=%s blocked by RBAC or invalid, returning permission_denied", domain)
        return {
            "result": None,
            "error": "Permission denied: you do not have access to this data",
            "sql": None,
            "row_count": 0,
        }
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
        from app.connectors.base_connector import QueryResult
        return {
            "result": QueryResult(
                columns=[], column_types=[], rows=[], row_count=0,
                execution_time_ms=0.0, truncated=False,
            ),
            "error": str(e),
            "sql": None,
        }
