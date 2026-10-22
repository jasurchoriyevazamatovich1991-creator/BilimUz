"""
Task 10.1 — the 15-minute Speaking limit is enforced on the server from the
decoded audio (ffprobe), not from the browser or the container header.
"""
import pytest

from app.modules.attempts.models import Answer
from tests.integration.audio_fixtures import audio_bytes
from tests.integration.test_task6_exam_ui import Ctx, _state


def _setup(client, pg_session):
    ctx = Ctx(client, pg_session)
    test, r1, w1, s1 = ctx.ielts()
    return ctx, ctx.start(test), s1


@pytest.mark.parametrize("seconds", [899, 900])
def test_recordings_up_to_15_minutes_are_accepted(client, pg_session, seconds):
    ctx, attempt_id, s1 = _setup(client, pg_session)
    # MediaRecorder-style WebM: no duration in the header, measured from packets.
    r = ctx.upload(attempt_id, s1, data=audio_bytes("webm_live", seconds))
    assert r.status_code == 201, r.json()
    assert _state(ctx.detail(attempt_id), s1)["has_audio"] is True


@pytest.mark.parametrize("fmt, mime", [("webm_live", "audio/webm"), ("ogg", "audio/ogg"), ("mp3", "audio/mpeg")])
def test_recordings_over_15_minutes_are_rejected(client, pg_session, fmt, mime):
    ctx, attempt_id, s1 = _setup(client, pg_session)
    r = ctx.upload(attempt_id, s1, data=audio_bytes(fmt, 905), mime=mime)
    assert r.status_code == 422
    assert "15 daqiqa" in r.json()["message"]
    assert pg_session.query(Answer).filter(Answer.audio_upload_id.is_not(None), Answer.question_id == s1.id).count() == 0


@pytest.mark.parametrize("data", [
    b"\x1aE\xdf\xa3" + b"\x00" * 4096,                        # correct signature, no decodable audio
    b"\x1aE\xdf\xa3" + bytes(range(256)) * 16,
])
def test_malformed_files_with_a_valid_signature_are_rejected(client, pg_session, data):
    ctx, attempt_id, s1 = _setup(client, pg_session)
    r = ctx.upload(attempt_id, s1, data=data, mime="audio/webm")
    assert r.status_code == 422
    assert "o'qib bo'lmadi" in r.json()["message"]


def test_without_ffprobe_uploads_are_refused_not_accepted_unchecked(client, pg_session, monkeypatch):
    ctx, attempt_id, s1 = _setup(client, pg_session)
    monkeypatch.setattr("app.core.media_probe.ffprobe_path", lambda: None)
    r = ctx.upload(attempt_id, s1, data=audio_bytes("webm_live", 1))
    assert r.status_code == 503
    assert _state(ctx.detail(attempt_id), s1)["has_audio"] is False
