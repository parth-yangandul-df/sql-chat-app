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

import json
import logging
import re
from typing import Any

from app.config import settings
from app.llm.base_provider import LLMConfig, LLMMessage
from app.llm.graph.intent_catalog import INTENT_CATALOG
from app.llm.graph.nodes.classifier_keywords import _keyword_route
from app.llm.graph.nodes.field_registry import FIELD_REGISTRY_BY_DOMAIN
from app.llm.graph.nodes.intent_classifier import _is_refinement_followup, _semantic_followup_check
from app.llm.graph.nodes.sql_compiler import BASE_QUERIES, NO_FILTER_INTENTS
from app.llm.graph.query_plan import FilterClause, _sanitize_value
from app.llm.graph.state import GraphState
from app.llm.providers.groq_provider import GroqProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error recovery — parse failed_generation from Groq error response
# ---------------------------------------------------------------------------


def _parse_failed_generation(error_str: str) -> dict | None:
    """Extract intent/filters from Groq's failed_generation error response.

    Groq returns partial model output in the 'failed_generation' field when
    tool calling fails. We can recover valid intent/filters from it.
    """
    import re as _re

    # Find the start of the JSON payload after '<function=name>'
    match = _re.search(r"'failed_generation':\s*'<function=\w+>\s*", error_str)
    if not match:
        return None
    start = error_str.find("{", match.end())
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(error_str, start)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Tool schema — built once at module load from live catalog + registry
# ---------------------------------------------------------------------------


