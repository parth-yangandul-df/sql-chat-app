"""Auth endpoints — login + JWT issuance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.user import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    resource_id: int | None
    employee_id: str | None


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """Authenticate with email + password, return a signed JWT.

    The token payload carries: sub (user UUID), email, role, resource_id, exp.
    No refresh tokens in this phase — tokens expire after jwt_expiry_seconds.
    """
    # Look up user by email
    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    # Constant-time check: always verify even if user is None to prevent timing attacks
    password_bytes = body.password.encode("utf-8")
    dummy_hash = b"$2b$12$000000000000000000000000000000000000000000000000000000000"

    stored_hash = user.hashed_password.encode("utf-8") if user else dummy_hash

    try:
        password_matches = bcrypt.checkpw(password_bytes, stored_hash)
    except Exception:
        password_matches = False

    if not user or not user.is_active or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Issue JWT
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=settings.jwt_expiry_seconds)

    payload: dict = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "resource_id": user.resource_id,
        "employee_id": user.employee_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    return LoginResponse(
        access_token=token,
        role=user.role,
        resource_id=user.resource_id,
        employee_id=user.employee_id,
    )
