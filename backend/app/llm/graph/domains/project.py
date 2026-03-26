"""ProjectAgent — 6 PRMS project intent SQL templates."""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent
from app.llm.graph.state import GraphState


class ProjectAgent(BaseDomainAgent):
    async def _run_intent(self, intent: str, params: dict[str, Any], connector: Any, state: GraphState) -> tuple[str, Any]:
        t = state["timeout_seconds"]
        m = state["max_rows"]

        if intent == "active_projects":
            sql = (
                "SELECT p.ProjectId, p.ProjectName, p.StartDate, p.EndDate, c.ClientName "
                "FROM Project p JOIN Client c ON p.ClientId = c.ClientId "
                "JOIN Status st ON p.StatusId = st.StatusId AND st.ReferenceId = 2 "
                "WHERE st.StatusName = 'Active'"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "project_by_client":
            name = params.get("resource_name", params.get("client_name", ""))
            sql = (
                "SELECT p.ProjectName, p.StartDate, p.EndDate "
                "FROM Project p JOIN Client c ON p.ClientId = c.ClientId "
                "WHERE c.ClientName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "project_budget":
            name = params.get("resource_name", params.get("project_name", ""))
            sql = (
                "SELECT p.ProjectName, p.Budget, p.BudgetUtilized "
                "FROM Project p WHERE p.ProjectName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "project_resources":
            name = params.get("resource_name", params.get("project_name", ""))
            sql = (
                "SELECT p.ProjectName, r.ResourceName, pr.BillingRate, pr.StartDate "
                "FROM Project p "
                "JOIN ProjectResource pr ON p.ProjectId = pr.ProjectId "
                "JOIN Resource r ON pr.ResourceId = r.ResourceId "
                "WHERE p.ProjectName LIKE ? AND pr.IsActive = 1"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "project_timeline":
            name = params.get("resource_name", params.get("project_name", ""))
            sql = (
                "SELECT ProjectName, StartDate, EndDate, "
                "DATEDIFF(day, StartDate, EndDate) AS DurationDays "
                "FROM Project WHERE ProjectName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "overdue_projects":
            sql = (
                "SELECT p.ProjectId, p.ProjectName, p.EndDate, c.ClientName "
                "FROM Project p JOIN Client c ON p.ClientId = c.ClientId "
                "JOIN Status st ON p.StatusId = st.StatusId AND st.ReferenceId = 2 "
                "WHERE p.EndDate < GETDATE() AND st.StatusName != 'Completed'"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"ProjectAgent: unknown intent '{intent}'")

        return sql, result
