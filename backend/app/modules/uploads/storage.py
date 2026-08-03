"""
StorageBackend abstraction — lives inside this module, used only by
UploadService. This is infrastructure the service depends on, the same
relationship a repository has to Postgres — NOT a new architectural
layer between Router/Service/Repository.

Only a local-disk implementation ships this sprint (per the approved
architecture — cloud storage is a future extension). UploadService never
calls `open()`/`os.remove()` directly; it only ever calls through this
interface, so swapping to S3-compatible storage later touches this file
only.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageBackend(ABC):
    @abstractmethod
    def save(self, filename: str, stream: BinaryIO) -> str:
        """Writes the stream to storage, returns a reference (path/URL)
        suitable for storing in `uploads.file_url`."""
        ...

    @abstractmethod
    def delete(self, file_url: str) -> None:
        """Removes the file. Must not raise if the file is already gone
        — delete is idempotent, matching every other module's delete
        semantics (calling it twice is not an error)."""
        ...

    @abstractmethod
    def read(self, file_url: str) -> BinaryIO:
        """Opens the file for reading — used by the /download endpoint."""
        ...


class LocalDiskStorage(StorageBackend):
    """The only StorageBackend implementation this sprint — matches the
    current single-server docker-compose.yml deployment. `base_dir`
    defaults to backend/storage/uploads/, created if missing."""

    def __init__(self, base_dir: str = "storage/uploads"):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, stream: BinaryIO) -> str:
        target = self._base_dir / filename
        with open(target, "wb") as f:
            f.write(stream.read())
        return str(target)

    def delete(self, file_url: str) -> None:
        try:
            os.remove(file_url)
        except FileNotFoundError:
            pass  # idempotent — already gone is not an error

    def read(self, file_url: str) -> BinaryIO:
        return open(file_url, "rb")
