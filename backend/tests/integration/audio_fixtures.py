"""
Task 10.1 — real, decodable audio for upload tests (the server now decodes
every Speaking recording with ffprobe to measure its duration, so fake
"signature + zeros" payloads are rightly rejected). Generated on demand
with ffmpeg (installed in the backend images and CI) and cached per run.
"""
import functools
import shutil
import subprocess
import tempfile
from pathlib import Path

_SPECS = {
    # format: (ffmpeg args, extension)
    "webm": (["-c:a", "libopus", "-b:a", "12k", "-f", "webm"], "webm"),
    "webm_live": (["-c:a", "libopus", "-b:a", "12k", "-f", "webm", "-live", "1"], "webm"),   # MediaRecorder-like: no duration header
    "ogg": (["-c:a", "libopus", "-b:a", "12k", "-f", "ogg"], "ogg"),
    "mp4": (["-c:a", "aac", "-b:a", "16k", "-f", "mp4"], "m4a"),
    "mp3": (["-c:a", "libmp3lame", "-b:a", "16k", "-f", "mp3"], "mp3"),
    "wav": (["-c:a", "pcm_s16le", "-ar", "8000", "-ac", "1", "-f", "wav"], "wav"),
}


@functools.lru_cache(maxsize=None)
def audio_bytes(fmt: str, seconds: float) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required for audio upload tests (install the 'ffmpeg' package)")
    args, ext = _SPECS[fmt]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"a.{ext}"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"sine=frequency=440:duration={seconds}", *args, str(out)], check=True, timeout=120)
        return out.read_bytes()
