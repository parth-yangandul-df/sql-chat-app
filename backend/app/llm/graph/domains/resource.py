"""ResourceAgent — 9 PRMS resource intent SQL templates."""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent
from app.llm.graph.state import GraphState


class ResourceAgent(BaseDomainAgent):
    async def _run_intent(self, intent: str, params: dict[str, Any], connector: Any, state: GraphState) -> tuple[str, Any]:
        t = state["timeout_seconds"]
        m = state["max_rows"]

        if intent == "active_resources":
            sql = "SELECT ResourceId, ResourceName, EmailId, IsActive FROM Resource WHERE IsActive = 1"
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "resource_by_skill":
            skill = params.get("skill", "")
            sql = (
                "SELECT Employeeid, ResourceName  FROM Resource WHERE PrimarySkill LIKE ? OR SecondarySkill LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{skill}%", f"%{skill}%"), timeout_seconds=t, max_rows=m)
        elif intent == "resource_utilization":
            sql = (
              "SELECT DISTINCT r.ResourceId, r.ResourceName, ts.Title, ts.Category, ts.activity, "
              "SUM(ts.[Effort Hours]) AS TotalHours "
              "FROM Resource r "
              "JOIN TS_Timesheet_Report ts ON r.EmployeeId = ts.[Emp ID] "
              "GROUP BY r.ResourceId, r.ResourceName, ts.Project, ts.Category, ts.activity, ts.Title "
              "ORDER BY TotalHours DESC"
           )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)
        elif intent == "resource_billing_rate":
            sql = (
                "SELECT r.ResourceId, r.ResourceName, pr.Rate, p.ProjectName "
                "FROM Resource r "
                "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                "JOIN Project p ON pr.ProjectId = p.ProjectId "
                "WHERE r.IsActive = 1"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)
        elif intent == "resource_availability":
            sql = (
                "SELECT ResourceId, ResourceName, EmailId FROM Resource "
                "WHERE IsActive = 1 "
                "AND ResourceId NOT IN (SELECT DISTINCT ResourceId FROM ProjectResource WHERE IsActive = 1)"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)
        elif intent == "resource_project_assignments":
            name = params.get("resource_name", "")
            sql = (
                "SELECT r.ResourceName, p.ProjectName, CAST(pr.StartDate AS DATE) AS StartDate, "
                "CAST(pr.EndDate AS DATE) AS EndDate FROM Resource r "
                "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                "JOIN Project p ON pr.ProjectId = p.ProjectId "
                "WHERE r.ResourceName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)
        elif intent == "resource_timesheet_summary":
            name = params.get("resource_name", "")
            sql = (
                "SELECT r.ResourceName, SUM(ts.[Effort Hours]) AS TotalHours, ts.[File Date], ts.Title "
                "FROM Resource r "
                "JOIN TS_Timesheet_Report ts ON r.EmployeeId = ts.[Emp ID] "
                "WHERE r.ResourceName LIKE ? "
                "GROUP BY r.ResourceName, ts.[File Date], ts.Title "
                "ORDER BY ts.[File Date] ASC"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)
        elif intent == "overallocated_resources":
            sql = (
                "SELECT r.ResourceId, r.ResourceName, COUNT(pr.ProjectId) AS ProjectCount "
                "FROM Resource r "
                "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                "WHERE pr.IsActive = 1 "
                "GROUP BY r.ResourceId, r.ResourceName "
                "HAVING COUNT(pr.ProjectId) > 1 "
                "ORDER BY ProjectCount DESC"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)
        elif intent == "resource_skills_list":
            name = params.get("resource_name", "")
            sql = (
                "SELECT DISTINCT r.ResourceName, s.Name, rs.SkillExperience "
                "FROM Resource r "
                "JOIN PA_ResourceSkills rs ON r.ResourceId = rs.ResourceId "
                "JOIN PA_Skills s ON rs.SkillId = s.SkillId "
                "WHERE r.ResourceName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"ResourceAgent: unknown intent '{intent}'")

        return sql, result
