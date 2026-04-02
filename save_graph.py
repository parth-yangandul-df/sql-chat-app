"""
save_graph.py — renders the QueryWise LangGraph pipeline to a PNG.

Usage (from the repo root):
    python save_graph.py [output.png]

The script adds backend/ to sys.path so all app.* imports resolve without
installing the package.  It builds only the graph topology — no DB or LLM
connections are opened.

Output defaults to: querywise_graph.png
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# ── stub out heavy optional deps so import doesn't crash ─────────────────────
# LangGraph graph building imports app.llm.graph.nodes.* which transitively
# import LLM providers, DB models, etc.  We only need the graph topology, so
# we provide lightweight stubs for anything that would need live credentials.

import types

def _stub_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod

# Prevent asyncpg / aioodbc / sqlalchemy from needing a live DB at import time.
# These are only used at call time, not at module import for the graph nodes.
# (The graph nodes themselves are plain async functions — safe to import.)

# ── build the graph ───────────────────────────────────────────────────────────
from langgraph.graph import END, StateGraph  # noqa: E402

from app.llm.graph.state import GraphState  # noqa: E402
from app.llm.graph.domains.registry import run_domain_tool  # noqa: E402
from app.llm.graph.nodes.fallback_intent import (  # noqa: E402
    route_after_domain_tool,
    route_after_fallback_intent,
    run_fallback_intent,
)
from app.llm.graph.nodes.history_writer import write_history  # noqa: E402
from app.llm.graph.nodes.intent_classifier import classify_intent, route_after_classify  # noqa: E402
from app.llm.graph.nodes.llm_fallback import llm_fallback  # noqa: E402
from app.llm.graph.nodes.param_extractor import extract_params  # noqa: E402
from app.llm.graph.nodes.result_interpreter import interpret_result  # noqa: E402


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("extract_params", extract_params)
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
            "extract_params": "extract_params",
            "llm_fallback": "llm_fallback",
        },
    )

    graph.add_edge("extract_params", "run_domain_tool")

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


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "querywise_graph.png"

    print("Building graph...")
    compiled = build_graph()

    print("Rendering PNG via Mermaid...")
    png_bytes = compiled.get_graph().draw_mermaid_png()

    out.write_bytes(png_bytes)
    print(f"Saved: {out.resolve()}")


if __name__ == "__main__":
    main()
