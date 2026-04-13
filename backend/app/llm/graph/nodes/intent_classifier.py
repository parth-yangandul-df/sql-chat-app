"""classify_intent node — cosine similarity routing over the 29-intent catalog."""

import logging
import os
from typing import Any

import numpy as np

from app.llm.graph.intent_catalog import INTENT_CATALOG, ensure_catalog_embedded, get_catalog_embeddings
from app.llm.graph.state import GraphState
from app.services.embedding_service import embed_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Follow-up detection — state-based: uses prior SQL/columns/params, not regex
# ---------------------------------------------------------------------------

# Common English stop words that carry no domain signal
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did",
    "be", "been", "being", "have", "has", "had", "of", "in", "on", "at",
    "to", "for", "with", "by", "from", "and", "or", "but", "not", "no",
    "so", "if", "all", "show", "me", "my", "their", "list", "get",
    "who", "what", "where", "when", "how", "which", "one", "these", "those",
    "them", "this", "that", "it", "its", "i", "we", "you", "they", "he", "she",
})

# ---------------------------------------------------------------------------
# Keyword pre-check sets — fast-path routing before embedding similarity.
# Each set covers unambiguous signals that embedding cosine similarity
# frequently misroutes due to short/generic catalog descriptions.
# ---------------------------------------------------------------------------

_SKILL_KEYWORDS: frozenset[str] = frozenset({
    # Languages
    "python", "java", "javascript", "typescript", "golang", "go", "rust",
    "kotlin", "swift", "scala", "ruby", "php", "perl", "matlab",
    "c#", "c++", "vb.net", ".net",
    # Frameworks / platforms
    "react", "angular", "vue", "svelte", "nextjs", "next.js",
    "django", "flask", "fastapi", "spring", "springboot",
    "nodejs", "node.js", "express", "nestjs",
    "dotnet", "asp.net", "blazor",
    # Data / cloud / infra
    "nosql", "mongodb", "postgres", "postgresql", "mysql",
    "redis", "elasticsearch", "kafka",
    "aws", "azure", "gcp", "kubernetes", "k8s",
    "terraform", "ansible",
    # Mobile / AI
    "android", "ios", "flutter",
    "tensorflow", "pytorch",
    # Database query language
    "sql",
})

# "bench" / "benched" are unambiguous — "available" / "free" excluded (too broad)
_BENCH_KEYWORDS: frozenset[str] = frozenset({
    "bench", "benched",
})

_OVERDUE_KEYWORDS: frozenset[str] = frozenset({
    "overdue", "delayed", "behind schedule", "past deadline",
    "past due", "past end date",
})

_TIMELINE_KEYWORDS: frozenset[str] = frozenset({
    "timeline", "duration", "start date", "end date",
    "how long", "when does", "when did", "deadline",
})

_BUDGET_KEYWORDS: frozenset[str] = frozenset({
    "budget", "burn rate",
})

_UNAPPROVED_KEYWORDS: frozenset[str] = frozenset({
    "unapproved", "pending approval", "not approved",
    "waiting for approval", "unreviewed", "pending timesheet",
})

# "show all active client*" pattern — must be checked BEFORE generic "active" matching
# to route to active_clients instead of client_projects or other intents
_ACTIVE_CLIENT_KEYWORDS: frozenset[str] = frozenset({
    "active client", "active clients", "all active client", "all active clients",
    "list active client", "list active clients", "show active client", "show active clients",
    "current client", "current clients", "all current client", "all current clients",
})

# "show all active project*" pattern — must be checked BEFORE generic "active" matching
_ACTIVE_PROJECT_KEYWORDS: frozenset[str] = frozenset({
    "active project", "active projects", "all active project", "all active projects",
    "list active project", "list active projects", "show active project", "show active projects",
    "current project", "current projects", "all current project", "all current projects",
    "ongoing project", "ongoing projects", "all ongoing project", "all ongoing projects",
})


