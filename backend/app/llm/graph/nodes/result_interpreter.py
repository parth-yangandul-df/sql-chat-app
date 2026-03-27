"""interpret_result node — wraps existing ResultInterpreterAgent unchanged."""

import logging
from typing import Any

from app.llm.agents.result_interpreter import ResultInterpreterAgent
from app.llm.graph.state import GraphState
from app.llm.router import route

logger = logging.getLogger(__name__)


async def interpret_result(state: GraphState) -> dict[str, Any]:
    """Interpret query results using LLM. Skips if no rows returned.

    Failures are logged and swallowed — an interpretation error must never
    prevent results from reaching the caller.
    """
    result = state.get("result")
    if not result or not result.rows:
        return {
            "answer": None,
            "highlights": [],
            "suggested_followups": [],
        }

    question = state["question"]
    sql: str = state.get("sql") or ""
    provider, llm_config = route(question)

    try:
        interpreter = ResultInterpreterAgent(provider, llm_config)
        interpretation = await interpreter.interpret(
            question=question,
            sql=sql,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
        )
    except Exception:
        logger.warning("interpret_result: LLM interpretation failed", exc_info=True)
        return {
            "answer": None,
            "highlights": [],
            "suggested_followups": [],
        }

    return {
        "answer": interpretation.summary,
        "highlights": interpretation.highlights,
        "suggested_followups": interpretation.suggested_followups,
    }