def _build_tool_schema() -> list[dict]:
    """Build Groq tool calling schema from INTENT_CATALOG descriptions and FIELD_REGISTRY."""
    intent_names = list(BASE_QUERIES.keys())

    # Build rich descriptions from INTENT_CATALOG — used for semantic intent selection.
    # Falls back to a plain name if an intent exists in BASE_QUERIES but not in the catalog.
    catalog_descriptions: dict[str, str] = {
        entry.name: entry.description for entry in INTENT_CATALOG
    }

    # [FIXED] intents have pre-built SQL with no dynamic filter support.
    # If user question needs filters for a [FIXED] intent → set confidence<0.6.
    intent_lines: list[str] = [
        "NOTE: [FIXED] = no dynamic filters. Set confidence<0.6 if user question needs filters on a [FIXED] intent."
    ]
    for name in intent_names:
        desc = catalog_descriptions.get(name, name)
        # Shorten description to core meaning only — strip synonym padding used for embeddings
        desc = desc.split(" — ")[0].strip()  # keep first clause only
        tag = " [FIXED]" if name in NO_FILTER_INTENTS else ""
        intent_lines.append(f"  {name}{tag}: {desc}")
    # 'unknown' escape hatch — select when NO catalog intent covers the question
    intent_lines.append("  unknown: No catalog intent matches — pipeline generates custom SQL.")
    intent_catalog_str = "\n".join(intent_lines)

    # Build field catalog as one compact line per domain
    domain_field_lines: list[str] = []
    for domain, fields in FIELD_REGISTRY_BY_DOMAIN.items():
        field_parts = [
            f"{fname}[{fc.sql_type[0]}]" for fname, fc in fields.items()
        ]  # e.g. skill[t], billable[b]
        domain_field_lines.append(f"  {domain}: {', '.join(field_parts)}")
    field_catalog_str = "\n".join(domain_field_lines)

    return [
        {
            "type": "function",
            "function": {
                "name": "extract_query_intent_and_filters",
                "description": (
                    "Extract intent and filters from a PRMS natural language query.\n\n"
                    "INTENTS:\n"
                    f"{intent_catalog_str}\n\n"
                    "FILTER FIELDS (field[type] per domain — t=text,d=date,n=numeric,b=boolean):\n"
                    f"{field_catalog_str}\n\n"
                    "OPS: eq,in,lt,gt,between. Values as strings. boolean: '1'=true,'0'=false. Extract only explicit filters."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": intent_names + ["unknown"],
                            "description": "The most appropriate intent from the catalog, or 'unknown' if no intent matches.",
                        },
                        "domain": {
                            "type": "string",
                            "enum": [
                                "resource",
                                "client",
                                "project",
                                "timesheet",
                                "user_self",
                                "unknown",
                            ],
                            "description": "Domain that the intent belongs to, or 'unknown' if the intent is unknown.",
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
    "PRMS intent+filter extractor. Call extract_query_intent_and_filters with the correct intent and any explicit filters. "
    "Only extract filters stated in the query — never infer. "
    "Skills/tech: use exact name as stated (Python, React Native, .NET). "
    "user_self intents (my_projects, my_timesheets, my_skills, my_allocation, my_utilization): only when user says 'my'/'I'/'me'. "
    "\nSet confidence<0.6 when: query spans multiple entity types; uses negation across entities; "
    "requires aggregation/counting; no intent clearly matches; closest intent is [FIXED] but filters needed. "
    "Use intent=unknown when query clearly needs data not in catalog (join dates, salary, trends, attrition). "
    "\nNever output empty filters array — omit filter if no value. "
    "\nEXAMPLES:"
    "\n- 'skills of John Doe' → resource_skills_list, 0.95, [{resource_name,eq,[John Doe]}]"
    "\n- 'python developers' → resource_by_skill, 0.95, [{skill,eq,[Python]}]"
    "\n- 'active resources' → active_resources, 0.95, []"
    "\n- 'resources joined last 6 months' → unknown, 0.0, []"
    "\n- 'clients with no billable resources' → unknown, 0.0, []"
)

# ---------------------------------------------------------------------------
# Post-processing heuristics — fix common extraction failures
# ---------------------------------------------------------------------------


def _post_process_extraction(args: dict, question: str) -> dict:
    """Fix common extraction failures with pattern matching heuristics.

    This catches cases where Groq doesn't extract filters correctly.
    """
    intent = args.get("intent", "")
    filters = args.get("filters", [])
    domain = args.get("domain", "")
    question_lower = question.lower()

    # Fix 0: project name cleanup - Groq sometimes includes the relational noun
    # from phrasing like "on Project Riggs Tree" as part of the project value,
    # which turns a broad LIKE into an overly specific miss.
    if domain == "project":
        normalized_filters = []
        for filter_item in filters:
            if filter_item.get("field") == "project_name":
                values = []
                for value in filter_item.get("values", []):
                    cleaned = value.strip()
                    if cleaned.lower().startswith("project ") and (
                        " on project " in f" {question_lower} "
                        or " for project " in f" {question_lower} "
                    ):
                        cleaned = cleaned[8:].strip()
                    values.append(cleaned)
                normalized_filters.append({**filter_item, "values": values})
            else:
                normalized_filters.append(filter_item)
        filters = normalized_filters

    # Fix 1: resource_skills_list - "skills of {name}" pattern
    if intent == "resource_skills_list" and domain == "resource":
        # Check if question has "skills of {person}" pattern
        name_pattern = r"(?:skills?\s+(?:of|for)\s+|show\s+(?:me\s+)?skills?\s+(?:of\s+)?)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
        if match := re.search(name_pattern, question, re.IGNORECASE):
            name = match.group(1).strip()
            # Check if we already have a resource_name filter
            if not any(f.get("field") == "resource_name" for f in filters):
                filters.append({"field": "resource_name", "op": "eq", "values": [name]})

    # Fix 2: resource_by_skill - common skill names
    if intent == "resource_by_skill" and not any(f.get("field") == "skill" for f in filters):
        skill_pattern = r"\b(python|java|react|angular|sql|javascript|typescript|\.net|nodejs|golang|rust|php|swift|kotlin|docker|kubernetes|aws|azure|gcp)\b"
        if match := re.search(skill_pattern, question_lower):
            skill = match.group(1).capitalize()
            filters.append({"field": "skill", "op": "eq", "values": [skill]})

    # Fix 3: project_by_client - "projects for {client}" pattern
    if intent == "project_by_client" and not any(f.get("field") == "client_name" for f in filters):
        client_pattern = (
            r"(?:projects?\s+(?:for|of)\s+|client\s+)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        )
        if match := re.search(client_pattern, question, re.IGNORECASE):
            client = match.group(1).strip()
            filters.append({"field": "client_name", "op": "eq", "values": [client]})

    # Fix 4: timesheet_by_period - date range patterns
    if intent == "timesheet_by_period" and not any(
        f.get("field") in ("start_date", "end_date") for f in filters
    ):
        # Try to extract date patterns
        date_pattern = r"(?:last\s+)?(week|month|year)|(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        if match := re.search(date_pattern, question_lower):
            if match.group(1):  # "last week", "last month"
                # Would add date filters here based on period: match.group(1)
                pass

    return {
        "intent": intent,
        "domain": domain,
        "filters": filters,
    }


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

    # ── 0. Keyword pre-check (BEFORE refinement follow-up) ─────────────────────
    keyword_result = _keyword_route(question)
    if keyword_result:
        intent, domain = keyword_result
        logger.info(
            "groq_extractor: keyword_precheck q=%r → intent=%s domain=%s",
            question[:80],
            intent,
            domain,
        )
        # RBAC gate: user role cannot access cross-user domains
        if user_role == "user" and domain != "user_self":
            return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}
        return {
            "domain": domain,
            "intent": intent,
            "confidence": 0.98,
            "filters": [],
        }

    # ── 1. Refinement follow-up fast path ──────────────────────────────────
    if _is_refinement_followup(question, last_turn_context):
        inherited_domain = last_turn_context["domain"]  # type: ignore[index]
        inherited_intent = last_turn_context["intent"]  # type: ignore[index]
        logger.info(
            "groq_extractor: followup_detected q=%r → inheriting intent=%s domain=%s",
            question[:80],
            inherited_intent,
            inherited_domain,
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
                question[:80],
                inherited_intent,
                inherited_domain,
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
        temperature=0.0,  # deterministic extraction
        max_tokens=512,  # tool call response is small
        top_p=1.0,
    )

    try:
        provider = _get_groq_provider()
        result = await provider.complete_with_tools(messages, _TOOL_SCHEMA, config)
        args = result["arguments"]
        latency_ms = result["latency_ms"]
    except Exception as e:
        from app.core.exceptions import RateLimitError as _RateLimitError

        if isinstance(e, _RateLimitError):
            raise  # let @llm_retry() on complete_with_tools handle it
        error_str = str(e)
        # Try to recover from failed_generation in the error response
        recovered = _parse_failed_generation(error_str)
        if recovered:
            logger.info(
                "groq_extractor: recovered from failed_generation intent=%s domain=%s",
                recovered.get("intent"),
                recovered.get("domain"),
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

    # Apply post-processing heuristics to fix common extraction failures
    if raw_filters:
        args = _post_process_extraction(args, question)
        raw_filters = args.get("filters", [])

    # Filter out filters with empty values arrays (secondary safety net)
    raw_filters = [f for f in raw_filters if f.get("values")]

    logger.info(
        "groq_extractor: q=%r intent=%s domain=%s confidence=%.2f filters=%d latency=%.0fms",
        question[:80],
        intent,
        domain,
        confidence,
        len(raw_filters),
        latency_ms,
    )

    # ── 3. RBAC gate ────────────────────────────────────────────────────────
    if user_role == "user" and domain != "user_self":
        logger.info(
            "groq_extractor: rbac_gate role=user domain=%s intent=%s → llm_fallback",
            domain,
            intent,
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
                field_name,
                domain,
            )
            continue

        try:
            fc = FilterClause(field=field_name, op=op, values=sanitized)
            filters.append(fc)
        except Exception as e:
            logger.warning("groq_extractor: invalid FilterClause for field=%r: %s", field_name, e)
            continue

    # Normalize 'unknown' intent/domain to None so llm_fallback generates fresh SQL
    # Try keyword recovery as last-resort before llm_fallback
    if intent == "unknown" or domain == "unknown":
        keyword_result = _keyword_route(question)
        if keyword_result:
            intent, domain = keyword_result
            confidence = 0.75  # Higher than <0.6 threshold to reach domain tool
            logger.info(
                "groq_extractor: keyword_recovery intent=unknown → keyword_match intent=%s domain=%s",
                intent,
                domain,
            )
            # RBAC gate
            if user_role == "user" and domain != "user_self":
                return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}
        else:
            intent = None
            domain = None
            confidence = 0.0

    return {
        "domain": domain,
        "intent": intent,
        "confidence": confidence,
        "filters": filters,
    }


def route_after_groq(state: GraphState) -> str:
    """Conditional edge: route based on Groq extraction confidence."""
    # 'unknown' is an explicit signal from the model that no catalog intent covers
    # this query — bypass confidence check and go straight to llm_fallback.
    if state.get("intent") == "unknown":
        logger.info("route_after_groq: intent=unknown → llm_fallback (no catalog coverage)")
        return "llm_fallback"
    if state["confidence"] >= _CONFIDENCE_THRESHOLD:
        return "run_domain_tool"
    return "llm_fallback"
