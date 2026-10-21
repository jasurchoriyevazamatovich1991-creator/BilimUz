"""Module-local exceptions — inherit AppException so the global handler
still produces the standard {success, message, data, errors} envelope."""
from fastapi import status

from app.core.exceptions import AppException


class TestNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "TEST_NOT_FOUND"


class InvalidTestReferenceException(AppException):
    """subject_id/grade_id/topic_id don't reference existing rows."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_TEST_REFERENCE"


class InvalidStatusTransitionException(AppException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "INVALID_STATUS_TRANSITION"


class CannotPublishEmptyTestException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "CANNOT_PUBLISH_EMPTY_TEST"


class MockTestRequiresSubjectException(AppException):
    """A test cannot be flagged is_mock_test=True without a subject_id
    — subject_id IS the subject/exam-direction the entitlements module
    keys access on. Mirrors ck_tests_mock_test_requires_subject (the DB
    backstop for this same rule, migration 0021)."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "MOCK_TEST_REQUIRES_SUBJECT"


class ExamSectionNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "EXAM_SECTION_NOT_FOUND"


class ExamModuleNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "EXAM_MODULE_NOT_FOUND"


class DuplicateOrderNumberException(AppException):
    """order_number already used by a sibling row under the same
    parent (test for ExamSection, section for ExamModule) — the exact
    condition UNIQUE(test_id/section_id, order_number) enforces at the
    DB level; this exception lets the service layer surface it as a
    clean 409 instead of a raw IntegrityError."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_ORDER_NUMBER"


class QuestionGroupNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "QUESTION_GROUP_NOT_FOUND"


class RoutingThresholdRuleNotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "ROUTING_THRESHOLD_RULE_NOT_FOUND"


class DuplicateRoutingThresholdRuleException(AppException):
    """(test_id, routing_group, min_ratio) already has a rule — the
    exact condition UNIQUE(test_id, routing_group, min_ratio) enforces
    at the DB level (migration 0019). Mirrors DuplicateOrderNumberException's
    own reasoning: a clean 409 from the service layer instead of a raw
    IntegrityError from a race that slips past this same check."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_ROUTING_THRESHOLD_RULE"


class QuestionGroupMediaNotFoundException(AppException):
    """Task 3 — no active media with this id on this group."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "QUESTION_GROUP_MEDIA_NOT_FOUND"


class UploadNotFoundForGroupMediaException(AppException):
    """Task 3 — upload_id doesn't exist (or was deleted)."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "UPLOAD_NOT_FOUND_FOR_GROUP_MEDIA"


class UnsupportedGroupMediaTypeException(AppException):
    """Task 3 — only audio and image uploads can be attached to a group."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "UNSUPPORTED_GROUP_MEDIA_TYPE"


class GroupMediaUploadNotReadyException(AppException):
    """Task 3 — the upload session hasn't been finalized yet."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "GROUP_MEDIA_UPLOAD_NOT_READY"


class DuplicateGroupMediaException(AppException):
    """Task 3 — this upload is already attached to this group."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_GROUP_MEDIA"


class InvalidScoringConfigurationException(AppException):
    """Task 4 — scoring profile / score component / conversion table rule
    violated (wrong profile, duplicate component, invalid table data...)."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "INVALID_SCORING_CONFIGURATION"


class ScoringConfigurationConflictException(AppException):
    """Task 4 — the change would orphan existing scoring data (e.g.
    changing a section's component after tables were published)."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "SCORING_CONFIGURATION_CONFLICT"