def _keyword_route(question: str) -> tuple[str, str] | None:
    """Check keyword sets and return (intent_name, domain) if a pre-check fires.

    Order matters — bench checked before skill to avoid "bench developers"
    routing to resource_by_skill instead of benched_resources.
    Returns None if no keyword guard matches.
    """
    q = question.lower()
    # Check most specific patterns FIRST - "active client*" before generic "active"
    if any(kw in q for kw in _ACTIVE_CLIENT_KEYWORDS):
        return ("active_clients", "client")
    if any(kw in q for kw in _ACTIVE_PROJECT_KEYWORDS):
        return ("active_projects", "project")
    if any(kw in q for kw in _BENCH_KEYWORDS):
        return ("benched_resources", "resource")
    if any(kw in q for kw in _SKILL_KEYWORDS):
        return ("resource_by_skill", "resource")
    if any(kw in q for kw in _OVERDUE_KEYWORDS):
        return ("overdue_projects", "project")
    if any(kw in q for kw in _TIMELINE_KEYWORDS):
        return ("project_timeline", "project")
    if any(kw in q for kw in _BUDGET_KEYWORDS):
        return ("project_budget", "project")
    if any(kw in q for kw in _UNAPPROVED_KEYWORDS):
        return ("unapproved_timesheets", "timesheet")
    return None


def _is_refinement_followup(question: str, last_turn_context: dict | None) -> bool:
    """Return True if question is a thin follow-up that should inherit prior intent.

    State-based detection — reads prior SQL / columns / params from
    last_turn_context rather than matching deictic regex phrases.

    Returns True when last_turn_context has a prior SQL result AND either:
    - The question is short (≤3 content words after stripping stop words), OR
    - ≥30% of content words overlap with prior column names or param values.
    """
    if not last_turn_context or not last_turn_context.get("sql"):
        return False

    words = [w.lower().strip("?.,!;:") for w in question.split()]
    content_words = [w for w in words if w not in _STOP_WORDS and len(w) > 1]

    # Short question with prior context → refinement
    if len(content_words) <= 3:
        return True

    # Content words overlap with prior column names or param values → refinement
    prior_words: set[str] = {c.lower() for c in (last_turn_context.get("columns") or [])}
    prior_words |= {str(v).lower() for v in (last_turn_context.get("params") or {}).values()}
    if prior_words:
        overlap = sum(1 for w in content_words if w in prior_words)
        if overlap / len(content_words) >= 0.3:
            return True

    return False


async def _semantic_followup_check(question: str, last_turn_context: dict | None) -> bool:
    """Use embedding similarity to determine if question is a semantic follow-up.
    
    Returns True only if cosine similarity between current question and
    previous question embedding >= threshold. If prior question has no
    embedding or similarity check fails, returns True (fail open for safety).
    """
    if not last_turn_context:
        return True
    
    # Get prior question from turn context
    prior_question = last_turn_context.get("question")
    if not prior_question:
        return True  # No prior question, allow follow-up inheritance
    
    try:
        current_embedding = await embed_text(question)
        prior_embedding = await embed_text(prior_question)
        similarity = _cosine(current_embedding, prior_embedding)
        
        logger.info(
            "semantic_followup: q=%r prior=%r similarity=%.2f threshold=%.2f",
            question[:50], prior_question[:50], similarity, _SEMANTIC_SIMILARITY_THRESHOLD
        )
        
        # Only treat as follow-up if semantic similarity is high enough
        return similarity >= _SEMANTIC_SIMILARITY_THRESHOLD
    except Exception as e:
        logger.warning("semantic_followup: embedding failed (%s) — falling back to word heuristics", e)
        return True  # Fail open, allow follow-up inheritance


# ---------------------------------------------------------------------------
# Topic switch detection — clears context when user changes subject
# ---------------------------------------------------------------------------

