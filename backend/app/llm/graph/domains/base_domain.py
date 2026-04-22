"""BaseDomainAgent — shared execute() logic for all PRMS domain agents.

Supports parameter-based refinement via the declarative refinement registry.
When a follow-up query is detected (_refine_mode=True), the agent attempts to
find a matching refinement template and execute it as a subquery with additional
filter conditions. If no template matches or refinement fails, falls back to
the base intent.

Feature flag: when settings.use_query_plan_compiler is True, execute() routes
through the QueryPlan SQL compiler instead of the subquery-based refinement path.
The flag=OFF path (_try_refinement) is preserved unchanged for rollback safety.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from app.connectors.base_connector import QueryResult
from app.connectors.connector_registry import get_or_create_connector
from app.llm.graph.domains.refinement_registry import (
    find_matching_template,
    supports_refinement,
)
from app.llm.graph.state import GraphState

logger = logging.getLogger(__name__)


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
    """Base class for PRMS domain SQL agents.

    Subclasses implement _run_intent() with SQL templates for each intent.
    Refinement is handled automatically via the refinement registry —
    subclasses can override _run_refinement() for custom logic (e.g. ResourceAgent).
    """

    @property
    def domain(self) -> str:
        """Return the domain name for this agent (used for registry lookup).

        Override in subclasses if the class name doesn't match the domain.
        Default: uses the class name without "Agent" suffix, lowercased.
        """
        return self.__class__.__name__.replace("Agent", "").lower()

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
        """Dispatch to the correct SQL template and execute against the connector.

        Feature flag routing:
        - settings.use_query_plan_compiler = True (NEW PATH):
            If query_plan is present → compile_query() → execute against connector
            If query_plan is None (LLM fallback turn) → _run_intent() fallback
        - settings.use_query_plan_compiler = False (EXISTING PATH, unchanged):
            If _refine_mode is set → _try_refinement()
            Otherwise → _run_intent()
        """
        # Lazy imports allow importlib.reload() in tests to pick up updated settings
        from app.config import settings
        from app.llm.graph.nodes.sql_compiler import compile_query
        from app.llm.graph.query_plan import QueryPlan

        intent = state["intent"] or ""
        params = state.get("params") or {}
        domain = self.domain

        connector = await get_or_create_connector(
            state["connection_id"],
            state["connector_type"],
            state["connection_string"],
        )

        if settings.use_query_plan_compiler:
            # NEW PATH: QueryPlan compiler
            query_plan_dict = state.get("query_plan")
            if query_plan_dict:
                plan = QueryPlan.from_untrusted_dict(query_plan_dict)
                try:
                    sql, sql_params = compile_query(plan, resource_id=state.get("resource_id"))
                except ValueError as exc:
                    # user_self domain requires resource_id — admin users have none.
                    # Fall back to _run_intent so the error surfaces gracefully.
                    logger.warning(
                        "execute: compile_query failed (%s) — falling back to _run_intent "
                        "domain=%s intent=%s",
                        exc, domain, intent,
                    )
                    try:
                        sql, result = await self._run_intent(intent, params, connector, state)
                    except ValueError as exc2:
                        # Both compile_query and _run_intent raised ValueError (no resource_id).
                        # Return graceful error response instead of crashing.
                        from app.connectors.base_connector import QueryResult
                        logger.error(
                            "execute: _run_intent also failed for user_self "
                            "domain (resource_id=None). "
                            "domain=%s intent=%s exc=%s",
                            domain, intent, exc2,
                        )
                        empty = QueryResult(
                            columns=[], column_types=[], rows=[], row_count=0,
                            execution_time_ms=0.0, truncated=False,
                        )
                        return {
                            "sql": None,
                            "result": empty,
                            "generated_sql": None,
                            "explanation": None,
                            "llm_provider": "domain_tool",
                            "llm_model": intent,
                            "error": f"user_self requires resource_id: {exc2}",
                        }
                    return {
                        "sql": sql,
                        "result": result,
                        "generated_sql": None,
                        "explanation": None,
                        "llm_provider": "domain_tool",
                        "llm_model": intent,
                        "error": None,
                    }
                
                # ── Log generated SQL ─────────────────────────────────────────
                logger.info(
                    "domain_sql: domain=%s intent=%s sql=[%s] params=%s",
                    domain, intent, sql[:200] if sql else "none", sql_params,
                )
                
                result = await connector.execute_query(
                    sql,
                    params=sql_params,
                    timeout_seconds=state["timeout_seconds"],
                    max_rows=state["max_rows"],
                )
            else:
                # No query_plan (LLM fallback turn) → run base intent
                logger.debug(
                    "execute: flag=ON but query_plan=None for domain=%s intent=%s — "
                    "falling back to _run_intent",
                    domain, intent,
                )
                sql, result = await self._run_intent(intent, params, connector, state)
                
                # ── Log fallback SQL ─────────────────────────────────────────
                logger.info(
                    "domain_sql: domain=%s intent=%s (fallback intent sql)",
                    domain, intent,
                )
        else:
            # EXISTING PATH: subquery refinement (unchanged)
            if _is_refine_mode(params):
                prior_sql = _get_prior_sql(params)
                sql, result = await self._try_refinement(
                    prior_sql, params, connector, state, domain, intent,
                )
            else:
                sql, result = await self._run_intent(intent, params, connector, state)
            
            # ── Log old path SQL ─────────────────────────────────────────────
            logger.info(
                "domain_sql: domain=%s intent=%s (old path)",
                domain, intent,
            )

        return {
            "sql": sql,
            "result": result,
            "generated_sql": None,   # domain tool path — no LLM generation
            "explanation": None,
            "llm_provider": "domain_tool",
            "llm_model": intent,
            "error": None,
        }

    async def _try_refinement(
        self,
        prior_sql: str,
        params: dict[str, Any],
        connector: Any,
        state: GraphState,
        domain: str,
        intent: str,
    ) -> tuple[str, QueryResult]:
        """Attempt refinement via registry, then subclass override, then fallback.

        Priority:
        1. Registry-based refinement (declarative templates)
        2. Subclass _run_refinement() (custom logic like ResourceAgent)
        3. Base intent (safe fallback)
        """
        logger.warning(
            "refinement path is DEPRECATED — enable USE_QUERY_PLAN_COMPILER=true "
            "(domain=%s intent=%s)",
            domain, intent,
        )

        t = state["timeout_seconds"]
        m = state["max_rows"]
        stripped = _strip_order_by(prior_sql)

        # Step 1: Try registry-based refinement
        if supports_refinement(domain, intent):
            template = find_matching_template(domain, intent, params)
            if template:
                try:
                    sql, sql_params = template.build_sql(stripped, params)
                    result = await connector.execute_query(
                        sql, params=sql_params, timeout_seconds=t, max_rows=m,
                    )
                    logger.info(
                        "refinement: domain=%s intent=%s type=%s rows=%d",
                        domain, intent, template.refinement_type.value, result.row_count,
                    )
                    return sql, result
                except Exception as e:
                    logger.warning(
                        "refinement: registry template failed (%s), trying subclass override", e,
                    )

        # Step 2: Try subclass _run_refinement() override
        # Check if the subclass has its own implementation (not the base default)
        if type(self)._run_refinement is not BaseDomainAgent._run_refinement:
            try:
                return await self._run_refinement(prior_sql, params, connector, state)
            except Exception as e:
                logger.warning(
                    "refinement: subclass override failed (%s), falling back to base intent", e,
                )

        # Step 3: Fallback to base intent
        logger.info(
            "refinement: no matching template for domain=%s intent=%s, running base intent",
            domain, intent,
        )
        return await self._run_intent(intent, params, connector, state)

    async def _run_refinement(
        self,
        prior_sql: str,
        params: dict[str, Any],
        connector: Any,
        state: GraphState,
    ) -> tuple[str, QueryResult]:
        """Wrap prior SQL as subquery with a new filter.

        Default: runs base intent unchanged (safe fallback for agents that
        don't implement refinement).

        Override in subclasses for custom refinement logic that isn't covered
        by the declarative registry (e.g. ResourceAgent's skill-based JOIN
        refinement).
        """
        intent = state["intent"] or ""
        return await self._run_intent(intent, params, connector, state)
