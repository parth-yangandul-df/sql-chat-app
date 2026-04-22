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
# First-person pronouns — checked on raw tokens (NOT stripped via _STOP_WORDS)
# Used to gate user_self intent: only valid when user is asking about themselves.
# ---------------------------------------------------------------------------
_FIRST_PERSON_WORDS: frozenset[str] = frozenset({
    "my", "i", "me", "mine", "myself", "i'm", "i've", "i'll", "i'd",
})


def _has_first_person(question: str) -> bool:
    """Return True if the question contains any first-person pronoun."""
    tokens = {w.lower().strip("?.,!;:'\"") for w in question.split()}
    return bool(tokens & _FIRST_PERSON_WORDS)


def _has_person_name(question: str) -> bool:
    """Return True if question contains a person name pattern.

    Detects sequences of 2+ consecutive capitalized words that look like
    a person's name (e.g., "Gautham R M", "John Smith", "Jane Doe").
    Used to guard _USER_SELF_KEYWORDS — queries about named people should
    not route to user_self even if they contain "my" or "me".
    """
    words = question.split()
    capitalized_count = 0

    for word in words:
        clean_word = word.strip("?.,!;:'\"")
        if clean_word and clean_word[0].isupper() and clean_word[0].isalpha():
            capitalized_count += 1
            if capitalized_count >= 2:
                return True
        else:
            capitalized_count = 0

    return False


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

