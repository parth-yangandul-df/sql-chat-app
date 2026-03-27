"""ClientAgent — 5 PRMS client intent SQL templates."""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent
from app.llm.graph.state import GraphState


class ClientAgent(BaseDomainAgent):
    async def _run_intent(self, intent: str, params: dict[str, Any], connector: Any, state: GraphState) -> tuple[str, Any]:
        t = state["timeout_seconds"]
        m = state["max_rows"]

        if intent == "active_clients":
            sql = (
                "SELECT c.ClientId, c.ClientName, c.Description, c.CountryId "
                "FROM Client c "
                "JOIN Status st ON c.StatusId = st.StatusId AND st.ReferenceId = 1 "
                "WHERE st.StatusName = 'Active'"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "client_projects":
            name = params.get("resource_name", params.get("client_name", ""))
            sql = (
                "SELECT c.ClientName, p.ProjectName, p.StartDate, p.EndDate "
                "FROM Client c "
                "JOIN Project p ON c.ClientId = p.ClientId "
                "WHERE c.ClientName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        #elif intent == "client_revenue":
        #    name = params.get("resource_name", params.get("client_name", ""))
        #    sql = (
        #        "SELECT c.ClientName, SUM(pr.BillingRate * ts.Hours) AS TotalRevenue "
        #        "FROM Client c "
        #        "JOIN Project p ON c.ClientId = p.ClientId "
        #        "JOIN ProjectResource pr ON p.ProjectId = pr.ProjectId "
        #        "JOIN Timesheet ts ON pr.ResourceId = ts.ResourceId AND ts.ProjectId = p.ProjectId "
        #        "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
        #        "AND c.ClientName LIKE ? "
        #        "GROUP BY c.ClientName"
        #    )
        #    result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "client_status":
            name = params.get("resource_name", params.get("client_name", ""))
            sql = (
                "SELECT c.ClientName, st.StatusName "
                "FROM Client c "
                "JOIN Status st ON c.StatusId = st.StatusId AND st.ReferenceId = 1 "
                "WHERE c.ClientName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "top_clients_by_revenue": # baadme
            sql = (
                "SELECT TOP 10 c.ClientName, SUM(pr.BillingRate * ts.Hours) AS TotalRevenue "
                "FROM Client c "
                "JOIN Project p ON c.ClientId = p.ClientId "
                "JOIN ProjectResource pr ON p.ProjectId = pr.ProjectId "
                "JOIN Timesheet ts ON pr.ResourceId = ts.ResourceId AND ts.ProjectId = p.ProjectId "
                "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
                "GROUP BY c.ClientName "
                "ORDER BY TotalRevenue DESC"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"ClientAgent: unknown intent '{intent}'")

        return sql, result
