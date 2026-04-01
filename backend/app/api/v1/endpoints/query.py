from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user
from app.api.v1.schemas.query import ExecuteSQLRequest, QueryRequest, SQLOnlyResponse
from app.db.models.user import User
from app.db.session import get_db
from app.services import query_service

router = APIRouter(prefix="/query", tags=["query"])


@router.post("")
async def execute_query(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
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


@router.post("/execute-sql")
async def execute_sql(
    body: ExecuteSQLRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
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
    current_user: User | None = Depends(get_optional_user),
):
    """Generate SQL without executing it."""
    result = await query_service.generate_sql_only(
        db, body.connection_id, body.question
    )
    return SQLOnlyResponse(**result)
