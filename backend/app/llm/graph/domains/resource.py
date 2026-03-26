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
            sql = "SELECT ResourceId, ResourceName, Email, IsActive FROM Resource WHERE IsActive = 1"
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "resource_by_skill":
            skill = params.get("skill", "")
            sql = (
                "SELECT r.ResourceId, r.ResourceName, s.SkillName "
                "FROM Resource r "
                "JOIN ResourceSkill rs ON r.ResourceId = rs.ResourceId "
                "JOIN Skill s ON rs.SkillId = s.SkillId "
                "WHERE s.SkillName LIKE ? AND r.IsActive = 1"
            )
            result = await connector.execute_query(sql, params=(f"%{skill}%",), timeout_seconds=t, max_rows=m)

        elif intent == "resource_utilization":
            sql = (
                "SELECT r.ResourceId, r.ResourceName, "
                "SUM(ts.Hours) AS TotalHours "
                "FROM Resource r "
                "JOIN Timesheet ts ON r.ResourceId = ts.ResourceId "
                "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
                "GROUP BY r.ResourceId, r.ResourceName "
                "ORDER BY TotalHours DESC"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "resource_billing_rate":
            sql = (
                "SELECT r.ResourceId, r.ResourceName, pr.BillingRate "
                "FROM Resource r "
                "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                "WHERE r.IsActive = 1"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "resource_availability":
            sql = (
                "SELECT ResourceId, ResourceName, Email FROM Resource "
                "WHERE IsActive = 1 "
                "AND ResourceId NOT IN (SELECT DISTINCT ResourceId FROM ProjectResource WHERE IsActive = 1)"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "resource_project_assignments":
            name = params.get("resource_name", "")
            sql = (
                "SELECT r.ResourceName, p.ProjectName, pr.StartDate, pr.EndDate "
                "FROM Resource r "
                "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                "JOIN Project p ON pr.ProjectId = p.ProjectId "
                "WHERE r.ResourceName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "resource_timesheet_summary":
            name = params.get("resource_name", "")
            sql = (
                "SELECT r.ResourceName, SUM(ts.Hours) AS TotalHours, ts.WorkDate "
                "FROM Resource r "
                "JOIN Timesheet ts ON r.ResourceId = ts.ResourceId "
                "WHERE ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
                "AND r.ResourceName LIKE ? "
                "GROUP BY r.ResourceName, ts.WorkDate "
                "ORDER BY ts.WorkDate DESC"
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
                "SELECT r.ResourceName, s.SkillName, rs.ProficiencyLevel "
                "FROM Resource r "
                "JOIN ResourceSkill rs ON r.ResourceId = rs.ResourceId "
                "JOIN Skill s ON rs.SkillId = s.SkillId "
                "WHERE r.ResourceName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"ResourceAgent: unknown intent '{intent}'")

        return sql, result
