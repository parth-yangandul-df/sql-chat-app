"""Fixed ResourceAgent._run_refinement() method with proper query detection."""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent, _strip_order_by
from app.llm.graph.state import GraphState


class ResourceAgent(BaseDomainAgent):
    async def _run_refinement(
        self,
        prior_sql: str,
        params: dict[str, Any],
        connector: Any,
        state: GraphState,
    ) -> tuple[str, Any]:
        """Wrap prior resource SQL as subquery with skill filter."""
        skill = params.get("skill", "")
        prior_columns = params.get("_prior_columns", [])
        t = state["timeout_seconds"]
        m = state["max_rows"]

        # Only skill-based refinement is supported; no skill → run base intent
        if not skill:
            intent = state["intent"] or ""
            return await self._run_intent(intent, params, connector, state)

        stripped = _strip_order_by(prior_sql)

        # Fixed detection logic: distinguish by unique columns instead of EMPID
        # active_resources has "Designation", benched_resources has "TechCategoryName"
        # Both queries return "EMPID" (without brackets) as the ID column
        has_designation = "designation" in [c.lower() for c in prior_columns]
        has_tech_category = "techcategoryname" in [c.lower() for c in prior_columns]
        
        if has_tech_category and not has_designation:
            # benched_resources pattern - join with employeeid from Resource table
            sql = (
                f"SELECT prev.* "
                f"FROM ({stripped}) AS prev "
                f"JOIN Resource r2 ON r2.EmployeeId = prev.EMPID "
                f"JOIN PA_ResourceSkills rs ON rs.ResourceId = r2.ResourceId "
                f"JOIN PA_Skills s ON s.SkillId = rs.SkillId "
                f"WHERE s.Name LIKE ?"
            )
            result = await connector.execute_query(
                sql, params=(f"%{skill}%",), timeout_seconds=t, max_rows=m
            )
        else:
            # active_resources pattern or any other - default to EMPID join
            sql = (
                f"SELECT prev.* "
                f"FROM ({stripped}) AS prev "
                f"JOIN Resource r2 ON r2.EmployeeId = prev.EMPID "
                f"JOIN PA_ResourceSkills rs ON rs.ResourceId = r2.ResourceId "
                f"JOIN PA_Skills s ON s.SkillId = rs.SkillId "
                f"WHERE s.Name LIKE ? OR r2.PrimarySkill LIKE ? OR r2.SecondarySkill LIKE ?"
            )
            result = await connector.execute_query(
                sql,
                params=(f"%{skill}%", f"%{skill}%", f"%{skill}%"),
                timeout_seconds=t,
                max_rows=m,
            )

        return sql, result
