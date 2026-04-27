"""llm_groq_extractor — unified intent classification + filter extraction via Groq tool calling.

Replaces the embedding-based classify_intent + regex filter_extractor with a single
Groq LLM call that returns structured intent and filters in one shot.

Features:
- Groq tool calling with strict JSON schema (all intents, all registered fields)
- Prior turn context injected into user message for LLM-native follow-up detection
- Intent mutation safety net: benched_resources+skill → benched_by_skill, etc.
- RBAC gate enforced identically to the embedding path
- Logs latency, token usage, and confidence for every call
- Graceful fallback to confidence=0.0 on any Groq failure
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.llm.base_provider import LLMConfig, LLMMessage
from app.llm.graph.intent_catalog import INTENT_CATALOG
from app.llm.graph.nodes.field_registry import FIELD_REGISTRY_BY_DOMAIN
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

    catalog_descriptions: dict[str, str] = {
        entry.name: entry.description for entry in INTENT_CATALOG
    }

    intent_lines: list[str] = [
        "NOTE: [FIXED] = no dynamic filters. Set confidence<0.6 if user question needs filters on a [FIXED] intent."
    ]
    for name in intent_names:
        desc = catalog_descriptions.get(name, name)
        desc = desc.split(" — ")[0].strip()
        tag = " [FIXED]" if name in NO_FILTER_INTENTS else ""
        intent_lines.append(f"  {name}{tag}: {desc}")
    intent_lines.append("  unknown: No catalog intent matches — pipeline generates custom SQL.")
    intent_catalog_str = "\n".join(intent_lines)

    domain_field_lines: list[str] = []
    for domain, fields in FIELD_REGISTRY_BY_DOMAIN.items():
        field_parts = [f"{fname}[{fc.sql_type[0]}]" for fname, fc in fields.items()]
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
                        "out_of_scope": {
                            "type": "boolean",
                            "description": "True if query is clearly outside PRMS domain (HR salary, leave, personal contact info, etc.)",
                        },
                        "is_follow_up": {
                            "type": "boolean",
                            "description": "True if current question is a follow-up/refinement of the prior turn",
                        },
                        "follow_up_type": {
                            "type": "string",
                            "enum": ["filter_refinement", "topic_switch", "none"],
                            "description": "Type of follow-up relationship to prior turn",
                        },
                    },
                    "required": ["intent", "domain", "confidence", "filters", "out_of_scope", "is_follow_up", "follow_up_type"],
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
# System prompt — comprehensive PRMS domain extractor
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a PRMS (Project Resource Management System) intent and filter extractor.
Always call extract_query_intent_and_filters with the correct intent, domain, confidence, and any explicit filters.

## MULTI-TURN RULES
When the user message starts with [PRIOR TURN: ...], determine if CURRENT is a follow-up:
- If CURRENT adds a filter or asks more about the same entity → set is_follow_up=true, follow_up_type=filter_refinement. Inherit prior intent and domain.
- If CURRENT clearly shifts to a different entity type (e.g. prior=resources, current=clients) → set is_follow_up=false, follow_up_type=topic_switch. Use a fresh intent.
- If no PRIOR TURN prefix present → set is_follow_up=false, follow_up_type=none.

## QUALIFICATION RULES (critical)
- "show active projects for [ClientName]" → use project_by_client with client_name filter (NOT active_projects)
- "active resources in [Location]" → use active_resources with location filter
- When the closest match is a [FIXED] intent but the question contains a qualifier (client name, skill, person name), check if a non-fixed intent better captures the qualifier.

## INTENT MUTATION RULES (critical)
- benched_resources + skill mentioned → use benched_by_skill with skill filter instead
- active_projects + client name mentioned → use project_by_client with client_name filter instead

## OUT OF SCOPE
Set out_of_scope=true for: salary, leave balance, personal contact info, HR-only data, anything clearly outside resource/project management.

## CONFIDENCE RULES
Set confidence < 0.60 when:
- Query spans multiple entity types or uses negation across entities
- Requires aggregation/counting with no matching intent
- No intent clearly matches the question
- Closest intent is [FIXED] but the question needs filters that [FIXED] cannot support

## EXTRACTION RULES
- Only extract EXPLICIT filters stated in the query — never infer or assume.
- Skills: use exact casing as stated by the user (Python, React Native, .NET, SQL).
- user_self intents (my_projects, my_timesheets, my_skills, etc.): ONLY when user says "my"/"I"/"me"/"mine".
- Filter field "project_name": do not include relational prefix words (strip leading "project " when phrasing is "on project X").

## FEW-SHOT EXAMPLES

"list all the benched resources"
→ benched_resources, resource, 0.97, [], out_of_scope=false, is_follow_up=false, follow_up_type=none

"python developers"
→ resource_by_skill, resource, 0.97, [{skill,eq,[Python]}], out_of_scope=false, is_follow_up=false, follow_up_type=none

"show active projects for moon gate technology"
→ project_by_client, project, 0.97, [{client_name,eq,[Moon Gate Technology]}], out_of_scope=false, is_follow_up=false, follow_up_type=none

"active resources"
→ active_resources, resource, 0.97, [], out_of_scope=false, is_follow_up=false, follow_up_type=none

"resources joined last 6 months"
→ unknown, unknown, 0.0, [], out_of_scope=false, is_follow_up=false, follow_up_type=none

"what is john's salary"
→ unknown, unknown, 0.0, [], out_of_scope=true, is_follow_up=false, follow_up_type=none

[PRIOR TURN: intent=benched_resources, domain=resource, question="list all the benched resources"]
CURRENT: which of these know SQL
→ benched_by_skill, resource, 0.95, [{skill,eq,[SQL]}], out_of_scope=false, is_follow_up=true, follow_up_type=filter_refinement

[PRIOR TURN: intent=active_resources, domain=resource, question="show active resources"]
CURRENT: show their skills
→ resource_skills_list, resource, 0.90, [], out_of_scope=false, is_follow_up=true, follow_up_type=filter_refinement

[PRIOR TURN: intent=benched_resources, domain=resource, question="show benched"]
CURRENT: show all clients
→ active_clients, client, 0.95, [], out_of_scope=false, is_follow_up=false, follow_up_type=topic_switch

## STATUS CATALOG
Valid status names per domain (use exact casing when extracting status filters):
  Client:   Active, Inactive, Closed
  Project:  Active, Inactive, On hold, Others, Closed
  Resource: Active, Inactive
The downstream SQL compiler resolves these names to the correct StatusId integers automatically.
"""

# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

_CONFIDENCE_THRESHOLD = 0.60


def _build_user_message(question: str, last_turn_context: dict | None) -> str:
    """Build user message with optional prior turn context prefix."""
    if not last_turn_context:
        return question
    prior_intent = last_turn_context.get("intent", "")
    prior_domain = last_turn_context.get("domain", "")
    prior_question = last_turn_context.get("question", "")
    prefix = f'[PRIOR TURN: intent={prior_intent}, domain={prior_domain}, question="{prior_question}"]\nCURRENT: '
    return prefix + question


async def groq_extract(state: GraphState) -> dict[str, Any]:
    """Unified intent + filter extraction via Groq tool calling.

    Flow:
    1. Build user message with optional prior turn context prefix
    2. Groq tool call → structured intent + filters + follow-up signals
    3. Follow-up inheritance: filter_refinement inherits prior intent/domain
    4. Intent mutation safety net (benched_resources+skill, active_projects+client)
    5. RBAC gate on extracted domain
    6. Validate + build FilterClause objects from extracted filters
    7. Return {domain, intent, confidence, filters}

    On any Groq failure → returns confidence=0.0 to trigger llm_fallback.
    """
    question = state["question"]
    user_role = state.get("user_role")
    last_turn_context = state.get("last_turn_context")

    # ── 1. Build user message ───────────────────────────────────────────────
    user_message = _build_user_message(question, last_turn_context)

    messages = [
        LLMMessage(role="system", content=_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_message),
    ]
    config = LLMConfig(
        model=settings.groq_model,
        temperature=0.1,
        max_tokens=512,
        top_p=1.0,
    )

    # ── 2. Groq tool call ───────────────────────────────────────────────────
    try:
        provider = _get_groq_provider()
        result = await provider.complete_with_tools(messages, _TOOL_SCHEMA, config)
        args = result["arguments"]
        latency_ms = result["latency_ms"]
    except Exception as e:
        from app.core.exceptions import RateLimitError as _RateLimitError

        if isinstance(e, _RateLimitError):
            raise
        error_str = str(e)
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
    is_follow_up = args.get("is_follow_up", False)
    follow_up_type = args.get("follow_up_type", "none")

    # Filter out entries with empty values (safety net)
    raw_filters = [f for f in raw_filters if f.get("values")]

    # ── 3. Follow-up inheritance ────────────────────────────────────────────
    if is_follow_up and follow_up_type == "filter_refinement" and last_turn_context:
        intent = last_turn_context.get("intent", intent)
        domain = last_turn_context.get("domain", domain)
        logger.info(
            "groq_extractor: followup_inherited intent=%s domain=%s filters=%d",
            intent,
            domain,
            len(raw_filters),
        )
    elif follow_up_type == "topic_switch":
        logger.info(
            "groq_extractor: topic_switch detected → new intent=%s",
            intent,
        )

    # ── 4. Intent mutation safety net ──────────────────────────────────────
    if intent == "benched_resources" and any(f.get("field") == "skill" for f in raw_filters):
        intent = "benched_by_skill"
        domain = "resource"

    if intent == "active_projects" and any(f.get("field") == "client_name" for f in raw_filters):
        intent = "project_by_client"
        domain = "project"

    logger.info(
        "groq_extractor: q=%r intent=%s domain=%s confidence=%.2f filters=%d latency=%.0fms",
        question[:80],
        intent,
        domain,
        confidence,
        len(raw_filters),
        latency_ms,
    )

    # ── 5. RBAC gate ────────────────────────────────────────────────────────
    if user_role == "user" and domain != "user_self":
        logger.info(
            "groq_extractor: rbac_gate role=user domain=%s intent=%s → llm_fallback",
            domain,
            intent,
        )
        return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}

    # Normalize 'unknown' intent/domain to None so llm_fallback generates fresh SQL
    if intent == "unknown" or domain == "unknown":
        return {"domain": None, "intent": None, "confidence": 0.0, "filters": []}

    # ── 6. Build FilterClause objects ───────────────────────────────────────
    filters: list[FilterClause] = []
    for raw in raw_filters:
        field_name = raw.get("field", "")
        op = raw.get("op", "eq")
        values = raw.get("values", [])

        if not field_name or not values:
            continue

        sanitized = [_sanitize_value(str(v)) for v in values if str(v).strip()]
        if not sanitized:
            continue

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

    return {
        "domain": domain,
        "intent": intent,
        "confidence": confidence,
        "filters": filters,
    }


def route_after_groq(state: GraphState) -> str:
    """Conditional edge: route based on Groq extraction confidence."""
    if state.get("intent") == "unknown":
        logger.info("route_after_groq: intent=unknown → llm_fallback (no catalog coverage)")
        return "llm_fallback"
    if state["confidence"] >= _CONFIDENCE_THRESHOLD:
        return "run_domain_tool"
    return "llm_fallback"
