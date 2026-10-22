"""Task 10.1 — ffprobe-based duration measurement (needs ffmpeg/ffprobe)."""
import shutil

import pytest

from app.core import media_probe
from tests.integration.audio_fixtures import audio_bytes

pytestmark = pytest.mark.skipif(shutil.which("ffprobe") is None or shutil.which("ffmpeg") is None,
                                reason="ffmpeg/ffprobe not installed")


@pytest.mark.parametrize("fmt, mime", [
    ("webm", "audio/webm"), ("webm_live", "audio/webm"), ("ogg", "audio/ogg"),
    ("mp4", "audio/mp4"), ("mp3", "audio/mpeg"), ("wav", "audio/wav"), ("wav", "audio/x-wav"),
])
def test_measures_duration_from_packets(fmt, mime):
    assert media_probe.audio_duration_seconds(audio_bytes(fmt, 3), mime) == pytest.approx(3, abs=0.15)


def test_demuxer_is_forced_from_the_declared_type():
    with pytest.raises(media_probe.AudioProbeFailed):
        media_probe.audio_duration_seconds(audio_bytes("ogg", 1), "audio/webm")
    with pytest.raises(media_probe.AudioProbeFailed):
        media_probe.audio_duration_seconds(audio_bytes("webm", 1), "audio/x-matroska")


def test_garbage_and_missing_tool(monkeypatch):
    with pytest.raises(media_probe.AudioProbeFailed):
        media_probe.audio_duration_seconds(b"\x1aE\xdf\xa3" + b"\x00" * 100, "audio/webm")
    monkeypatch.setattr(media_probe, "ffprobe_path", lambda: None)
    with pytest.raises(media_probe.AudioProbeUnavailable):
        media_probe.audio_duration_seconds(audio_bytes("webm", 1), "audio/webm")
