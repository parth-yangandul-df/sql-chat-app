"""BaseDomainAgent — shared execute() logic for all PRMS domain agents."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from app.connectors.base_connector import QueryResult
from app.connectors.connector_registry import get_or_create_connector
from app.llm.graph.state import GraphState


def _is_refine_mode(params: dict) -> bool:
    """Return True if params signal a subquery refinement (set by extract_params)."""
    return bool(params.get("_refine_mode") and params.get("_prior_sql"))


def _get_prior_sql(params: dict) -> str:
    """Get the prior turn's SQL from params."""
    return params.get("_prior_sql", "")


def _strip_order_by(sql: str) -> str:
    """Remove trailing ORDER BY clause from SQL — required for SQL Server subquery use.

    SQL Server does not allow ORDER BY in subqueries unless TOP/OFFSET FETCH is used.
    """
    return re.sub(r"\s+ORDER\s+BY\s+.+$", "", sql, flags=re.IGNORECASE | re.DOTALL).strip()


class BaseDomainAgent(ABC):
    """Base class for PRMS domain SQL agents."""

    @abstractmethod
    async def _run_intent(
        self,
        intent: str,
        params: dict[str, Any],
        connector: Any,
        state: GraphState,
    ) -> tuple[str, QueryResult]:
        """Return (sql, result). Raises ValueError for unknown intent."""

    async def execute(self, state: GraphState) -> dict[str, Any]:
        """Dispatch to the correct SQL template and execute against the connector."""
        intent = state["intent"] or ""
        params = state.get("params") or {}

        connector = await get_or_create_connector(
            state["connection_id"],
            state["connector_type"],
            state["connection_string"],
        )

        if _is_refine_mode(params):
            prior_sql = _get_prior_sql(params)
            sql, result = await self._run_refinement(prior_sql, params, connector, state)
        else:
            sql, result = await self._run_intent(intent, params, connector, state)

        return {
            "sql": sql,
            "result": result,
            "generated_sql": None,   # domain tool path — no LLM generation
            "explanation": None,
            "llm_provider": "domain_tool",
            "llm_model": intent,
            "error": None,
        }

    async def _run_refinement(
        self,
        prior_sql: str,
        params: dict[str, Any],
        connector: Any,
        state: GraphState,
    ) -> tuple[str, QueryResult]:
        """Wrap prior SQL as subquery with a new filter.

        Default: runs base intent unchanged (safe fallback for agents that don't implement refinement).
        Override in subclasses to add domain-specific refinement logic.
        """
        intent = state["intent"] or ""
        return await self._run_intent(intent, params, connector, state)
