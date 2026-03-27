"""extract_params node — regex/keyword parameter extraction. No LLM calls."""

from __future__ import annotations

import re
from typing import Any

from app.llm.graph.state import GraphState

# Skill: "with skill X", "skilled in X", "who knows X", "expertise in X"
_SKILL_RE = re.compile(
    r"\b(?:with skill|skilled in|who knows|expertise in)\s+([A-Za-z0-9#+.\-]+)",
    re.IGNORECASE,
)

# ISO date: YYYY-MM-DD
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Resource name: proper noun (Title Case word) after "for", "by", "assigned to", "of"
_NAME_RE = re.compile(
    r"\b(?:for|by|assigned to|of)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
)

# Project name: everything after "on project", "for project", "project named/called", "about project"
# Captures until end-of-string or a question mark; handles hyphens, spaces, mixed case
_PROJECT_NAME_RE = re.compile(
    r"\b(?:on project|for project|project named?|project called|about project)\s+"
    r"([A-Za-z0-9][A-Za-z0-9\-\s]+?)(?:\s*[?]?\s*$)",
    re.IGNORECASE,
)

# Client name: "for client X", "by client X", "client named/called X"
_CLIENT_NAME_RE = re.compile(
    r"\b(?:for client|by client|client named?|client called)\s+"
    r"([A-Za-z0-9][A-Za-z0-9\-\s]+?)(?:\s*[?]?\s*$)",
    re.IGNORECASE,
)


async def extract_params(state: GraphState) -> dict[str, Any]:
    """Extract structured parameters from the question using regex only."""
    question = state["question"]
    params: dict[str, Any] = dict(state.get("params") or {})

    # Skill
    skill_match = _SKILL_RE.search(question)
    if skill_match:
        params["skill"] = skill_match.group(1)

    # Dates (first = start, second = end if present)
    dates = _DATE_RE.findall(question)
    if dates:
        params["start_date"] = dates[0]
    if len(dates) >= 2:
        params["end_date"] = dates[1]

    # Project name (must run before generic resource name to avoid conflicts)
    project_match = _PROJECT_NAME_RE.search(question)
    if project_match:
        params["project_name"] = project_match.group(1).strip()

    # Client name
    client_match = _CLIENT_NAME_RE.search(question)
    if client_match:
        params["client_name"] = client_match.group(1).strip()

    # Resource name (generic fallback — only set if no project/client match claimed it)
    name_match = _NAME_RE.search(question)
    if name_match:
        params["resource_name"] = name_match.group(1)

    return {"params": params}
