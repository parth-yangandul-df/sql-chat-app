"""LangGraph StateGraph assembly for the PRMS domain tool pipeline.

Graph topology (Groq-native path):
  groq_extract
       |
       ├─ confidence >= 0.60 → update_query_plan → run_domain_tool
       │                                            ├─ rows > 0 → interpret_result
       │                                            └─ 0 rows / error → llm_fallback
       └─ confidence < 0.60  → llm_fallback
                                      │
                                interpret_result
                                      │
                                write_history
                                      │
                                     END
"""

from langgraph.graph import END, StateGraph

from app.llm.graph.domains.registry import run_domain_tool
from app.llm.graph.nodes.domain_routing import route_after_domain_tool
from app.llm.graph.nodes.history_writer import write_history
from app.llm.graph.nodes.llm_fallback import llm_fallback
from app.llm.graph.nodes.plan_updater import update_query_plan
from app.llm.graph.nodes.result_interpreter import interpret_result
from app.llm.graph.state import GraphState

_compiled_graph = None


def _build_graph():
    from app.llm.graph.nodes.llm_groq_extractor import groq_extract, route_after_groq

    graph = StateGraph(GraphState)

    # Entry: Groq unified intent + filter extractor
    graph.add_node("groq_extract", groq_extract)
    graph.add_node("update_query_plan", update_query_plan)
    graph.add_node("run_domain_tool", run_domain_tool)
    graph.add_node("llm_fallback", llm_fallback)
    graph.add_node("interpret_result", interpret_result)
    graph.add_node("write_history", write_history)

    graph.set_entry_point("groq_extract")

    graph.add_conditional_edges(
        "groq_extract",
        route_after_groq,
        {
            "run_domain_tool": "update_query_plan",
            "llm_fallback": "llm_fallback",
        },
    )

    graph.add_edge("update_query_plan", "run_domain_tool")

    graph.add_conditional_edges(
        "run_domain_tool",
        route_after_domain_tool,
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
