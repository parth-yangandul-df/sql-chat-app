"""BaseDomainAgent — shared execute() logic for all PRMS domain agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.connectors.base_connector import QueryResult
from app.connectors.connector_registry import get_or_create_connector
from app.llm.graph.state import GraphState


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
