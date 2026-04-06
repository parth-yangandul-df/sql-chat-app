"""LangGraph StateGraph assembly for the PRMS domain tool pipeline.

Graph topology:
  classify_intent
       |
       ├─ confidence >= threshold → extract_filters → update_query_plan → run_domain_tool
       │                                                                    ├─ rows > 0 → interpret_result
       │                                                                    └─ 0 rows + fallback_intent? → run_fallback_intent
       │                                                                                    ├─ rows > 0 → interpret_result
       │                                                                                    └─ 0 rows   → llm_fallback
       └─ confidence < threshold  → llm_fallback
                                           │
                                     interpret_result
                                           │
                                     write_history
                                           │
                                          END
"""

from langgraph.graph import END, StateGraph

from app.llm.graph.domains.registry import run_domain_tool
from app.llm.graph.nodes.fallback_intent import (
    route_after_domain_tool,
    route_after_fallback_intent,
    run_fallback_intent,
)
from app.llm.graph.nodes.filter_extractor import extract_filters
from app.llm.graph.nodes.history_writer import write_history
from app.llm.graph.nodes.intent_classifier import classify_intent, route_after_classify
from app.llm.graph.nodes.llm_fallback import llm_fallback
from app.llm.graph.nodes.plan_updater import update_query_plan
from app.llm.graph.nodes.result_interpreter import interpret_result
from app.llm.graph.state import GraphState

_compiled_graph = None


def _build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("extract_filters", extract_filters)
    graph.add_node("update_query_plan", update_query_plan)
    graph.add_node("run_domain_tool", run_domain_tool)
    graph.add_node("run_fallback_intent", run_fallback_intent)
    graph.add_node("llm_fallback", llm_fallback)
    graph.add_node("interpret_result", interpret_result)
    graph.add_node("write_history", write_history)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "extract_params": "extract_filters",
            "llm_fallback": "llm_fallback",
        },
    )

    graph.add_edge("extract_filters", "update_query_plan")
    graph.add_edge("update_query_plan", "run_domain_tool")

    graph.add_conditional_edges(
        "run_domain_tool",
        route_after_domain_tool,
        {
            "interpret_result": "interpret_result",
            "run_fallback_intent": "run_fallback_intent",
            "llm_fallback": "llm_fallback",
        },
    )

    graph.add_conditional_edges(
        "run_fallback_intent",
        route_after_fallback_intent,
        {
            "interpret_result": "interpret_result",
            "llm_fallback": "llm_fallback",
        },
    )

    graph.add_edge("llm_fallback", "interpret_result")
    graph.add_edge("interpret_result", "write_history")
    graph.add_edge("write_history", END)

    return graph.compile()


def get_compiled_graph():
    """Return the compiled graph singleton. Thread-safe after first call."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph
