"""Tests for context-aware classify_intent: _is_refinement_followup() and fast path."""
import pytest
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LAST_TURN = {
    "intent": "benched_resources",
    "domain": "resource",
    "params": {"skill": "Python"},
    "columns": ["employeeid", "ResourceName", "EmailId", "TechCategoryName"],
    "sql": "SELECT DISTINCT r.employeeid FROM resources r WHERE r.IsActive = 0",
}


def _base_state(**overrides):
    state = {
        "question": "show active resources",
        "connection_id": "00000000-0000-0000-0000-000000000001",
        "connector_type": "sqlserver",
        "connection_string": "dsn=test",
        "timeout_seconds": 30,
        "max_rows": 100,
        "db": None,
        "domain": None,
        "intent": None,
        "confidence": 0.0,
        "params": {},
        "sql": None,
        "result": None,
        "generated_sql": None,
        "retry_count": 0,
        "explanation": None,
        "llm_provider": None,
        "llm_model": None,
        "answer": None,
        "highlights": [],
        "suggested_followups": [],
        "execution_id": None,
        "execution_time_ms": None,
        "error": None,
        "conversation_history": [],
        "last_turn_context": None,
        "user_role": None,
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Unit tests for _is_refinement_followup (pure, no async needed)
# ---------------------------------------------------------------------------


def test_is_refinement_followup_which_of_these_with_skill():
    """'Which of these know Python?' + context → True (deictic + skill keyword)."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("Which of these know Python?", _LAST_TURN) is True


def test_is_refinement_followup_filter_by():
    """'Filter by active only' + context → True (filter keyword)."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("Filter by active only", _LAST_TURN) is True


def test_is_refinement_followup_among_them():
    """'Among them, who are assigned?' + context → True."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("Among them, who are assigned?", _LAST_TURN) is True


def test_is_refinement_followup_those_who_billable():
    """'those who are billable' + context → True."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("those who are billable", _LAST_TURN) is True


def test_is_refinement_followup_returns_false_no_deictic():
    """'Show all Python developers' + context → False (no deictic phrase)."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("Show all Python developers", _LAST_TURN) is False


def test_is_refinement_followup_returns_false_no_context():
    """'Which of these know Python?' + None → False (no last_turn_context)."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("Which of these know Python?", None) is False


def test_is_refinement_followup_returns_false_filter_no_context():
    """'Filter by active only' + None → False (no context)."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("Filter by active only", None) is False


def test_is_refinement_followup_deictic_but_no_keyword():
    """Deictic phrase present but no refinement keyword → False."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    # "among them" is deictic but "display" is not a refinement keyword
    assert _is_refinement_followup("Among them, display all", _LAST_TURN) is False


def test_is_refinement_followup_filter_them_keyword():
    """'filter them by available' + context → True."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("filter them by available", _LAST_TURN) is True


def test_is_refinement_followup_only_those():
    """'only those who are inactive' + context → True."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("only those who are inactive", _LAST_TURN) is True


def test_is_refinement_followup_same_ones():
    """'same ones who are billable' + context → True."""
    from app.llm.graph.nodes.intent_classifier import _is_refinement_followup

    assert _is_refinement_followup("same ones who are billable", _LAST_TURN) is True


# ---------------------------------------------------------------------------
# classify_intent fast path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_intent_followup_inherits_prior():
    """classify_intent with deictic follow-up returns inherited intent/domain/0.95."""
    from app.llm.graph.nodes.intent_classifier import classify_intent

    state = _base_state(
        question="Which of these know Python?",
        last_turn_context=_LAST_TURN,
    )

    with patch(
        "app.llm.graph.nodes.intent_classifier.embed_text", AsyncMock()
    ) as mock_embed, patch(
        "app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded", AsyncMock()
    ):
        result = await classify_intent(state)

    # embed_text must NOT be called — this is the fast path
    mock_embed.assert_not_called()

    assert result["domain"] == "resource"
    assert result["intent"] == "benched_resources"
    assert result["confidence"] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_classify_intent_followup_rbac_gate():
    """user_role='user' with resource domain context → confidence=0.0 (RBAC blocked)."""
    from app.llm.graph.nodes.intent_classifier import classify_intent

    state = _base_state(
        question="Which of these know Python?",
        last_turn_context=_LAST_TURN,  # domain="resource"
        user_role="user",
    )

    with patch(
        "app.llm.graph.nodes.intent_classifier.embed_text", AsyncMock()
    ) as mock_embed, patch(
        "app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded", AsyncMock()
    ):
        result = await classify_intent(state)

    mock_embed.assert_not_called()  # fast path still, not embedding

    assert result["confidence"] == pytest.approx(0.0)
    assert result["domain"] is None
    assert result["intent"] is None


@pytest.mark.asyncio
async def test_classify_intent_followup_user_self_domain_passes_rbac():
    """user_role='user' with user_self domain context → allowed (confidence=0.95)."""
    from app.llm.graph.nodes.intent_classifier import classify_intent

    user_self_context = {**_LAST_TURN, "domain": "user_self", "intent": "my_projects"}
    state = _base_state(
        question="Which of these know Python?",
        last_turn_context=user_self_context,
        user_role="user",
    )

    with patch(
        "app.llm.graph.nodes.intent_classifier.embed_text", AsyncMock()
    ) as mock_embed, patch(
        "app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded", AsyncMock()
    ):
        result = await classify_intent(state)

    mock_embed.assert_not_called()
    assert result["confidence"] == pytest.approx(0.95)
    assert result["domain"] == "user_self"


@pytest.mark.asyncio
async def test_classify_intent_normal_path_unchanged():
    """Fresh question with last_turn_context set still goes through embedding (no deictic)."""
    from app.llm.graph.nodes.intent_classifier import classify_intent
    from app.llm.graph.intent_catalog import INTENT_CATALOG

    # Patch catalog so first entry gets matching embedding
    first_entry = INTENT_CATALOG[0]
    identical_embedding = [1.0, 0.0, 0.0]
    first_entry.embedding = identical_embedding

    state = _base_state(
        question="Show all Python developers",  # no deictic phrase
        last_turn_context=_LAST_TURN,  # context present but irrelevant for fresh questions
    )

    with patch(
        "app.llm.graph.nodes.intent_classifier.embed_text",
        AsyncMock(return_value=identical_embedding),
    ) as mock_embed, patch(
        "app.llm.graph.nodes.intent_classifier.ensure_catalog_embedded", AsyncMock()
    ), patch(
        "app.llm.graph.nodes.intent_classifier.get_catalog_embeddings",
        return_value=[[1.0, 0.0, 0.0]] + [[0.0, 1.0, 0.0]] * (len(INTENT_CATALOG) - 1),
    ):
        result = await classify_intent(state)

    # embed_text MUST be called — fresh question takes normal path
    mock_embed.assert_called_once()

    assert result["confidence"] == pytest.approx(1.0, abs=1e-6)
    assert result["domain"] == first_entry.domain
    assert result["intent"] == first_entry.name
