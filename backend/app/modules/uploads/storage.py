"""
StorageBackend abstraction — lives inside this module, used only by
UploadService. This is infrastructure the service depends on, the same
relationship a repository has to Postgres — NOT a new architectural
layer between Router/Service/Repository.

Sprint 27: added R2Storage, exactly as this module's own README already
proposed ("implement a second StorageBackend subclass, swap via the
existing get_storage_backend() dependency, zero change to
UploadService"). LocalDiskStorage is completely unchanged — the two new
presigned-URL methods on the ABC have default NotImplementedError
bodies (not abstract), so LocalDiskStorage needs no new code and every
existing test for it keeps passing unmodified.
"""
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class PresignedUpload:
    """What the frontend needs to PUT a file directly to storage."""
    url: str
    object_key: str
    required_headers: dict[str, str]


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

    def create_presigned_upload(self, object_key: str, content_type: str, expires_in: int) -> PresignedUpload:
        """Sprint 27: a short-lived URL the BROWSER PUTs the file bytes
        to directly — the backend never proxies large media through
        itself. Only meaningful for a real object-storage backend;
        LocalDiskStorage has no equivalent (there is nothing for a
        browser to PUT to directly on a single-server local-disk setup),
        so it inherits this default rather than pretending to support it."""
        raise NotImplementedError("This storage backend does not support direct browser uploads")

    def create_presigned_download(self, object_key: str, expires_in: int) -> str:
        """Sprint 27: a short-lived, object-specific GET URL — the
        mechanism that keeps a private R2 bucket private while still
        letting an authorized browser view/play the file directly."""
        raise NotImplementedError("This storage backend does not support presigned downloads")

    # --- Sprint 27 Amendment: R2 Multipart Upload (2 GB video support) ---
    # Same reasoning as the two methods above: concrete, NotImplementedError
    # defaults (not abstract) so LocalDiskStorage needs zero new code and
    # every existing LocalDiskStorage test keeps passing unmodified.

    def create_multipart_upload(self, object_key: str, content_type: str) -> str:
        """Starts an R2-side multipart session, returns R2's own
        multipart upload ID (stored on the Upload row so later
        part-url/complete/abort calls can reference it)."""
        raise NotImplementedError("This storage backend does not support multipart upload")

    def create_presigned_part_url(self, object_key: str, multipart_upload_id: str, part_number: int, expires_in: int) -> str:
        """A short-lived URL for uploading exactly one part — the
        browser PUTs that part's byte range directly to R2."""
        raise NotImplementedError("This storage backend does not support multipart upload")

    def complete_multipart_upload(self, object_key: str, multipart_upload_id: str, parts: list[dict]) -> None:
        """`parts` is `[{"PartNumber": int, "ETag": str}, ...]` for
        every successfully uploaded part, in order. R2 assembles the
        final object from them server-side — no bytes pass through
        this backend."""
        raise NotImplementedError("This storage backend does not support multipart upload")

    def abort_multipart_upload(self, object_key: str, multipart_upload_id: str) -> None:
        """Cancels an in-progress multipart session and releases the
        already-uploaded parts on R2's side — must never leave an
        orphaned active multipart upload when a user explicitly cancels."""
        raise NotImplementedError("This storage backend does not support multipart upload")


class LocalDiskStorage(StorageBackend):
    """The only StorageBackend implementation before Sprint 27 — matches
    the current single-server docker-compose.yml deployment. `base_dir`
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


class R2Storage(StorageBackend):
    """S3-compatible client against Cloudflare R2 (boto3 — R2 documents
    itself as S3-API-compatible, avoiding a bespoke request-signing
    implementation). The bucket MUST be private — this class never
    constructs a permanent public URL, only short-lived presigned ones.

    `save`/`read`/`delete` are implemented for interface completeness
    and for any small, backend-mediated upload that still goes through
    the original POST /uploads flow — the primary large-media path uses
    `create_presigned_upload`/`create_presigned_download` instead, so
    the browser talks to R2 directly and file bytes never transit this
    server.
    """

    def __init__(self, *, account_id: str, access_key_id: str, secret_access_key: str, bucket: str, endpoint: str):
        import boto3  # imported lazily — only when this backend is actually selected,
        # so an environment with STORAGE_BACKEND=local never needs boto3 installed/importable.

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",  # R2 has no regions — "auto" is R2's own documented convention
        )

    def save(self, filename: str, stream: BinaryIO) -> str:
        self._client.upload_fileobj(stream, self._bucket, filename)
        return filename  # the object key IS the reference stored in uploads.file_url

    def delete(self, file_url: str) -> None:
        # delete_object is already idempotent in the S3 API (no error on
        # a missing key) — no extra handling needed to match this
        # interface's idempotency requirement.
        self._client.delete_object(Bucket=self._bucket, Key=file_url)

    def read(self, file_url: str) -> BinaryIO:
        response = self._client.get_object(Bucket=self._bucket, Key=file_url)
        return response["Body"]

    def create_presigned_upload(self, object_key: str, content_type: str, expires_in: int) -> PresignedUpload:
        url = self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )
        return PresignedUpload(url=url, object_key=object_key, required_headers={"Content-Type": content_type})

    def create_presigned_download(self, object_key: str, expires_in: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )

    # --- Sprint 27 Amendment: R2 Multipart Upload ---

    def create_multipart_upload(self, object_key: str, content_type: str) -> str:
        response = self._client.create_multipart_upload(Bucket=self._bucket, Key=object_key, ContentType=content_type)
        return response["UploadId"]

    def create_presigned_part_url(self, object_key: str, multipart_upload_id: str, part_number: int, expires_in: int) -> str:
        return self._client.generate_presigned_url(
            "upload_part",
            Params={"Bucket": self._bucket, "Key": object_key, "UploadId": multipart_upload_id, "PartNumber": part_number},
            ExpiresIn=expires_in,
        )

    def complete_multipart_upload(self, object_key: str, multipart_upload_id: str, parts: list[dict]) -> None:
        self._client.complete_multipart_upload(
            Bucket=self._bucket, Key=object_key, UploadId=multipart_upload_id,
            MultipartUpload={"Parts": parts},
        )

    def abort_multipart_upload(self, object_key: str, multipart_upload_id: str) -> None:
        # abort_multipart_upload is idempotent in the S3 API (no error
        # if already aborted/completed) — matches this interface's
        # existing idempotency requirement, same as delete().
        self._client.abort_multipart_upload(Bucket=self._bucket, Key=object_key, UploadId=multipart_upload_id)
