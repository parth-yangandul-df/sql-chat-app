"""TimesheetAgent — 4 PRMS timesheet intent SQL templates.

All valid timesheet queries filter: IsApproved=1 AND IsDeleted=0 AND IsRejected=0
The unapproved_timesheets intent inverts the approved filter.
"""

from __future__ import annotations

from typing import Any

from app.llm.graph.domains.base_domain import BaseDomainAgent
from app.llm.graph.state import GraphState

_VALID = "ts.IsApproved = 1 AND ts.IsDeleted = 0 AND ts.IsRejected = 0"


class TimesheetAgent(BaseDomainAgent):
    async def _run_intent(self, intent: str, params: dict[str, Any], connector: Any, state: GraphState) -> tuple[str, Any]:
        t = state["timeout_seconds"]
        m = state["max_rows"]

        if intent == "approved_timesheets":
            sql = (
                f"SELECT ts.TimesheetId, r.ResourceName, ts.WorkDate, ts.Hours, ts.Description "
                f"FROM Timesheet ts JOIN Resource r ON ts.ResourceId = r.ResourceId "
                f"WHERE {_VALID} ORDER BY ts.WorkDate DESC"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "timesheet_by_period":
            start = params.get("start_date", "")
            end = params.get("end_date", "")
            sql = (
                f"SELECT r.ResourceName, ts.WorkDate, ts.Hours, ts.Description "
                f"FROM Timesheet ts JOIN Resource r ON ts.ResourceId = r.ResourceId "
                f"WHERE {_VALID} AND ts.WorkDate BETWEEN ? AND ? "
                f"ORDER BY ts.WorkDate"
            )
            result = await connector.execute_query(sql, params=(start, end), timeout_seconds=t, max_rows=m)

        elif intent == "unapproved_timesheets":
            sql = (
                "SELECT ts.TimesheetId, r.ResourceName, ts.WorkDate, ts.Hours "
                "FROM Timesheet ts JOIN Resource r ON ts.ResourceId = r.ResourceId "
                "WHERE ts.IsApproved = 0 AND ts.IsDeleted = 0 AND ts.IsRejected = 0 "
                "ORDER BY ts.WorkDate DESC"
            )
            result = await connector.execute_query(sql, timeout_seconds=t, max_rows=m)

        elif intent == "timesheet_by_project":
            name = params.get("resource_name", params.get("project_name", ""))
            sql = (
                f"SELECT p.ProjectName, r.ResourceName, ts.WorkDate, ts.Hours "
                f"FROM Timesheet ts "
                f"JOIN Resource r ON ts.ResourceId = r.ResourceId "
                f"JOIN Project p ON ts.ProjectId = p.ProjectId "
                f"WHERE {_VALID} AND p.ProjectName LIKE ? "
                f"ORDER BY ts.WorkDate DESC"
            )
            result = await connector.execute_query(sql, params=(f"%{name}%",), timeout_seconds=t, max_rows=m)

        else:
            raise ValueError(f"TimesheetAgent: unknown intent '{intent}'")

        return sql, result
