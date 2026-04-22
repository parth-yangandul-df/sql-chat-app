"""QueryPlan — structured query representation for the compiler pipeline."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


# Dangerous SQL tokens to sanitize from filter values
_SQL_DANGEROUS_TOKENS = re.compile(
    r"(;|'|--|/\*|\*/|DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE)",
    re.IGNORECASE,
)


def _sanitize_value(value: str) -> str:
    """Strip/escape dangerous SQL characters from filter values."""
    return _SQL_DANGEROUS_TOKENS.sub("", value).strip()


class FilterClause(BaseModel):
    """A single filter condition within a QueryPlan."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: str
    op: Literal["eq", "in", "lt", "gt", "between"]
    values: list[str]

    @field_validator("values", mode="before")
    @classmethod
    def coerce_values_to_str(cls, v: object) -> list[str]:
        """Coerce non-string values (bool, int, float) to strings before strict validation.

        LLMs frequently return booleans (True/False) for boolean fields like 'billable'.
        Map Python booleans to '1'/'0' to match SQL Server BIT column convention.
        """
        if not isinstance(v, list):
            v = [v]
        coerced = []
        for item in v:
            if isinstance(item, bool):
                coerced.append("1" if item else "0")
            elif not isinstance(item, str):
                coerced.append(str(item))
            else:
                coerced.append(item)
        return coerced

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: list[str]) -> list[str]:
        if len(v) > 50:
            raise ValueError("Filter values cannot exceed 50 items")
        return [_sanitize_value(val) for val in v]


class QueryPlan(BaseModel):
    """Complete structured query plan compiled into SQL."""

    model_config = ConfigDict(extra="forbid", strict=True)

    domain: str
    intent: str
    filters: list[FilterClause] = []
    base_intent_sql: str = ""
    schema_version: Literal[1]

    @classmethod
    def from_untrusted_dict(cls, data: dict) -> "QueryPlan":
        """Validate and construct from untrusted external data (e.g. API)."""
        cleaned: dict = {}
        for key, value in data.items():
            # Coerce single string values to [string] for filter values
            if key == "filters" and isinstance(value, list):
                cleaned[key] = [
                    {**f, "values": [f["values"]] if isinstance(f.get("values"), str) else f.get("values", [])}
                    for f in value
                ]
            else:
                cleaned[key] = value
        return cls.model_validate(cleaned)

    def to_api_dict(self) -> dict:
        """Return a serializable dict for turn_context response."""
        return {
            "domain": self.domain,
            "intent": self.intent,
            "filters": [
                {"field": f.field, "op": f.op, "values": f.values}
                for f in self.filters
            ],
            "base_intent_sql": self.base_intent_sql,
            "schema_version": self.schema_version,
        }
