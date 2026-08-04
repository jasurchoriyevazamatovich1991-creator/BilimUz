"""Unit tests for AuditLogOut — specifically the metadata_ -> metadata
attribute aliasing, since SQLAlchemy's `AuditLog` model necessarily
names the Python attribute `metadata_` (SQLAlchemy reserves `metadata`
on the declarative base) while the API response must expose it as
`metadata`."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.audit_logs.schemas import AuditLogOut


def _fake_audit_log(metadata_value=None):
    return SimpleNamespace(
        id=uuid.uuid4(), user_id=uuid.uuid4(), action="test.created",
        entity_type="test", entity_id=uuid.uuid4(), ip_address="127.0.0.1",
        metadata_=metadata_value, created_at=datetime.now(timezone.utc),
    )


def test_metadata_attribute_is_correctly_aliased():
    """The core guarantee: reading from an ORM-shaped object's
    `metadata_` attribute must populate the schema's `metadata` field."""
    log = _fake_audit_log(metadata_value={"key": "value"})
    result = AuditLogOut.model_validate(log)
    assert result.metadata == {"key": "value"}


def test_metadata_json_output_uses_unaliased_key():
    """The JSON response key must be 'metadata', not 'metadata_' — a
    client should never see the SQLAlchemy-internal attribute name."""
    log = _fake_audit_log(metadata_value={"tokens_used": 42})
    result = AuditLogOut.model_validate(log)
    dumped = result.model_dump(by_alias=True)
    assert "metadata" in dumped
    assert "metadata_" not in dumped
    assert dumped["metadata"] == {"tokens_used": 42}


def test_none_metadata_is_allowed():
    log = _fake_audit_log(metadata_value=None)
    result = AuditLogOut.model_validate(log)
    assert result.metadata is None
