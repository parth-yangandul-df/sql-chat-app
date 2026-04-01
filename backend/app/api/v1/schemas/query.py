from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class TurnContext(BaseModel):
    intent: str
    domain: str
    params: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    sql: str = ""


class QueryRequest(BaseModel):
    connection_id: UUID
    question: str = Field(min_length=1, max_length=1000)
    session_id: UUID | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list, max_length=6)
    last_turn_context: TurnContext | None = None
    clear_context: bool = Field(
        default=False,
        description="Explicitly clear prior context for this query",
    )


class ExecuteSQLRequest(BaseModel):
    connection_id: UUID
    sql: str = Field(min_length=1, max_length=10000)
    original_question: str | None = None  # for history tracking


class QueryResponse(BaseModel):
    id: UUID
    question: str
    generated_sql: str
    explanation: str
    columns: list[str]
    column_types: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool
    summary: str | None
    suggested_followups: list[str]
    llm_provider: str
    llm_model: str
    turn_context: TurnContext | None = None
    topic_switch_detected: bool = Field(
        default=False,
        description="True if the system detected a topic switch and cleared context",
    )


class SQLOnlyResponse(BaseModel):
    generated_sql: str
    explanation: str
    confidence: float
    tables_used: list[str]
    assumptions: list[str]


class QueryHistoryResponse(BaseModel):
    id: UUID
    connection_id: UUID
    natural_language: str
    generated_sql: str | None
    final_sql: str | None
    execution_status: str
    error_message: str | None
    row_count: int | None
    execution_time_ms: float | None
    retry_count: int
    result_summary: str | None
    is_favorite: bool
    created_at: datetime

    model_config = {"from_attributes": True}
