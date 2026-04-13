"""LangGraph StateGraph assembly for the PRMS domain tool pipeline.

Graph topology (default — embedding + regex path):
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

Graph topology (USE_GROQ_EXTRACTOR=true — unified Groq path):
  groq_extract
       |
       ├─ confidence >= 0.60 → update_query_plan → run_domain_tool
       │                                            ├─ rows > 0 → interpret_result
       │                                            └─ 0 rows + fallback_intent? → run_fallback_intent
       │                                                            ├─ rows > 0 → interpret_result
       │                                                            └─ 0 rows   → llm_fallback
       └─ confidence < 0.60  → llm_fallback
                                      │
                                interpret_result
                                      │
                                write_history
                                      │
                                     END

Graph topology (USE_HYBRID_MODE=true — Phase 8 hybrid path):
  classify_intent
       |
       compute_embedding
       |
       followup_detection
       |
       llm_extraction
       |
       deterministic_override
       |
       confidence_scoring
       |
       ├─ confidence >= 0.7 → update_query_plan → run_domain_tool
       │                                            ├─ rows > 0 → interpret_result
       │                                            └─ 0 rows + fallback_intent? → run_fallback_intent
       │                                                            ├─ rows > 0 → interpret_result
       │                                                            └─ 0 rows   → llm_fallback
       └─ confidence < 0.7  → llm_fallback
                                      │
                                interpret_result
                                      │
                                write_history
                                      │
                                     END
"""

from langgraph.graph import END, StateGraph

from app.config import settings
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

    # ── Shared nodes (all paths) ────────────────────────────────────────────
    graph.add_node("run_domain_tool", run_domain_tool)
    graph.add_node("run_fallback_intent", run_fallback_intent)
    graph.add_node("llm_fallback", llm_fallback)
    graph.add_node("interpret_result", interpret_result)
    graph.add_node("write_history", write_history)
    graph.add_node("update_query_plan", update_query_plan)

    if settings.use_hybrid_mode:
        # ── Phase 8 Hybrid Mode Path ─────────────────────────────────────────
        from app.llm.graph.nodes.compute_embedding import compute_embedding_node
        from app.llm.graph.nodes.followup_detection import followup_detection_node
        from app.llm.graph.nodes.llm_extraction import llm_extraction_node
        from app.llm.graph.nodes.deterministic_override import deterministic_override_node
        from app.llm.graph.nodes.confidence_scoring import confidence_scoring_node, route_after_confidence

        graph.add_node("classify_intent", classify_intent)
        graph.add_node("compute_embedding", compute_embedding_node)
        graph.add_node("followup_detection", followup_detection_node)
        graph.add_node("llm_extraction", llm_extraction_node)
        graph.add_node("deterministic_override", deterministic_override_node)
        graph.add_node("confidence_scoring", confidence_scoring_node)

        graph.set_entry_point("classify_intent")

        # Flow: classify → embed → followup → extract → override → score
        graph.add_edge("classify_intent", "compute_embedding")
        graph.add_edge("compute_embedding", "followup_detection")
        graph.add_edge("followup_detection", "llm_extraction")
        graph.add_edge("llm_extraction", "deterministic_override")
        graph.add_edge("deterministic_override", "confidence_scoring")

        # Route based on confidence score
        graph.add_conditional_edges(
            "confidence_scoring",
            route_after_confidence,
            {
                "update_query_plan": "update_query_plan",
                "llm_fallback": "llm_fallback",
            },
        )

    elif settings.use_groq_extractor:
        # ── Groq unified path ─────────────────────────────────────────────────
        from app.llm.graph.nodes.llm_groq_extractor import groq_extract, route_after_groq

        graph.add_node("groq_extract", groq_extract)
        graph.set_entry_point("groq_extract")

        # groq_extract returns {domain, intent, confidence, filters}
        # route_after_groq checks confidence >= 0.60
        # Groq path skips extract_filters (already done inside groq_extract)
        graph.add_conditional_edges(
            "groq_extract",
            route_after_groq,
            {
                "run_domain_tool": "update_query_plan",
                "llm_fallback": "llm_fallback",
            },
        )
    else:
        # ── Default embedding + regex path ────────────────────────────────────
        graph.add_node("classify_intent", classify_intent)
        graph.add_node("extract_filters", extract_filters)

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

    # ── Shared downstream edges ──────────────────────────────────────────────
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
