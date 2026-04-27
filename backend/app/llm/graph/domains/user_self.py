"""UserSelfAgent — 5 intents scoped to the authenticated user's resource_id / employee_id.

Intents that join on ResourceId (my_projects, my_allocation, my_skills) use
resource_id (integer PK). Intents that join on EmployeeId (my_timesheets,
my_utilization) use employee_id (string column) — EmployeeId is a VARCHAR,
so comparing as string without CAST is correct.

All SQL templates use parameterised queries (? placeholder) with the
appropriate ID drawn from GraphState at runtime. IDs are NEVER hardcoded —
they always come from the authenticated user's profile.

This agent is only reachable when user_role == "user" (enforced by
intent_classifier.py). Admin and manager roles are routed to the
broader domain agents (resource, project, etc.) instead.
"""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent
from app.llm.graph.state import GraphState

# Intents that use EmployeeId (string column) instead of ResourceId (integer PK)
_EMPLOYEE_ID_INTENTS: frozenset[str] = frozenset({"my_timesheets", "my_utilization"})


class UserSelfAgent(BaseDomainAgent):
    async def _run_intent(
        self, intent: str, params: dict[str, Any], connector: Any, state: GraphState
    ) -> tuple[str, Any]:
        t = state["timeout_seconds"]
        m = state["max_rows"]
        resource_id = state.get("resource_id")
        employee_id = state.get("employee_id")

        if resource_id is None and intent not in _EMPLOYEE_ID_INTENTS:
            raise ValueError(
                "UserSelfAgent requires resource_id in GraphState — "
                "this agent should only be reached by authenticated 'user' role accounts."
            )

        if intent in _EMPLOYEE_ID_INTENTS and employee_id is None:
            raise ValueError(
                f"UserSelfAgent requires employee_id in GraphState for '{intent}' — "
                "EmployeeId is a string column, not an integer ResourceId."
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
                "WHERE r.EmployeeId = ? "
                "ORDER BY ts.[File Date] DESC"
            )
            result = await connector.execute_query(sql, params=(employee_id,), timeout_seconds=t, max_rows=m)

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
                "WHERE r.EmployeeId = ? "
                "GROUP BY ts.Title, ts.[File Date] "
                "ORDER BY ts.[File Date] DESC"
            )
            result = await connector.execute_query(sql, params=(employee_id,), timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"UserSelfAgent: unknown intent '{intent}'")

        return sql, result
