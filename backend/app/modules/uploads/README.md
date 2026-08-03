# Uploads Module — BilimUz

Full design rationale: `docs/Sprint8_Notifications_Settings_Uploads_Architecture.md` (approved). The only module with zero dependencies on any other business module.

## Architecture

Same 8-layer pattern. One addition, `storage.py`, living **inside this module** — `StorageBackend` (abstract) + `LocalDiskStorage` (the only implementation this sprint). This is infrastructure the service depends on, the same relationship a repository has to Postgres — **not a new architectural layer**. `UploadService` never calls `open()`/`os.remove()` directly, only through this interface, so a future move to S3-compatible storage touches `storage.py` only.

## Approved scope boundaries (stated explicitly, not silently assumed)

- **File size limits**: images 10 MB, PDF 20 MB, Office documents 20 MB, audio 50 MB, video 200 MB (`constants.py`).
- **`/uploads/{id}/download` requires authentication** — no public access this sprint.
- **`video.duration_seconds` and `document.page_count` are always `NULL`** — no metadata-extraction library chosen yet. The `Video`/`Document` rows are still created (for FK integrity and future backfill), just missing these two derived fields. Tested explicitly (`test_upload_video_creates_video_metadata_with_null_duration`, `test_upload_document_creates_document_metadata_with_null_page_count`) to prove this is a deliberate, verified state — not an accident.

## Business rules

- **Validation happens before anything touches disk**: MIME type checked against an allowlist (not a denylist — anything unrecognized is rejected, including a disguised executable), size checked against the type-specific limit.
- **The on-disk filename is always a generated UUID**, never derived from the caller's `file_name` — the single most important security property in this module, tested explicitly with a path-traversal-style input (`test_upload_uses_generated_uuid_name_not_original_filename`) to prove the vulnerability class doesn't exist rather than just asserting it in prose.
- **`file_type` routes to exactly one metadata table**: image → `Image`, video → `Video`, document (PDF/Office) → `Document`. **Audio has no dedicated metadata table in the schema** — tracked in `uploads` only, tested explicitly (`test_upload_audio_creates_no_metadata_row`).
- **Soft-delete also removes the physical file** — a deliberate, stated exception to the platform's usual "nothing is really gone" soft-delete convention used everywhere else (`grades`, `topics`, `questions`, etc.). A multi-megabyte orphaned file has no audit value the way an orphaned DB row does, and storage isn't free.

## Database

Tables: `uploads`, `images`, `videos`, `documents` (Module 23, `schema_v2.sql`). No schema change, no migration.

## API

```
POST   /api/v1/uploads                      — multipart upload   Authenticated
GET    /api/v1/uploads/me                     — list my own          Authenticated
GET    /api/v1/uploads/{id}                     — get metadata           Authenticated (owner)
GET    /api/v1/uploads/{id}/download              — stream the file          Authenticated (owner)
DELETE /api/v1/uploads/{id}                         — delete DB row + file      Authenticated (owner)
```

Ownership pattern matches `attempts`/`results`/`certificates` exactly (404-not-403, no separate Admin-bypass endpoint) — no new access-control shape introduced.

## Flow — upload a file

```
POST /uploads (multipart)
  → UploadService.upload(stream, filename, content_type, size, user_id)
      → classify_content_type(content_type)   [None → 422 UnsupportedFileTypeException]
      → size > max_size for that category      [422 FileTooLargeException]
      → generated_name = uuid4() + extension_for_content_type(content_type)
      → storage.save(generated_name, stream)    [LocalDiskStorage — writes to storage/uploads/]
      → create Upload(file_name=sanitized_original, file_url=path, file_type, size_bytes)
      → route to Image/Video/Document metadata row (fields NULL where noted above)
      → log_action('upload.created') → commit → return UploadOut
```

## Tests

Three files, 23 tests: `test_upload_validators.py` (11 — MIME classification for every category, unknown-type rejection, disguised-executable rejection, filename sanitization, extension lookup), `test_upload_service.py` (9 — unsupported type, oversized file, successful upload with metadata creation, the path-traversal security test, per-category metadata routing including the audio-has-no-table case, ownership check, delete removes both DB and physical file), `test_local_disk_storage.py` (3 — save/read round-trip and delete-idempotency against a **real** temp directory, not mocked, since this is the one place in the module that genuinely touches the filesystem).

## Future improvements
- Cloud storage backend (S3-compatible) — implement a second `StorageBackend` subclass, swap via the existing `get_storage_backend()` dependency, zero change to `UploadService`.
- Video duration / document page-count extraction, once a parsing library is chosen (flagged, not implemented, per approved scope).
- Public download access for specific contexts (e.g. embeddable lesson media) — deferred, needs a signed-URL or similar pattern, not just removing the auth check.
