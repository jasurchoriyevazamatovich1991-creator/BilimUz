"""
Domain-level exceptions and their HTTP mapping.
Services raise these (never HTTPException directly — services must not know
about HTTP). Routers/main.py translate them to responses so internal details
(stack traces, SQL errors) are never exposed to the client.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base class for all domain exceptions."""
    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "APP_ERROR"

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors
        super().__init__(message)


class InvalidCredentialsException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "INVALID_CREDENTIALS"


class UserAlreadyExistsException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "USER_ALREADY_EXISTS"


class UserNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "USER_NOT_FOUND"


class InvalidTokenException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "INVALID_TOKEN"


class VerificationCodeInvalidException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "VERIFICATION_CODE_INVALID"


class RateLimitExceededException(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Registered once in main.py — every AppException becomes this envelope.
    Matches the platform-wide response contract: {success, message, data, errors}."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "data": None,
            "errors": exc.errors or [exc.message],
        },
    )
