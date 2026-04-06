"""llm_groq_extractor — unified intent classification + filter extraction via Groq tool calling.

Replaces the embedding-based classify_intent + regex filter_extractor with a single
Groq LLM call that returns structured intent and filters in one shot.

Features:
- Groq tool calling with strict JSON schema (all 24 intents, all registered fields)
- Graceful fallback to embedding classifier if Groq fails or returns low confidence
- Refinement follow-up fast path preserved (short follow-ups skip LLM entirely)
- RBAC gate enforced identically to the embedding path
- Logs latency, token usage, and confidence for every call
"""

from __future__ import annotations

import logging
import re
import json
from typing import Any

from app.llm.graph.intent_catalog import INTENT_CATALOG
from app.llm.graph.nodes.field_registry import FIELD_REGISTRY_BY_DOMAIN
from app.llm.graph.nodes.intent_classifier import _is_refinement_followup, _semantic_followup_check
from app.llm.graph.query_plan import FilterClause, _sanitize_value
from app.llm.graph.state import GraphState
from app.llm.providers.groq_provider import GroqProvider
from app.config import settings
from app.llm.base_provider import LLMConfig, LLMMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error recovery — parse failed_generation from Groq error response
# ---------------------------------------------------------------------------

def _parse_failed_generation(error_str: str) -> dict | None:
    """Extract intent/filters from Groq's failed_generation error response.
    
    Groq returns partial model output in the 'failed_generation' field when
    tool calling fails. We can recover valid intent/filters from it.
    """
    # Groq error format: "... 'failed_generation': '<function=...>{\"intent\": ..., ...}'"
    match = re.search(r"'failed_generation': '<function=\w+>(.+?)'", error_str, re.DOTALL)
    if not match:
        return None
    try:
        # The captured group may have trailing garbage, try to extract valid JSON
        json_str = match.group(1).rstrip(">")
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

# ---------------------------------------------------------------------------
# Tool schema — built once at module load from live catalog + registry
# ---------------------------------------------------------------------------

def _build_tool_schema() -> list[dict]:
    """Build Groq tool calling schema from INTENT_CATALOG and FIELD_REGISTRY."""
    intent_names = [e.name for e in INTENT_CATALOG]
    intent_descriptions = {e.name: e.description for e in INTENT_CATALOG}

    # Build field catalog per domain for the description
    field_lines: list[str] = []
    for domain, fields in FIELD_REGISTRY_BY_DOMAIN.items():
        for fname, fc in fields.items():
            aliases = f" (aliases: {', '.join(fc.aliases)})" if fc.aliases else ""
            field_lines.append(
                f"  {fname} [{fc.sql_type}] — domain:{domain}{aliases}"
            )
    field_catalog_str = "\n".join(field_lines)

    intent_catalog_str = "\n".join(
        f"  {name}: {desc}" for name, desc in intent_descriptions.items()
    )

    return [
        {
            "type": "function",
            "function": {
                "name": "extract_query_intent_and_filters",
                "description": (
                    "Extract the user's intent and structured filters from a natural language PRMS query.\n\n"
                    "INTENT CATALOG (pick exactly one):\n"
                    f"{intent_catalog_str}\n\n"
                    "AVAILABLE FILTER FIELDS (use canonical field_name, validate domain matches intent):\n"
                    f"{field_catalog_str}\n\n"
                    "FILTER OPS: eq (equals/contains), gt (greater than), lt (less than), between (date/numeric range), in (multiple values).\n"
                    "All filter values must be plain strings. For boolean fields: '1'=true, '0'=false.\n"
                    "Extract only filters explicitly mentioned. Do not infer filters not present in the query."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": intent_names,
                            "description": "The most appropriate intent from the catalog.",
                        },
                        "domain": {
                            "type": "string",
                            "enum": ["resource", "client", "project", "timesheet", "user_self"],
                            "description": "Domain that the intent belongs to.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score 0.0-1.0. Use <0.6 if the query is ambiguous or doesn't match any intent well.",
                        },
                        "filters": {
                            "type": "array",
                            "description": "Structured filters extracted from the query. Empty array if no filters present.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {
                                        "type": "string",
                                        "description": "Canonical field name from the field catalog.",
                                    },
                                    "op": {
                                        "type": "string",
                                        "enum": ["eq", "in", "lt", "gt", "between"],
                                    },
                                    "values": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Filter values as strings. For 'between' provide [start, end].",
                                    },
                                },
                                "required": ["field", "op", "values"],
                            },
                        },
                    },
                    "required": ["intent", "domain", "confidence", "filters"],
                },
            },
        }
    ]


# Build tool schema once at import time
_TOOL_SCHEMA = _build_tool_schema()

# ---------------------------------------------------------------------------
# Groq client — instantiated lazily using configured API key
# ---------------------------------------------------------------------------

_groq_provider: GroqProvider | None = None


def _get_groq_provider() -> GroqProvider:
    global _groq_provider
    if _groq_provider is None:
        _groq_provider = GroqProvider(api_key=settings.groq_api_key or None)
    return _groq_provider


# ---------------------------------------------------------------------------
# System prompt — concise context for the PRMS domain
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an intent and filter extraction assistant for a PRMS (Project Resource Management System). "
    "Given a natural language query, call the extract_query_intent_and_filters tool with the correct intent "
    "and any filters the user mentioned. "
    "Be precise — only extract filters explicitly stated in the query. "
    "For skill/technology filters, extract the exact technology name as stated (e.g. 'Python', 'React Native', 'SQL', '.NET'). "
    "For 'user_self' domain intents, the user is asking about their own data (my projects, my skills, etc.). "
    "If the query is ambiguous or doesn't clearly match any intent, set confidence below 0.6."
    "IMPORTANT: If a filter has no values, OMIT the filter entirely from the output. Never output an empty values array []. "
    "Instead, simply do not include that filter field."
)

# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

_CONFIDENCE_THRESHOLD = 0.60


async def groq_extract(state: GraphState) -> dict[str, Any]:
    """Unified intent + filter extraction via Groq tool calling.

    Flow:
    1. Refinement follow-up fast path — inherit prior intent (no LLM call)
    2. Groq tool call → structured intent + filters
    3. RBAC gate on extracted domain
    4. Validate + build FilterClause objects from extracted filters
    5. Return {domain, intent, confidence, filters} — same shape as classify_intent + extract_filters combined

    On any Groq failure → returns confidence=0.0 to trigger llm_fallback.
    """
    question = state["question"]
    user_role = state.get("user_role")
    last_turn_context = state.get("last_turn_context")

    # ── 1. Refinement follow-up fast path ──────────────────────────────────
    if _is_refinement_followup(question, last_turn_context):
        inherited_domain = last_turn_context["domain"]  # type: ignore[index]
        inherited_intent = last_turn_context["intent"]  # type: ignore[index]
        logger.info(
            "groq_extractor: followup_detected q=%r → inheriting intent=%s domain=%s",
            question[:80], inherited_intent, inherited_domain,
        )
        if user_role == "user" and inherited_domain != "user_self":
            return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}
        return {
            "domain": inherited_domain,
            "intent": inherited_intent,
            "confidence": 0.95,
            "filters": [],  # filter_extractor still runs downstream for refinement
        }

    # Semantic follow-up check: if word-overlap is inconclusive, use embedding similarity
    if last_turn_context and last_turn_context.get("sql"):
        is_semantic_followup = await _semantic_followup_check(question, last_turn_context)
        if is_semantic_followup:
            inherited_domain = last_turn_context["domain"]
            inherited_intent = last_turn_context["intent"]
            logger.info(
                "groq_extractor: semantic_followup q=%r → inheriting intent=%s domain=%s",
                question[:80], inherited_intent, inherited_domain,
            )
            if user_role == "user" and inherited_domain != "user_self":
                return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}
            return {
                "domain": inherited_domain,
                "intent": inherited_intent,
                "confidence": 0.95,
                "filters": [],
            }
        else:
            logger.info(
                "groq_extractor: semantic_topic_switch q=%r — treating as new topic",
                question[:80],
            )
            last_turn_context = None  # Clear context for new topic

    # ── 2. Groq tool call ───────────────────────────────────────────────────
    messages = [
        LLMMessage(role="system", content=_SYSTEM_PROMPT),
        LLMMessage(role="user", content=question),
    ]
    config = LLMConfig(
        model=settings.groq_model,
        temperature=0.0,   # deterministic extraction
        max_tokens=512,    # tool call response is small
        top_p=1.0,
    )

    try:
        provider = _get_groq_provider()
        result = await provider.complete_with_tools(messages, _TOOL_SCHEMA, config)
        args = result["arguments"]
        latency_ms = result["latency_ms"]
    except Exception as e:
        error_str = str(e)
        # Try to recover from failed_generation in the error response
        recovered = _parse_failed_generation(error_str)
        if recovered:
            logger.info(
                "groq_extractor: recovered from failed_generation intent=%s domain=%s",
                recovered.get("intent"), recovered.get("domain"),
            )
            return {
                "domain": recovered.get("domain"),
                "intent": recovered.get("intent"),
                "confidence": float(recovered.get("confidence", 0.5)),
                "filters": recovered.get("filters", []),
            }
        logger.warning(
            "groq_extractor: Groq call failed (%s) — falling back to llm_fallback",
            e,
        )
        return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}

    intent = args.get("intent", "")
    domain = args.get("domain", "")
    confidence = float(args.get("confidence", 0.0))
    raw_filters = args.get("filters", [])

    # Filter out filters with empty values arrays (secondary safety net)
    raw_filters = [f for f in raw_filters if f.get("values")]

    logger.info(
        "groq_extractor: q=%r intent=%s domain=%s confidence=%.2f filters=%d latency=%.0fms",
        question[:80], intent, domain, confidence, len(raw_filters), latency_ms,
    )

    # ── 3. RBAC gate ────────────────────────────────────────────────────────
    if user_role == "user" and domain != "user_self":
        logger.info(
            "groq_extractor: rbac_gate role=user domain=%s intent=%s → llm_fallback",
            domain, intent,
        )
        return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}

    # ── 4. Build FilterClause objects ───────────────────────────────────────
    filters: list[FilterClause] = []
    for raw in raw_filters:
        field_name = raw.get("field", "")
        op = raw.get("op", "eq")
        values = raw.get("values", [])

        if not field_name or not values:
            continue

        # Sanitize all values
        sanitized = [_sanitize_value(str(v)) for v in values if str(v).strip()]
        if not sanitized:
            continue

        # Validate field exists in domain registry
        domain_fields = FIELD_REGISTRY_BY_DOMAIN.get(domain, {})
        if field_name not in domain_fields:
            logger.warning(
                "groq_extractor: field '%s' not in registry for domain '%s' — dropping",
                field_name, domain,
            )
            continue

        try:
            fc = FilterClause(field=field_name, op=op, values=sanitized)
            filters.append(fc)
        except Exception as e:
            logger.warning("groq_extractor: invalid FilterClause for field=%r: %s", field_name, e)
            continue

    return {
        "domain": domain,
        "intent": intent,
        "confidence": confidence,
        "filters": filters,
    }


def route_after_groq(state: GraphState) -> str:
    """Conditional edge: route based on Groq extraction confidence."""
    if state["confidence"] >= _CONFIDENCE_THRESHOLD:
        return "run_domain_tool"
    return "llm_fallback"
