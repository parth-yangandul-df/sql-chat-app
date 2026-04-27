import asyncio
import json
import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.schemas.query import ExecuteSQLRequest, QueryRequest, SQLOnlyResponse
from app.core.exceptions import AppError, InternalServerError
from app.db.models.user import User
from app.db.session import get_db
from app.services import query_service

router = APIRouter(prefix="/query", tags=["query"])

_STREAM_STAGES = [
    {"stage": "extracting", "label": "Extracting intent...", "progress": 25},
    {"stage": "composing", "label": "Composing SQL...", "progress": 50},
    {"stage": "validating", "label": "Validating query...", "progress": 75},
    {"stage": "interpreting", "label": "Interpreting results...", "progress": 95},
]
_STREAM_STAGE_TIMELINE_S = (0.0, 1.1, 2.25, 3.45)
_STREAM_POLL_INTERVAL_S = 0.2


def _json_default(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _encode_stream_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=_json_default)}\n\n"


@router.post("")
async def execute_query(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a natural language question and get SQL + results + interpretation."""
    result = await query_service.execute_nl_query(
        db,
        body.connection_id,
        body.question,
        session_id=body.session_id,
        conversation_history=[t.model_dump() for t in body.conversation_history],
        current_user=current_user,
        last_turn_context=body.last_turn_context.model_dump() if body.last_turn_context else None,
        clear_context=body.clear_context,
    )
    return result


@router.post("/stream")
async def stream_query(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream coarse-grained NL pipeline progress followed by the final result."""

    async def event_generator():
        query_task = asyncio.create_task(
            query_service.execute_nl_query(
                db,
                body.connection_id,
                body.question,
                session_id=body.session_id,
                conversation_history=[t.model_dump() for t in body.conversation_history],
                current_user=current_user,
                last_turn_context=(body.last_turn_context.model_dump() if body.last_turn_context else None),
                clear_context=body.clear_context,
            )
        )

        stage_index = 0
        started_at = time.monotonic()
        yield _encode_stream_event({"type": "stage", **_STREAM_STAGES[stage_index]})

        try:
            while True:
                try:
                    result = await asyncio.wait_for(
                        asyncio.shield(query_task),
                        timeout=_STREAM_POLL_INTERVAL_S,
                    )
                    yield _encode_stream_event({"type": "result", "data": result})
                    break
                except TimeoutError:
                    elapsed = time.monotonic() - started_at
                    while (
                        stage_index < len(_STREAM_STAGES) - 1
                        and elapsed >= _STREAM_STAGE_TIMELINE_S[stage_index + 1]
                    ):
                        stage_index += 1
                        yield _encode_stream_event({"type": "stage", **_STREAM_STAGES[stage_index]})
        except asyncio.CancelledError:
            query_task.cancel()
            raise
        except AppError as exc:
            yield _encode_stream_event(exc.to_stream_event())
        except Exception:
            internal_error = InternalServerError()
            yield _encode_stream_event(internal_error.to_stream_event())

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/execute-sql")
async def execute_sql(
    body: ExecuteSQLRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute user-provided SQL directly (no LLM generation)."""
    result = await query_service.execute_raw_sql(
        db, body.connection_id, body.sql, body.original_question
    )
    return result


@router.post("/sql-only", response_model=SQLOnlyResponse)
async def generate_sql_only(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate SQL without executing it."""
    result = await query_service.generate_sql_only(
        db, body.connection_id, body.question
    )
    return SQLOnlyResponse(**result)
