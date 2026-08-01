"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class QuestionNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "QUESTION_NOT_FOUND"


class OptionNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "OPTION_NOT_FOUND"


class MediaNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "MEDIA_NOT_FOUND"


class InvalidTestReferenceException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_TEST_REFERENCE"


class InvalidOptionConfigurationException(AppException):
    """Raised when a choice-type question's options don't satisfy the
    rules in constants.py (too few options, wrong number of correct
    answers for the question type)."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_OPTION_CONFIGURATION"


class QuestionInUseException(AppException):
    """Raised when trying to hard-modify a question's core structure
    (e.g. its type) after it already has recorded answers — would
    corrupt historical attempts."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "QUESTION_IN_USE"
