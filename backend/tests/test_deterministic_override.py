"""Test stubs for deterministic override module."""

import pytest

from app.llm.graph.nodes.deterministic_override import (
    apply_overrides,
    OverrideResult,
    should_force_new_query,
    merge_override_with_extracted,
)


class TestDeterministicOverrideImports:
    """Verify module can be imported."""

    def test_module_imports(self):
        """Module should import without errors."""
        from app.llm.graph.nodes import deterministic_override
        assert hasattr(deterministic_override, "apply_overrides")

    def test_exports(self):
        """Verify expected exports exist."""
        from app.llm.graph.nodes.deterministic_override import apply_overrides
        assert callable(apply_overrides)


class TestApplyOverrides:
    """Test apply_overrides function."""

    def test_intent_mismatch_forces_new(self):
        """Intent mismatch should force follow_up_type='new'."""
        extracted = {
            "filters": [],
            "follow_up_type": "refine",
        }
        state = {
            "intent": "active_clients",
            "last_intent": "active_resources",
        }
        result = apply_overrides(extracted, state)
        assert result.final_follow_up_type == "new"
        assert result.was_overridden is True
        assert "intent_mismatch" in result.overrides_applied[0]

    def test_same_intent_keeps_llm_type(self):
        """Same intent should keep LLM-extracted follow_up_type."""
        extracted = {
            "filters": [],
            "follow_up_type": "refine",
        }
        state = {
            "intent": "active_resources",
            "last_intent": "active_resources",
        }
        result = apply_overrides(extracted, state)
        assert result.final_follow_up_type == "refine"
        assert result.was_overridden is False

    def test_no_last_intent_keeps_llm_type(self):
        """No last_intent should keep LLM-extracted type."""
        extracted = {
            "filters": [],
            "follow_up_type": "new",
        }
        state = {
            "intent": "active_resources",
            # No last_intent
        }
        result = apply_overrides(extracted, state)
        assert result.final_follow_up_type == "new"
        assert result.was_overridden is False

    def test_empty_extracted_handled(self):
        """Empty extracted dict should be handled gracefully."""
        extracted = {}
        state = {
            "intent": "active_clients",
            "last_intent": "active_resources",
        }
        result = apply_overrides(extracted, state)
        # Empty extracted defaults to "new", so no override detected
        # (the rule only overrides when LLM says something different)
        assert result.final_follow_up_type == "new"
        # was_overridden is False because extracted.get('follow_up_type') returned 'new' 
        # (default), which matches what we'd force anyway


class TestShouldForceNewQuery:
    """Test should_force_new_query helper."""

    def test_intent_mismatch_returns_true(self):
        """Different intents should return True."""
        assert should_force_new_query("active_clients", "active_resources") is True

    def test_same_intent_returns_false(self):
        """Same intent should return False."""
        assert should_force_new_query("active_resources", "active_resources") is False

    def test_none_last_intent_returns_false(self):
        """None last_intent should return False."""
        assert should_force_new_query("active_resources", None) is False

    def test_low_confidence_returns_true(self):
        """Low confidence should return True."""
        assert should_force_new_query("active_resources", "active_resources", 0.2) is True

    def test_high_confidence_returns_false(self):
        """High confidence should return False."""
        assert should_force_new_query("active_resources", "active_resources", 0.8) is False


class TestMergeOverrideWithExtracted:
    """Test merge_override_with_extracted function."""

    def test_merged_result_has_follow_up_type(self):
        """Result should have updated follow_up_type."""
        extracted = {"filters": [], "follow_up_type": "refine"}
        override_result = OverrideResult(
            final_follow_up_type="new",
            overrides_applied=["test_override"],
            was_overridden=True,
        )
        result = merge_override_with_extracted(extracted, override_result)
        assert result["follow_up_type"] == "new"

    def test_merged_result_has_override_marker(self):
        """Result should include override metadata when overridden."""
        extracted = {"filters": [], "follow_up_type": "refine"}
        override_result = OverrideResult(
            final_follow_up_type="new",
            overrides_applied=["test_override"],
            was_overridden=True,
        )
        result = merge_override_with_extracted(extracted, override_result)
        assert "_overrides_applied" in result

    def test_no_override_no_marker(self):
        """No override should not add marker."""
        extracted = {"filters": [], "follow_up_type": "new"}
        override_result = OverrideResult(
            final_follow_up_type="new",
            overrides_applied=[],
            was_overridden=False,
        )
        result = merge_override_with_extracted(extracted, override_result)
        assert "_overrides_applied" not in result