"""
Task 10.1 — server-side audio duration check with FFmpeg's ``ffprobe``.

Why ffprobe: it is the maintained reference parser for every format the
Speaking recorder can produce. Pure-Python alternatives do not cover WebM
(Chrome/Firefox MediaRecorder output) and mutagen is GPL-licensed.

What is measured: the end of the last audio packet (max pts + duration),
read from the actual packets — NOT the container's duration header, which
browsers often omit (MediaRecorder WebM has none) and a client can forge.

Hardening for untrusted input:
* the demuxer is forced from the server-validated MIME type (``-f``), so a
  file can only be parsed as the format it was accepted as;
* the process has a wall-clock timeout and receives a temp file path built
  by the server (no user-controlled name);
* stderr is never echoed back to the client.

Deployment requirement: ffprobe must be installed (backend Dockerfiles and
CI install the ``ffmpeg`` package). Without it uploads are refused (503)
rather than accepted unchecked.
"""
import os
import shutil
import subprocess
import tempfile

# server-validated MIME type -> ffprobe demuxer name
DEMUXERS = {
    "audio/webm": "matroska",
    "audio/ogg": "ogg",
    "audio/mp4": "mov",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}
PROBE_TIMEOUT_SECONDS = 30


class AudioProbeUnavailable(Exception):
    """ffprobe is not installed / not executable on this server."""


class AudioProbeFailed(Exception):
    """The file could not be parsed as audio of the declared type."""


def ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


def audio_duration_seconds(data: bytes, mime: str) -> float:
    """Duration in seconds of the first audio stream, from its packets.
    Raises AudioProbeUnavailable or AudioProbeFailed."""
    demuxer = DEMUXERS.get(mime)
    if demuxer is None:
        raise AudioProbeFailed("unsupported type")
    binary = ffprobe_path()
    if binary is None:
        raise AudioProbeUnavailable("ffprobe not found")

    fd, path = tempfile.mkstemp(prefix="speaking-probe-", suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        try:
            proc = subprocess.run(
                [binary, "-v", "error", "-f", demuxer, "-select_streams", "a:0",
                 "-show_entries", "packet=pts_time,duration_time", "-of", "csv=p=0", path],
                capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS, check=False,
            )
        except subprocess.TimeoutExpired:
            raise AudioProbeFailed("probe timed out")
        except OSError:
            raise AudioProbeUnavailable("ffprobe could not be executed")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    if proc.returncode != 0:
        raise AudioProbeFailed("not decodable")
    end = 0.0
    packets = 0
    for line in proc.stdout.splitlines():
        parts = line.strip().split(",")
        if len(parts) < 2:
            continue
        try:
            pts = float(parts[0])
            dur = float(parts[1]) if parts[1] not in ("", "N/A") else 0.0
        except ValueError:
            continue
        packets += 1
        end = max(end, pts + dur)
    if packets == 0 or end <= 0:
        raise AudioProbeFailed("no audio packets")
    return end
