"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class AttemptNotFoundException(AppException):
    """Also raised for 'exists but isn't yours' — same status/message for
    both, so a caller can't distinguish 'doesn't exist' from 'not mine'
    (resource enumeration defense, same convention as auth/permissions)."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "ATTEMPT_NOT_FOUND"


class TestNotPublishedException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "TEST_NOT_PUBLISHED"


class MaxAttemptsExceededException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "MAX_ATTEMPTS_EXCEEDED"


class AttemptNotActiveException(AppException):
    """Raised when trying to answer/submit an attempt that's already
    submitted, auto-finished, or cancelled — includes the case where the
    timer expired and lazy auto-finish just ran inside this same request."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "ATTEMPT_NOT_ACTIVE"


class InvalidQuestionReferenceException(AppException):
    """The question_id doesn't belong to this attempt's test."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_QUESTION_REFERENCE"


class InvalidOptionReferenceException(AppException):
    """The selected_option doesn't belong to the referenced question."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_OPTION_REFERENCE"


class ResultNotAvailableException(AppException):
    """The attempt hasn't finished yet — result/correctness data cannot
    be revealed before submit/auto-finish, per platform-wide policy."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "RESULT_NOT_AVAILABLE"


class ModuleNotFoundForAttemptException(AppException):
    """Sprint 50. Also raised for 'module belongs to someone else's
    attempt' — same status/message for both, mirroring
    AttemptNotFoundException's own resource-enumeration defense."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "MODULE_NOT_FOUND"


class ModuleNotActiveException(AppException):
    """Sprint 50. Raised when trying to submit a module that's already
    submitted or whose own expires_at has passed — mirrors
    AttemptNotActiveException's own 409 convention at module scope."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "MODULE_NOT_ACTIVE"


class ExamNotCompleteException(AppException):
    """Sprint 61 — S61-C. Raised by submit_attempt() when a modular
    attempt's module lifecycle isn't finished yet (per
    ModuleExecutionService.is_exam_complete()) — closes the gap where
    a student could call POST /attempts/{id}/submit directly at any
    point mid-exam and finalize against only the modules visited so
    far, bypassing the remaining routed modules entirely instead of
    going through submit_module()'s own per-module completion flow.
    Never raised for a non-modular attempt, or any attempt whose
    module_execution service isn't configured — is_exam_complete()
    itself returns True vacuously when the test has no ExamModule
    rows, so this exception can only fire for a genuinely incomplete
    modular exam. Mirrors AttemptNotActiveException/ModuleNotActiveException's
    existing 409 convention rather than inventing a new status code."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "EXAM_NOT_COMPLETE"
