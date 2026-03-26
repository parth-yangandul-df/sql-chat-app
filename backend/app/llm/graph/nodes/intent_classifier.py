"""classify_intent node — cosine similarity routing over the 24-intent catalog."""

import logging
import os
from typing import Any

import numpy as np

from app.llm.graph.intent_catalog import INTENT_CATALOG, ensure_catalog_embedded, get_catalog_embeddings
from app.llm.graph.state import GraphState
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)

_THRESHOLD = float(os.environ.get("TOOL_CONFIDENCE_THRESHOLD", "0.78"))


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


async def classify_intent(state: GraphState) -> dict[str, Any]:
    """Embed the question and pick the best matching intent via cosine similarity."""
    # Ensure catalog embeddings are ready
    if any(not e.embedding for e in INTENT_CATALOG):
        await ensure_catalog_embedded()

    question_embedding = await embed_text(state["question"])
    catalog_embeddings = get_catalog_embeddings()

    scores = [_cosine(question_embedding, ce) for ce in catalog_embeddings]
    best_idx = int(np.argmax(scores))
    best_entry = INTENT_CATALOG[best_idx]
    best_score = scores[best_idx]

    route_taken = "run_domain_tool" if best_score >= _THRESHOLD else "llm_fallback"
    if route_taken == "run_domain_tool":
        logger.info(
            "intent=classify q=%r domain=%s intent=%s confidence=%.3f route=%s",
            state["question"][:80], best_entry.domain, best_entry.name, best_score, route_taken,
        )
    else:
        logger.warning(
            "intent=classify q=%r domain=%s intent=%s confidence=%.3f route=%s (below threshold %.2f)",
            state["question"][:80], best_entry.domain, best_entry.name, best_score, route_taken, _THRESHOLD,
        )

    return {
        "domain": best_entry.domain,
        "intent": best_entry.name,
        "confidence": best_score,
    }


def route_after_classify(state: GraphState) -> str:
    """LangGraph conditional edge: route based on classification confidence."""
    if state["confidence"] >= _THRESHOLD:
        return "extract_params"
    return "llm_fallback"