# Domain-specific intent switches that indicate a topic change (not a refinement)
_RESOURCE_TOPIC_SWITCHES: frozenset[tuple[str, str]] = frozenset({
    ("active_resources", "benched_resources"),
    ("active_resources", "resource_by_skill"),
    ("active_resources", "resource_availability"),
    ("benched_resources", "active_resources"),
    ("benched_resources", "resource_by_skill"),
    ("benched_resources", "resource_availability"),
    ("resource_by_skill", "active_resources"),
    ("resource_by_skill", "benched_resources"),
})

_PROJECT_TOPIC_SWITCHES: frozenset[tuple[str, str]] = frozenset({
    ("active_projects", "project_budget"),
    ("active_projects", "project_timeline"),
    ("project_by_client", "project_budget"),
    ("project_timeline", "project_resources"),
})


def _is_topic_switch(
    current_domain: str | None,
    current_intent: str | None,
    last_turn_context: dict | None,
) -> bool:
    """Return True if the current query represents a topic switch.

    A topic switch means the user has changed subject enough that prior
    context should NOT be inherited for refinement.

    Detects:
    - Domain switches (resource → client, etc.)
    - Major intent switches within the same domain (active → benched, etc.)
    """
    if not last_turn_context:
        return False

    last_domain = last_turn_context.get("domain")
    last_intent = last_turn_context.get("intent")

    # No prior domain/intent to compare against
    if not last_domain or not last_intent:
        return False

    # Domain switch always clears context
    if current_domain and last_domain and current_domain != last_domain:
        return True

    # Same domain — check for major intent switches
    if current_domain == last_domain and current_intent and last_intent:
        if current_domain == "resource":
            if (last_intent, current_intent) in _RESOURCE_TOPIC_SWITCHES:
                return True
        elif current_domain == "project":
            if (last_intent, current_intent) in _PROJECT_TOPIC_SWITCHES:
                return True

    return False


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

# Semantic similarity threshold for follow-up detection (0.65 = treat more queries as new topics)
_SEMANTIC_SIMILARITY_THRESHOLD = float(os.environ.get("SEMANTIC_SIMILARITY_THRESHOLD", "0.65"))


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

    # Semantic follow-up check: if word-overlap is inconclusive, use embedding similarity
    # Only runs when prior context exists but word-based follow-up detection returned False
    if last_turn_context and last_turn_context.get("sql"):
        is_semantic_followup = await _semantic_followup_check(question, last_turn_context)
        if is_semantic_followup:
            inherited_domain = last_turn_context["domain"]
            inherited_intent = last_turn_context["intent"]
            logger.info(
                "intent=classify semantic_followup q=%r → inheriting intent=%s domain=%s",
                question[:80], inherited_intent, inherited_domain,
            )
            if user_role == "user" and inherited_domain != "user_self":
                return {"domain": None, "intent": None, "confidence": 0.0}
            return {
                "domain": inherited_domain,
                "intent": inherited_intent,
                "confidence": 0.95,
            }
        else:
            logger.info(
                "intent=classify semantic_topic_switch q=%r — treating as new topic",
                question[:80],
            )
            last_turn_context = None  # Clear context for new topic

    # Keyword pre-check — fires before embedding for unambiguous signal words.
    # Prevents generic catalog descriptions from beating specific intents on
    # cosine similarity. Guards are ordered: bench > skill > overdue > timeline
    # > budget > unapproved. RBAC gate applies identically to embedding path.
    kw_route = _keyword_route(question)
    if kw_route is not None:
        kw_intent, kw_domain = kw_route
        if user_role == "user" and kw_domain != "user_self":
            logger.info(
                "intent=classify keyword_match rbac_gate role=user intent=%s → llm_fallback",
                kw_intent,
            )
            return {"domain": None, "intent": None, "confidence": 0.0}
        logger.info(
            "intent=classify keyword_match q=%r → forcing intent=%s domain=%s",
            question[:80], kw_intent, kw_domain,
        )
        return {
            "domain": kw_domain,
            "intent": kw_intent,
            "confidence": 0.99,
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
