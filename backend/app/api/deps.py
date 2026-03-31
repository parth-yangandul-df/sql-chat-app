"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.user import User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=True)
bearer_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT, look up the user, return the User ORM object.

    Raises 401 on missing/expired/invalid token or inactive user.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of raising 401 when no token is present.

    Use this on endpoints that must remain accessible to the unauthenticated main frontend
    while still identifying the caller when a token is provided (e.g. for role-scoped filtering).
    """
    if credentials is None:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return None

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        return None

    return user


def require_role(*roles: str):
    """Dependency factory: returns a FastAPI dependency that enforces one of the given roles.

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(
            current_user: User = Depends(require_role("admin")),
        ): ...

        @router.get("/any-auth")
        async def any_endpoint(
            current_user: User = Depends(get_current_user),
        ): ...
    """

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted to perform this action",
            )
        return current_user

    return _check
