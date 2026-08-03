"""Integration-style tests for LocalDiskStorage against a real temp
directory — the one place in this module that genuinely touches the
filesystem, so it's tested against the real thing, not mocked."""
import io
import tempfile
from pathlib import Path

from app.modules.uploads.storage import LocalDiskStorage


def test_save_and_read_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalDiskStorage(base_dir=tmp)
        path = storage.save("test.txt", io.BytesIO(b"hello world"))
        with storage.read(path) as f:
            assert f.read() == b"hello world"


def test_delete_removes_file():
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalDiskStorage(base_dir=tmp)
        path = storage.save("test.txt", io.BytesIO(b"data"))
        assert Path(path).exists()
        storage.delete(path)
        assert not Path(path).exists()


def test_delete_is_idempotent():
    """Deleting an already-gone file must not raise."""
    with tempfile.TemporaryDirectory() as tmp:
        storage = LocalDiskStorage(base_dir=tmp)
        storage.delete(f"{tmp}/never-existed.txt")  # no exception
