"""DOMAIN_REGISTRY and run_domain_tool LangGraph node."""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.client import ClientAgent
from app.llm.graph.domains.project import ProjectAgent
from app.llm.graph.domains.resource import ResourceAgent
from app.llm.graph.domains.timesheet import TimesheetAgent
from app.llm.graph.state import GraphState

DOMAIN_REGISTRY: dict[str, type] = {
    "resource": ResourceAgent,
    "client": ClientAgent,
    "project": ProjectAgent,
    "timesheet": TimesheetAgent,
}


async def run_domain_tool(state: GraphState) -> dict[str, Any]:
    """LangGraph node: dispatch to the correct domain agent."""
    domain = state.get("domain")
    if domain not in DOMAIN_REGISTRY:
        raise ValueError(f"run_domain_tool: unknown domain '{domain}'")
    agent_class = DOMAIN_REGISTRY[domain]
    agent = agent_class()
    return await agent.execute(state)
