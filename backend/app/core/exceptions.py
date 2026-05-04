class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def to_response_content(self) -> dict[str, str]:
        return {"error": self.message}

    def to_stream_event(self) -> dict[str, str | int]:
        return {
            "type": "error",
            "message": self.message,
            "status_code": self.status_code,
        }


class InternalServerError(AppError):
    def __init__(self, message: str = "An unexpected error occurred"):
        super().__init__(message, status_code=500)


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(f"{resource} not found: {resource_id}", status_code=404)


class ConnectionError(AppError):
    def __init__(self, message: str):
        super().__init__(f"Database connection error: {message}", status_code=502)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class SQLSafetyError(AppError):
    def __init__(self, message: str):
        super().__init__(f"SQL safety violation: {message}", status_code=403)


class QueryTimeoutError(AppError):
    def __init__(self, timeout_seconds: int):
        super().__init__(f"Query exceeded timeout of {timeout_seconds} seconds", status_code=408)


class RateLimitError(AppError):
    def __init__(self, message: str = "LLM provider rate limit exceeded. Please retry shortly."):
        super().__init__(message, status_code=429)


def raise_if_provider_rate_limited(exc: Exception, provider_name: str) -> None:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        raise RateLimitError(f"{provider_name} rate limit exceeded. Please retry shortly.") from exc

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if response_status == 429:
        raise RateLimitError(f"{provider_name} rate limit exceeded. Please retry shortly.") from exc
