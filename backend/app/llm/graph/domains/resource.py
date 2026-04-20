"""ResourceAgent — 9 PRMS resource intent SQL templates."""

from __future__ import annotations

import logging
from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent, _strip_order_by
from app.llm.graph.state import GraphState


class ResourceAgent(BaseDomainAgent):
    @staticmethod
    def _detect_prior_intent(prior_columns: list[str]) -> str:
        """Identify which resource intent generated the prior result set.

        Uses distinguishing column names rather than EMPID variants (both
        active_resources and benched_resources return EMPID as the alias).

        Returns the detected intent name, or "unknown" if unrecognizable.
        """
        cols_lower = {c.lower() for c in prior_columns}
        if "techcategoryname" in cols_lower:
            return "benched_resources"
        if "designation" in cols_lower:
            return "active_resources"
        # Fallback: check for other resource intent signatures
        if "billab" in cols_lower or "percentageallocation" in cols_lower:
            return "resource_project_assignments"
        if "skillexperience" in cols_lower:
            return "resource_skills_list"
        return "unknown"

    async def _run_refinement(
        self,
        prior_sql: str,
        params: dict[str, Any],
        connector: Any,
        state: GraphState,
    ) -> tuple[str, Any]:
        """Wrap prior resource SQL as subquery with a new filter.

        Supported refinement types:
        - skill: join PA_ResourceSkills/PA_Skills to filter by skill name
        - name: filter by resource name via subquery WHERE
        - designation/tech_category: filter by column value via subquery WHERE

        Falls back to base intent if no supported refinement param is found
        or if the refinement SQL fails.
        """
        logger = logging.getLogger(__name__)

        skill = params.get("skill_name", params.get("skill", ""))
        _ = params.get("_prior_columns", [])  # available for future intent detection
        t = state["timeout_seconds"]
        m = state["max_rows"]
        stripped = _strip_order_by(prior_sql)

        # --- Skill-based refinement (most common) ---
        if skill:
            # Both active_resources and benched_resources return EMPID as the
            # join key — use consistent unbracketed reference.
            sql = (
                f"SELECT prev.* "
                f"FROM ({stripped}) AS prev "
                f"JOIN Resource r2 ON r2.EmployeeId = prev.EMPID "
                f"JOIN PA_ResourceSkills rs ON rs.ResourceId = r2.ResourceId "
                f"JOIN PA_Skills s ON s.SkillId = rs.SkillId "
                f"WHERE s.Name LIKE ? OR r2.PrimarySkill LIKE ? OR r2.SecondarySkill LIKE ?"
            )
            try:
                result = await connector.execute_query(
                    sql,
                    params=(f"%{skill}%", f"%{skill}%", f"%{skill}%"),
                    timeout_seconds=t,
                    max_rows=m,
                )
                return sql, result
            except Exception as e:
                logger.warning(
                    "resource: skill refinement failed (%s), falling back to base intent", e,
                )
                # Fall through to base intent below

        # --- Name-based refinement ---
        name = params.get("resource_name", "")
        if name:
            sql = (
                f"SELECT prev.* "
                f"FROM ({stripped}) AS prev "
                f"WHERE prev.[Name] LIKE ?"
            )
            try:
                result = await connector.execute_query(
                    sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m,
                )
                return sql, result
            except Exception as e:
                logger.warning(
                    "resource: name refinement failed (%s), falling back to base intent", e,
                )

        # --- Designation filter (active_resources) ---
        designation = params.get("designation", "")
        if designation:
            sql = (
                f"SELECT prev.* "
                f"FROM ({stripped}) AS prev "
                f"WHERE prev.[Designation] LIKE ?"
            )
            try:
                result = await connector.execute_query(
                    sql, params=(f"%{designation}%",), timeout_seconds=t, max_rows=m,
                )
                return sql, result
            except Exception as e:
                logger.warning(
                    "resource: designation refinement failed (%s), falling back to base intent", e,
                )

        # --- Tech category filter (benched_resources) ---
        tech_category = params.get("tech_category", "")
        if tech_category:
            sql = (
                f"SELECT prev.* "
                f"FROM ({stripped}) AS prev "
                f"WHERE prev.TechCategoryName LIKE ?"
            )
            try:
                result = await connector.execute_query(
                    sql, params=(f"%{tech_category}%",), timeout_seconds=t, max_rows=m,
                )
                return sql, result
            except Exception as e:
                logger.warning(
                    "resource: tech_category refinement failed (%s), falling back to base intent", e,
                )

        # --- No supported refinement param → base intent ---
        intent = state["intent"] or ""
        logger.info(
            "resource: no supported refinement param (skill=%r, name=%r), running base intent=%s",
            skill, name, intent,
        )
        return await self._run_intent(intent, params, connector, state)

    async def _run_intent(self, intent: str, params: dict[str, Any], connector: Any, state: GraphState) -> tuple[str, Any]:
        t = state["timeout_seconds"]
        m = state["max_rows"]

        if intent == "active_resources": # done and ready for improvement
            sql = "SELECT r.EmployeeId as [EMPID], r.ResourceName as [Name], r.EmailId, dr.designationname as [Designation] FROM Resource r " \
                  "JOIN Designation dr ON r.designationid = dr.designationid " \
                  "WHERE r.IsActive = 1 and r.statusid = 8 order by r.resourcename asc"
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "benched_resources": # done and ready for improvement
            sql = (
                    "SELECT DISTINCT r.employeeid as [EMPID], r.ResourceName as [Name], r.EmailId, t.TechCategoryName "
                    "FROM Resource r "
                    "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                    "JOIN Project p ON pr.ProjectId = p.ProjectId "
                    "JOIN TechCatagory t ON t.TechCategoryId = r.TechCategoryId "
                    "WHERE p.ProjectId = 119 "
                    "ORDER BY r.ResourceName"
            )

            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "benched_by_skill":
            skill = params.get("skill_name", params.get("skill", ""))
            sql = (
                "SELECT DISTINCT r.employeeid as [EMPID], r.ResourceName as [Name], r.EmailId, "
                "t.TechCategoryName as [Tech Category], s.Name as [Skill] "
                "FROM Resource r "
                "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                "JOIN Project p ON pr.ProjectId = p.ProjectId "
                "JOIN TechCatagory t ON t.TechCategoryId = r.TechCategoryId "
                "JOIN PA_ResourceSkills rs ON rs.ResourceId = r.ResourceId "
                "JOIN PA_Skills s ON s.SkillId = rs.SkillId "
                "WHERE p.ProjectId = 119 "
                "AND (s.Name LIKE ? OR r.PrimarySkill LIKE ? OR r.SecondarySkill LIKE ?) "
                "ORDER BY r.ResourceName"
            )
            result = await connector.execute_query(
                sql,
                params=(f"%{skill}%", f"%{skill}%", f"%{skill}%"),
                timeout_seconds=t,
                max_rows=m,
            )

        elif intent == "resource_by_skill": # done and ready for improvement
            skill = params.get("skill", "")
            sql = (
                "SELECT distinct r.EmployeeId as [EMPID], r.ResourceName as [Name], r.EmailId, dr.designationname as [Designation] "
                "FROM Resource r "
                "JOIN Designation dr ON r.designationid = dr.designationid "
				"JOIN TechCatagory tc ON tc.TechCategoryId = r.TechCategoryId "
				"JOIN PA_ResourceSkills par ON par.ResourceId = r.ResourceId "
				"JOIN PA_Skills psk ON psk.SkillId = par.SkillId "
                "WHERE r.PrimarySkill LIKE ? OR r.SecondarySkill LIKE ? OR tc.TechCategoryName LIKE ? OR psk.Name LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{skill}%", f"%{skill}%", f"%{skill}%", f"%{skill}%"), timeout_seconds=t, max_rows=m)
        
        
        elif intent == "resource_availability": # done and ready for improvement
            sql = (
                "SELECT ResourceId, ResourceName, EmailId FROM Resource "
                "WHERE IsActive = 1 "
                "AND ResourceId NOT IN (SELECT DISTINCT ResourceId FROM ProjectResource WHERE IsActive = 1)"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)
        elif intent == "resource_project_assignments": # done and ready for improvement
            name = params.get("resource_name", "")
            sql = (
                "SELECT r.EmployeeId as [EMPID],r.ResourceName as [Employee Name], p.ProjectName as  [Project Name], CAST(pr.StartDate AS DATE) AS [Start Date],"
                "CAST(pr.EndDate AS DATE) AS [End Date], pr.resourcerole as [Role], pr.PercentageAllocation as [Allocation], pr.Billable FROM Resource r "
                "JOIN ProjectResource pr ON r.ResourceId = pr.ResourceId "
                "JOIN Project p ON pr.ProjectId = p.ProjectId "
                "WHERE r.ResourceName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)
        
        elif intent == "resource_skills_list": # done and ready for improvement
            name = params.get("resource_name", "")
            sql = (
                "SELECT DISTINCT r.ResourceName, s.Name, rs.SkillExperience "
                "FROM Resource r "
                "JOIN PA_ResourceSkills rs ON r.ResourceId = rs.ResourceId "
                "JOIN PA_Skills s ON rs.SkillId = s.SkillId "
                "WHERE r.ResourceName LIKE ?"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        elif intent == "reports_to":
            name = params.get("resource_name", "")
            sql = (
                "SELECT r.EmployeeId, r.ResourceName, pm.ResourceName as [Reporting To] "
                "FROM Resource r "
                "JOIN Resource pm ON pm.ResourceId = r.ReportingTo "
                "WHERE pm.ResourceName LIKE ? AND r.IsActive = 1"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"ResourceAgent: unknown intent '{intent}'")

        return sql, result


'''
elif intent == "resource_utilization": #baadme
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
                   
            '''