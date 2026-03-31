"""classify_intent node — cosine similarity routing over the 29-intent catalog."""

import logging
import os
import re
from typing import Any

import numpy as np

from app.llm.graph.intent_catalog import INTENT_CATALOG, ensure_catalog_embedded, get_catalog_embeddings
from app.llm.graph.state import GraphState
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Follow-up detection — deictic phrases that signal refinement of prior results
# ---------------------------------------------------------------------------

_FOLLOWUP_PATTERNS = re.compile(
    r"\b(?:"
    r"which\s+of\s+th(?:ese|ose)"
    r"|among\s+th(?:em|ese|ose)"
    r"|from\s+th(?:em|ese|ose)"
    r"|of\s+th(?:ose|ese)"
    r"|filter\s+(?:by|them)"
    r"|only\s+th(?:ose|ese)"
    r"|same\s+ones"
    r"|th(?:ose|ese)\s+who"
    r")\b",
    re.IGNORECASE,
)

_REFINEMENT_KEYWORDS = re.compile(
    r"\b(?:skill|know|python|java|javascript|typescript|dotnet|\.net|react|angular|"
    r"who|filter|only|active|inactive|billable|assigned|available|unassigned)\b",
    re.IGNORECASE,
)


def _is_refinement_followup(question: str, last_turn_context: dict | None) -> bool:
    """Return True if question is a thin follow-up that should inherit prior intent.

    Requires ALL three conditions:
    - last_turn_context is not None (a prior turn exists)
    - question contains a deictic reference phrase ("which of these", "among them", etc.)
    - question contains a refinement keyword (skill, active, filter, etc.)
    """
    if not last_turn_context:
        return False
    if not _FOLLOWUP_PATTERNS.search(question):
        return False
    if not _REFINEMENT_KEYWORDS.search(question):
        return False
    return True


def _resolve_question(question: str, history: list[dict]) -> str:
    """Enrich a thin follow-up with prior user context for intent classification.

    Concatenates the last 2 prior user turns with the current question so the
    embedding used for catalog cosine similarity has enough signal to route
    follow-ups correctly rather than always falling through to llm_fallback.

    Only used for the catalog embedding; bare question is used for logging.
    """
    prior = [t["content"] for t in history if t.get("role") == "user"][-2:]
    if not prior:
        return question
    return " | ".join(prior + [question])


# Default lowered to 0.65 — nomic-embed-text (768-dim) paraphrase similarity
# sits in the 0.65–0.85 range; 0.78 was too aggressive and caused all queries
# to fall through to llm_fallback even for clear PRMS intent matches.
# Override via TOOL_CONFIDENCE_THRESHOLD env var without code changes.
_THRESHOLD = float(os.environ.get("TOOL_CONFIDENCE_THRESHOLD", "0.65"))


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=float), np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


async def classify_intent(state: GraphState) -> dict[str, Any]:
    """Embed the question and pick the best matching intent via cosine similarity.

    Role-based routing constraint (enforced here, not in route_after_classify):
    - If user_role == "user" and the best-matching domain is NOT "user_self",
      the result is overridden to confidence=0.0 so route_after_classify sends
      the request to llm_fallback (which will inject the scope constraint).
    - This prevents 'user' role accounts from reaching cross-user domain tools.

    Follow-up fast path:
    - If the question is a deictic refinement follow-up (e.g. "Which of these know Python?")
      AND a prior turn context exists, skip embedding entirely and inherit the prior
      domain/intent with confidence=0.95.  RBAC gate still applies on the inherited domain.
    """
    last_turn_context = state.get("last_turn_context")
    question = state["question"]
    user_role = state.get("user_role")

    # Follow-up fast path: inherit prior domain/intent without embedding
    if _is_refinement_followup(question, last_turn_context):
        inherited_domain = last_turn_context["domain"]  # type: ignore[index]
        inherited_intent = last_turn_context["intent"]  # type: ignore[index]
        logger.info(
            "intent=classify followup_detected q=%r → inheriting intent=%s domain=%s",
            question[:80], inherited_intent, inherited_domain,
        )
        # RBAC gate still applies on inherited domain
        if user_role == "user" and inherited_domain != "user_self":
            return {"domain": None, "intent": None, "confidence": 0.0}
        return {
            "domain": inherited_domain,
            "intent": inherited_intent,
            "confidence": 0.95,
        }

    # Normal embedding path ─────────────────────────────────────────────────
    # Ensure catalog embeddings are ready
    if any(not e.embedding for e in INTENT_CATALOG):
        await ensure_catalog_embedded()

    resolved = _resolve_question(state["question"], state.get("conversation_history") or [])
    question_embedding = await embed_text(resolved)
    catalog_embeddings = get_catalog_embeddings()

    scores = [_cosine(question_embedding, ce) for ce in catalog_embeddings]
    best_idx = int(np.argmax(scores))
    best_entry = INTENT_CATALOG[best_idx]
    best_score = scores[best_idx]

    # RBAC gate: 'user' role may only access user_self domain
    if user_role == "user" and best_entry.domain != "user_self":
        logger.info(
            "intent=classify rbac_gate role=user domain=%s intent=%s → forcing llm_fallback (scope constrained)",
            best_entry.domain, best_entry.name,
        )
        return {"domain": None, "intent": None, "confidence": 0.0}

    route_taken = "run_domain_tool" if best_score >= _THRESHOLD else "llm_fallback"

    # Always log top-3 scores so threshold can be tuned empirically from Docker logs
    top3 = sorted(zip(scores, INTENT_CATALOG), key=lambda x: x[0], reverse=True)[:3]
    top3_str = ", ".join(f"{e.name}:{s:.3f}" for s, e in top3)
    logger.info(
        "intent=classify q=%r  top3=[%s]  threshold=%.2f  route=%s",
        state["question"][:80], top3_str, _THRESHOLD, route_taken,
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
