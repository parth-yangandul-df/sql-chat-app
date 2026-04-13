"""Tests for semantic integration module."""

import pytest
from app.llm.graph.nodes.semantic_integration import (
    get_field_hints,
    normalize_filter_value,
    normalize_values_batch,
    validate_field_mapping,
)


class TestGetFieldHints:
    """Test get_field_hints function."""

    def test_get_field_hints_resource(self):
        """Returns field names for resource domain."""
        hints = get_field_hints("resource")
        assert "ResourceName" in hints
        assert "designation" in hints
        assert "PA_Skills.Name" in hints

    def test_get_field_hints_client(self):
        """Returns field names for client domain."""
        hints = get_field_hints("client")
        assert "ClientName" in hints
        assert "Industry" in hints

    def test_get_field_hints_unknown_domain(self):
        """Returns empty list for unknown domain."""
        hints = get_field_hints("unknown_domain")
        assert hints == []


class TestNormalizeFilterValue:
    """Test normalize_filter_value function."""

    def test_normalize_filter_value_with_mapping(self):
        """Normalizes value using provided value_map."""
        value_map = {
            "designation": {
                "backend": "Backend Developer",
                "frontend": "Frontend Developer",
            }
        }
        result = normalize_filter_value("backend", "designation", value_map)
        assert result == "Backend Developer"

    def test_normalize_filter_value_no_match(self):
        """Returns original value when no mapping exists."""
        value_map = {"designation": {}}
        result = normalize_filter_value("unknown", "designation", value_map)
        assert result == "unknown"

    def test_normalize_filter_value_unknown_field(self):
        """Returns original value for unknown field."""
        value_map = {}
        result = normalize_filter_value("some_value", "unknown_field", value_map)
        assert result == "some_value"


class TestNormalizeValuesBatch:
    """Test normalize_values_batch function."""

    def test_normalize_values_batch_empty(self):
        """Returns empty list for empty input."""
        result = normalize_values_batch([])
        assert result == []

    def test_normalize_values_batch_no_map(self):
        """Returns filters unchanged when no value_map provided."""
        filters = [
            {"field": "designation", "operator": "eq", "value": "backend"},
        ]
        result = normalize_values_batch(filters, None)
        # Should return filters unchanged (graceful degradation)
        assert result == filters


class TestValidateFieldMapping:
    """Test validate_field_mapping function."""

    def test_validate_field_mapping_skill(self):
        """Maps user field to canonical field."""
        result = validate_field_mapping("skill", "resource")
        assert result == "PA_Skills.Name"

    def test_validate_field_mapping_name(self):
        """Maps user field 'name' to ResourceName."""
        result = validate_field_mapping("name", "resource")
        assert result == "ResourceName"

    def test_validate_field_mapping_unknown(self):
        """Returns None for unknown field."""
        result = validate_field_mapping("unknown_field", "resource")
        assert result is None
