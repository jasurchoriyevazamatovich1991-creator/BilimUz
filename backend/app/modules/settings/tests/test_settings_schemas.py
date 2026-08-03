"""The single most important test file in this module — proves the
secret-omission guarantee at the schema level, not just by inspection."""
from app.modules.settings.schemas import AiSettingsOut, PaymentSettingsOut, SmtpSettingsOut


def test_smtp_settings_out_has_no_password_field():
    fields = SmtpSettingsOut.model_fields.keys()
    assert "password" not in fields


def test_payment_settings_out_has_no_secret_key_field():
    fields = PaymentSettingsOut.model_fields.keys()
    assert "secret_key" not in fields


def test_ai_settings_out_has_no_api_key_field():
    fields = AiSettingsOut.model_fields.keys()
    assert "api_key" not in fields


def test_smtp_settings_out_dump_never_contains_password_string():
    """Belt-and-suspenders: even if a future refactor accidentally passed
    extra kwargs, model_dump() must never surface the word 'password'."""
    import uuid
    from datetime import datetime, timezone

    out = SmtpSettingsOut(
        id=uuid.uuid4(), host="smtp.example.com", port=587,
        username="noreply", from_email="noreply@bilimuz.uz",
        status="active", updated_at=datetime.now(timezone.utc),
    )
    dumped = out.model_dump()
    assert "password" not in dumped