# "skills of X" / "skills for X" — specific person skill queries
# Must be checked BEFORE generic bench/skill to catch "skills of Abhijeet Desai" patterns
_SKILLS_OF_KEYWORDS: frozenset[str] = frozenset({
    "skills of", "skills for", "skill set of", "skill set for",
    "tech skills of", "tech skills for",
    "what skills does", "what skills do",
    "what are the skills of", "what are the skill",
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

# "show all active resource*" / "active employees" — must be checked BEFORE generic skill/bench matching
_ACTIVE_RESOURCE_KEYWORDS: frozenset[str] = frozenset({
    "active resource", "active resources", "all active resource", "all active resources",
    "list active resource", "list active resources", "show active resource", "show active resources",
    "active employee", "active employees", "all active employee", "all active employees",
    "show active employee", "show active employees", "list active employee", "list active employees",
    "active staff", "all active staff", "show active staff",
})

_PROJECT_RESOURCES_KEYWORDS: frozenset[str] = frozenset({
    "working on project", "works on project", "assigned to project",
    "who is on project", "who are on project", "on the project",
    "team on project", "team for project", "members of project",
    "resources on project", "resources for project", "resources assigned",
    "working on the project", "assigned to the project",
    "who is working on", "who works on", "team members on",
})

# "projects for client X" — explicit filter-by-client patterns
# Must NOT include "client projects" (ambiguous with client_projects intent)
_PROJECT_BY_CLIENT_KEYWORDS: frozenset[str] = frozenset({
    "projects for client", "show projects for client",
    "client's projects", "projects of client",
})

# "resource project assignments" — who is assigned to which projects for a specific person
_RESOURCE_PROJECT_KEYWORDS: frozenset[str] = frozenset({
    "project assignment", "project assignments",
    "who is assigned to", "who are assigned to",
    "resources assigned to", "resource assigned to",
    "assigned projects", "person's projects", "employee projects",
    "staff projects", "team member projects",
})

# Specific "my X" patterns must be checked BEFORE generic "my project(s)" in _keyword_route
# to prevent substring matches (e.g., "my project" matching "my utilization").
_USER_UTILIZATION_KEYWORDS: frozenset[str] = frozenset({
    "my utilization", "my utilization for",
    "my hours", "my hours for",
})

_USER_ALLOCATION_KEYWORDS: frozenset[str] = frozenset({
    "my allocation", "my allocation for", "show my allocation",
})

_USER_SELF_KEYWORDS: frozenset[str] = frozenset({
    "my timesheet", "my timesheets", "show my timesheet", "show my timesheets",
    "my project", "my projects", "show my project", "show my projects",
})

_MY_SKILLS_KEYWORDS: frozenset[str] = frozenset({
    "my skill", "my skills", "show my skill", "show my skills",
})

_REPORTS_TO_KEYWORDS: frozenset[str] = frozenset({
    "reports to", "reporting to", "who reports to",
    "direct reports", "reportees of", "team under",
    "subordinates of", "who report to",
})


def _keyword_route(question: str) -> tuple[str, str] | None:
    """Check keyword sets and return (intent_name, domain) if a pre-check fires.

    Order matters — bench checked before skill to avoid "bench developers"
    routing to resource_by_skill instead of benched_resources.
    Returns None if no keyword guard matches.
    """
    q = question.lower()
    # Check most specific patterns FIRST — reports_to before resource_project
    if any(kw in q for kw in _REPORTS_TO_KEYWORDS):
        return ("reports_to", "resource")
    # Check most specific patterns FIRST — resource_project before project_resources
    if any(kw in q for kw in _RESOURCE_PROJECT_KEYWORDS):
        return ("resource_project_assignments", "resource")
    # Check most specific patterns FIRST — project_resources before active_projects
    if any(kw in q for kw in _PROJECT_RESOURCES_KEYWORDS):
        return ("project_resources", "project")
    # "projects for client X" — explicit filter-by-client patterns
    if any(kw in q for kw in _PROJECT_BY_CLIENT_KEYWORDS):
        return ("project_by_client", "project")
    # USER_UTILIZATION must be checked BEFORE generic _USER_SELF_KEYWORDS
    # to prevent "my project" from substring-matching "my utilization"
    if any(kw in q for kw in _USER_UTILIZATION_KEYWORDS):
        return ("my_utilization", "user_self")
    # USER_ALLOCATION must be checked AFTER my_utilization and BEFORE generic keywords
    if any(kw in q for kw in _USER_ALLOCATION_KEYWORDS):
        return ("my_allocation", "user_self")
    # MY_SKILLS must be checked BEFORE _USER_SELF_KEYWORDS to route "my skills" to my_skills
    if any(kw in q for kw in _MY_SKILLS_KEYWORDS):
        return ("my_skills", "user_self")
    # USER_SELF — "my projects", "my timesheets" etc. route to user_self
    # Skip if question contains a person name (e.g., "Show me Gautham R M project assignments")
    # — in that case "me" refers to someone else, not the current user.
    if not _has_person_name(question) and any(kw in q for kw in _USER_SELF_KEYWORDS):
        return ("my_projects", "user_self")
    if any(kw in q for kw in _ACTIVE_CLIENT_KEYWORDS):
        return ("active_clients", "client")
    if any(kw in q for kw in _ACTIVE_PROJECT_KEYWORDS):
        return ("active_projects", "project")
    if any(kw in q for kw in _ACTIVE_RESOURCE_KEYWORDS):
        return ("active_resources", "resource")
    if any(kw in q for kw in _BENCH_KEYWORDS):
        # If a skill keyword also appears, route to benched_by_skill
        if any(kw in q for kw in _SKILL_KEYWORDS):
            return ("benched_by_skill", "resource")
        return ("benched_resources", "resource")
    if any(kw in q for kw in _SKILL_KEYWORDS):
        return ("resource_by_skill", "resource")
    # "skills of Abhijeet Desai" — specific person skill queries
    # Must be AFTER generic skill check but BEFORE bench so "skills of X who know Python" routes correctly
    if any(kw in q for kw in _SKILLS_OF_KEYWORDS):
        return ("resource_skills_list", "resource")
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

    # Keyword pre-check FIRST — unambiguous signals always win over follow-up inheritance.
    # Prevents "show benched resources who know .NET" from inheriting a prior benched_resources
    # intent via semantic follow-up instead of routing to benched_by_skill.
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

    # Follow-up fast path: inherit prior domain/intent without embedding
    if _is_refinement_followup(question, last_turn_context):
        inherited_domain = last_turn_context["domain"]  # type: ignore[index]
        inherited_intent = last_turn_context["intent"]  # type: ignore[index]
        # Guard: user_self intent only valid when question contains first-person pronoun.
        # "projects for notesight" has no "my"/"i" → should NOT inherit user_self context.
        if inherited_domain == "user_self" and not _has_first_person(question):
            logger.info(
                "intent=classify followup_skipped q=%r"
                " — user_self inherited without first-person pronoun, re-routing",
                question[:80],
            )
            # Fall through to embedding — do NOT inherit
        else:
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
            # Guard: user_self intent only valid with first-person pronoun in question.
            if inherited_domain == "user_self" and not _has_first_person(question):
                logger.info(
                    "intent=classify semantic_followup_skipped q=%r"
                    " — user_self without first-person pronoun, re-routing",
                    question[:80],
                )
                last_turn_context = None  # Clear context, treat as new topic
            else:
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
    display_scores = scores  # used for top3 log; updated if masking occurs

    # First-person guard: user_self intents require first-person pronouns.
    # Prevents "projects for notesight" from routing to my_projects via embedding similarity.
    if best_entry.domain == "user_self" and not _has_first_person(question):
        # Mask all user_self scores and pick next-best entry
        user_self_indices = [
            i for i, e in enumerate(INTENT_CATALOG) if e.domain == "user_self"
        ]
        masked_scores = [
            s if i not in user_self_indices else -1.0
            for i, s in enumerate(scores)
        ]
        best_idx = int(np.argmax(masked_scores))
        best_entry = INTENT_CATALOG[best_idx]
        best_score = masked_scores[best_idx]
        display_scores = masked_scores
        logger.info(
            "intent=classify user_self_masked q=%r"
            " — no first-person pronoun, re-routed to intent=%s domain=%s score=%.3f",
            question[:80], best_entry.name, best_entry.domain, best_score,
        )

    # RBAC gate: 'user' role may only access user_self domain
    if user_role == "user" and best_entry.domain != "user_self":
        logger.info(
            "intent=classify rbac_gate role=user domain=%s intent=%s → forcing llm_fallback (scope constrained)",
            best_entry.domain, best_entry.name,
        )
        return {"domain": None, "intent": None, "confidence": 0.0}

    route_taken = "run_domain_tool" if best_score >= _THRESHOLD else "llm_fallback"

    # Always log top-3 scores so threshold can be tuned empirically from Docker logs
    top3 = sorted(zip(display_scores, INTENT_CATALOG), key=lambda x: x[0], reverse=True)[:3]
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
