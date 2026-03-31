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
                "SELECT p.ProjectId, p.ProjectName, c.ClientName "
                "FROM Project p JOIN Client c ON p.ClientId = c.ClientId "
                "JOIN Status st ON p.ProjectStatusId = st.StatusId AND st.ReferenceId = 2 "
                "WHERE st.StatusName = 'Active'"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "project_by_client": # done and ready for improvement
            name = params.get("resource_name", params.get("client_name", ""))
            sql = (
                "SELECT p.ProjectName as [Project Name], c.clientname as [Client Name], cast(p.StartDate as date) as [Start date], cast(p.EndDate as date) as [End date],r.ResourceName as [Project Manager], s.StatusName as Status "
                "FROM Project p JOIN Client c ON p.ClientId = c.ClientId "
				"JOIN Status s ON s.StatusId = p.ProjectStatusId "
				"JOIN Resource r ON r.ResourceId = p.ProjectManagerId "
                "WHERE c.ClientName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "project_budget": # budget not in db
            name = params.get("resource_name", params.get("project_name", ""))
            sql = (
                "SELECT p.ProjectName, p.Budget, p.BudgetUtilized "
                "FROM Project p WHERE p.ProjectName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "project_resources": # done and ready for improvement
            name = params.get("project_name", "")
            sql = (
                "SELECT p.ProjectName, c.ClientId, r.ResourceName, tc.TechCategoryName, pr.Billable, pr.ResourceRole, pr.PercentageAllocation "
                "FROM Project p "
                "JOIN ProjectResource pr ON p.ProjectId = pr.ProjectId "
                "JOIN Resource r ON pr.ResourceId = r.ResourceId "
                "JOIN TechCategory tc ON tc.TechCategoryId = r.TechCategoryId "
                "JOIN Client c ON c.ClientId = pr.ClientId "
                "WHERE p.ProjectName LIKE ? AND pr.IsActive = 1"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "project_timeline": # done and ready for improvement
            name = params.get("resource_name", params.get("project_name", ""))
            sql = (
                "SELECT ProjectName, cast(StartDate as Date) as [Start Date],COALESCE(CONVERT(VARCHAR(10), EndDate, 120), 'NA') AS [End Date], "
                "COALESCE(CAST(DATEDIFF(DAY, StartDate, EndDate) AS VARCHAR(10)), 'NA') AS DurationDays "
                "FROM Project WHERE ProjectName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "overdue_projects": # ask logic
            sql = (
                "SELECT p.ProjectId, p.ProjectName, p.EndDate, c.ClientName "
                "FROM Project p JOIN Client c ON p.ClientId = c.ClientId "
                "JOIN Status st ON p.ProjectStatusId = st.StatusId AND st.ReferenceId = 2 "
                "WHERE p.EndDate < GETDATE() AND st.StatusName != 'Completed'"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"ProjectAgent: unknown intent '{intent}'")

        return sql, result
