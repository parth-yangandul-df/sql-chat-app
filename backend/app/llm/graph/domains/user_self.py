"""UserSelfAgent — 5 intents scoped to the authenticated user's resource_id.

All SQL templates use parameterised queries (? placeholder) with the
resource_id drawn from state["resource_id"] at runtime. The resource_id
is NEVER hardcoded — it always comes from the authenticated user's profile.

This agent is only reachable when user_role == "user" (enforced by
intent_classifier.py). Admin and manager roles are routed to the
broader domain agents (resource, project, etc.) instead.
"""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent
from app.llm.graph.state import GraphState


class UserSelfAgent(BaseDomainAgent):
    async def _run_intent(
        self, intent: str, params: dict[str, Any], connector: Any, state: GraphState
    ) -> tuple[str, Any]:
        t = state["timeout_seconds"]
        m = state["max_rows"]
        resource_id = state.get("resource_id")

        if resource_id is None:
            raise ValueError(
                "UserSelfAgent requires resource_id in GraphState — "
                "this agent should only be reached by authenticated 'user' role accounts."
            )

        if intent == "my_projects":
            sql = (
                "SELECT p.ProjectName, r.ResourceName AS [Employee Name], "
                "COALESCE(CAST(p.StartDate AS DATE), 'NA') AS [Start Date], "
                "COALESCE(CAST(p.EndDate AS DATE), 'NA') AS [End Date] "
                "FROM Project p "
                "JOIN ProjectResource pr ON p.ProjectId = pr.ProjectId "
                "JOIN Resource r ON r.ResourceId = pr.ResourceId "
                "WHERE pr.ResourceId = ? AND r.IsActive = 1"
            )
            result = await connector.execute_query(sql, params=(resource_id,), timeout_seconds=t, max_rows=m)

        elif intent == "my_allocation":
            sql = (
                "SELECT p.ProjectName, pr.PercentageAllocation, pr.StartDate, pr.EndDate "
                "FROM ProjectResource pr "
                "JOIN Project p ON pr.ProjectId = p.ProjectId "
                "WHERE pr.ResourceId = ? AND pr.IsActive = 1"
            )
            result = await connector.execute_query(sql, params=(resource_id,), timeout_seconds=t, max_rows=m)

        elif intent == "my_timesheets":
            sql = (
                "SELECT ts.Title, ts.Category, ts.Activity, ts.[Effort Hours], ts.[File Date] "
                "FROM TS_Timesheet_Report ts "
                "JOIN Resource r ON r.EmployeeId = ts.[Emp ID] "
                "WHERE CAST(r.EmployeeId AS INT) = ? "
                "ORDER BY ts.[File Date] DESC"
            )
            result = await connector.execute_query(sql, params=(resource_id,), timeout_seconds=t, max_rows=m)

        elif intent == "my_skills":
            sql = (
                "SELECT s.Name, rs.SkillExperience "
                "FROM PA_ResourceSkills rs "
                "JOIN PA_Skills s ON rs.SkillId = s.SkillId "
                "WHERE rs.ResourceId = ?"
            )
            result = await connector.execute_query(sql, params=(resource_id,), timeout_seconds=t, max_rows=m)

        elif intent == "my_utilization":
            sql = (
                "SELECT ts.Title, SUM(ts.[Effort Hours]) AS TotalHours, ts.[File Date] "
                "FROM TS_Timesheet_Report ts "
                "JOIN Resource r ON r.EmployeeId = ts.[Emp ID] "
                "WHERE CAST(r.EmployeeId AS INT) = ? "
                "GROUP BY ts.Title, ts.[File Date] "
                "ORDER BY ts.[File Date] DESC"
            )
            result = await connector.execute_query(sql, params=(resource_id,), timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"UserSelfAgent: unknown intent '{intent}'")

        return sql, result
