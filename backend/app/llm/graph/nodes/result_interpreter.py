"""interpret_result node — wraps existing ResultInterpreterAgent unchanged."""

from typing import Any

from app.llm.graph.state import GraphState
from app.llm.agents.result_interpreter import ResultInterpreterAgent
from app.llm.router import route


async def interpret_result(state: GraphState) -> dict[str, Any]:
    """Interpret query results using LLM. Skips if no rows returned."""
    result = state.get("result")
    if not result or not result.rows:
        return {
            "answer": None,
            "highlights": [],
            "suggested_followups": [],
        }

    question = state["question"]
    sql = state.get("sql", "")
    provider, llm_config = route(question)

    interpreter = ResultInterpreterAgent(provider, llm_config)
    interpretation = await interpreter.interpret(
        question=question,
        sql=sql,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
    )

    return {
        "answer": interpretation.summary,
        "highlights": interpretation.highlights,
        "suggested_followups": interpretation.suggested_followups,
    }
