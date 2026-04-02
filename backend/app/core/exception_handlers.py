import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Normalize FastAPI HTTPException to the app's {"error": ...} shape."""
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Normalize Pydantic request validation errors to {"error": ...} shape."""
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = " → ".join(str(part) for part in first.get("loc", []) if part != "body")
            msg = first.get("msg", "Validation error")
            detail = f"{loc}: {msg}" if loc else msg
        else:
            detail = "Request validation error"
        return JSONResponse(
            status_code=422,
            content={"error": detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all: normalize any unhandled exception to {"error": ...} shape."""
        logger.error(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={"error": "An unexpected error occurred"},
        )
