"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class CatalogProductNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "CATALOG_PRODUCT_NOT_FOUND"


class CatalogProductAlreadyExistsException(AppException):
    """Raised when a grade/subject already has a catalog_products row —
    the plain UNIQUE constraint on grade_id/subject_id (see models.py)
    is the DB-level backstop for this same rule."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "CATALOG_PRODUCT_ALREADY_EXISTS"


class InvalidGradeReferenceException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_GRADE_REFERENCE"


class InvalidSubjectReferenceException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_SUBJECT_REFERENCE"
