"""Tests for fallback_intent wiring on all 24 active PRMS catalog entries.

Requirement CTX-04: When a domain tool query returns 0 rows, the pipeline
tries the fallback_intent before escalating to LLM. These tests verify that
all 24 active entries have fallback_intent set per the mapping table.
"""

from app.llm.graph.intent_catalog import INTENT_CATALOG


def test_fallback_intent_count():
    """Exactly 18 entries should have a non-None fallback_intent."""
    with_fallback = [e for e in INTENT_CATALOG if e.fallback_intent is not None]
    assert len(with_fallback) == 18


def test_all_fallback_intents_reference_existing_catalog_names():
    """Every non-None fallback_intent must reference an intent name that exists in the catalog."""
    names = {e.name for e in INTENT_CATALOG}
    for entry in INTENT_CATALOG:
        if entry.fallback_intent is not None:
            assert entry.fallback_intent in names, (
                f"{entry.name}.fallback_intent={entry.fallback_intent!r} not in catalog"
            )


def test_specific_mappings():
    """Spot-check specific fallback_intent mappings per the RESEARCH.md table."""
    by_name = {e.name: e for e in INTENT_CATALOG}
    assert by_name["resource_by_skill"].fallback_intent == "active_resources"
    assert by_name["client_projects"].fallback_intent == "active_clients"
    assert by_name["project_budget"].fallback_intent == "active_projects"
    assert by_name["my_utilization"].fallback_intent == "my_timesheets"
    assert by_name["active_resources"].fallback_intent is None
    assert by_name["active_projects"].fallback_intent is None
