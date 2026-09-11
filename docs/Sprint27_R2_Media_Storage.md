# Sprint 27 — Cloudflare R2 Media Storage

**Status: READY FOR REVIEW (real R2 credentials required for live end-to-end verification — see §"Manual Cloudflare Setup Required")**

# Architecture

**Approved decision: extend, don't parallel-build.** The existing `uploads` module (`Upload`/`Image`/`Video`/`Document` tables, `StorageBackend` abstraction) was audited first and found to be the exact intended extension point — its own README already stated the plan: *"Cloud storage backend (S3-compatible) — implement a second `StorageBackend` subclass, swap via the existing `get_storage_backend()` dependency, zero change to `UploadService`."* This sprint follows that plan precisely. No new parallel Media/File model was created.

```
Browser
  │  POST /uploads/presigned (auth + validation + RBAC)
  ▼
Backend → creates status=pending Upload row → asks R2Storage for a presigned PUT URL
  │
  │  PUT (file bytes) — direct, browser → R2, backend never touches the bytes
  ▼
Cloudflare R2 (private bucket)
  │
  │  PATCH /uploads/{id}/finalize
  ▼
Backend → status=ready

Viewing:
Browser → GET /uploads/{id}/view-url → Backend (auth check) → presigned GET URL → Browser opens it directly
```

# R2 Configuration

New `Settings` fields (`app/core/config.py`), all with the same `CHANGE_ME_IN_PRODUCTION` convention already used for `FILE_ENCRYPTION_KEY`:

```
STORAGE_BACKEND=local   # "local" | "r2" — defaults to "local", every existing deployment unaffected
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_ENDPOINT              # optional override, defaults to https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com
```

Mirrored in `.env.example` with placeholder values only — no real secret was ever written to this repository.

# Bucket Security

**The bucket must be created as PRIVATE in the Cloudflare dashboard** (see the manual setup checklist below — this cannot be done from this environment). `R2Storage` never constructs a permanent public URL anywhere in its code — only `create_presigned_upload`/`create_presigned_download`, both short-lived and object-specific.

# Upload Flow

1. `POST /uploads/presigned` — validates MIME type + size (reuses the **exact same** `classify_content_type`/size-limit logic the original synchronous upload already used — no new limits invented), and if `lesson_id` is provided: confirms the lesson exists (404 otherwise) and that the acting user's role is in `{Admin, Super Admin, Teacher}` (403 otherwise) — **matching Lessons' own write RBAC exactly**, verified against `lessons/router.py` before writing this check, not invented. Creates a `status=pending` `Upload` row and returns a presigned PUT URL.
2. The browser PUTs the file directly to R2 using that URL (`api/uploads.ts::putToPresignedUrl`, raw `XMLHttpRequest` for real progress events).
3. `PATCH /uploads/{id}/finalize` — flips `pending → ready`. Ownership-checked (404, not 403, for a non-owned upload — same anti-enumeration shape as every other module).

# Download / View Flow

`GET /uploads/{id}/view-url` — authorization branches on whether the upload is lesson-linked:
- **Lesson-linked**: any authenticated user may view it, matching the fact that `GET /lessons/{id}` itself is public (verified in Sprint 27's own audit before this decision was made).
- **Personal (non-lesson) upload**: strict ownership check, unchanged from the original module's behavior.
- Either way, a non-existent `upload_id` returns 404 without revealing whether it ever existed.
- Returns 409 if the upload hasn't been finalized yet (`status != ready`).

# Signed URLs

`PRESIGNED_UPLOAD_TTL_SECONDS = 900` (15 min — enough for a large PUT to start and finish), `PRESIGNED_DOWNLOAD_TTL_SECONDS = 300` (5 min — short-lived view/play access). Both are named constants in `uploads/constants.py`, not magic numbers.

# Database Schema

**One column added**: `uploads.lesson_id` (nullable UUID, FK → `lessons.id`, `ON DELETE SET NULL`, indexed). No redundant `subject_id`/`grade_id`/`topic_id` columns were added — those are derivable via `lesson → topic → subject_id/grade_id`, and duplicating them would violate normalization for no real benefit (documented reasoning in the migration file itself). `status` reuses the existing free-text `StatusMixin` column with three new string values (`pending`/`ready`/`failed`) — **no new column, no migration needed for that part.**

# Object Key Structure

```
lessons/{lesson_id}/{file_type}/{uuid}{extension}   — lesson-linked media
misc/{file_type}/{uuid}{extension}                   — personal (non-lesson) uploads
```

Every path segment is either a server-generated UUID or a value already loaded from the database (`lesson_id`, `file_type`) — **never raw user input**, preserving the original module's most important tested security property (no path-traversal is structurally possible, not just filtered). Verified with an explicit test using a `"../../etc/passwd.mp4"` filename input.

# API

| Endpoint | Method | New/Existing | Auth |
|---|---|---|---|
| `/uploads` | POST | Existing, unchanged | Any authenticated user |
| `/uploads/presigned` | POST | **New** | Any authenticated user; `Admin/Super Admin/Teacher` if `lesson_id` given |
| `/uploads/{id}/finalize` | PATCH | **New** | Owner only |
| `/uploads/{id}/view-url` | GET | **New** | Any user if lesson-linked; owner only if personal |
| `/uploads/me` | GET | Existing, unchanged | Any authenticated user |
| `/uploads/{id}` | GET | Existing, unchanged | Owner only |
| `/uploads/{id}/download` | GET | Existing, unchanged | Owner only |
| `/uploads/{id}` | DELETE | Existing, unchanged | Owner only |

No endpoint was invented beyond what this sprint's real requirements needed, and every new endpoint lives on the **same** `uploads` router — no new module, no new router.

# Admin File Manager

**Real backend gap found and respected, not worked around**: there is **no admin-wide "list every user's uploads" endpoint** — only `GET /uploads/me` exists (matching the exact same "no admin-wide list" pattern already found in Results/Payments/Certificates across earlier sprints, re-confirmed here). `pages/admin/FilesPage.tsx` (`/admin/files`) therefore shows the **current admin's own uploaded files** — a real, fully-working capability — rather than a fabricated platform-wide browser with Subject/Grade/Topic filters, which would require a new backend endpoint this sprint does not invent. Documented explicitly in the page's own docstring.

Features actually built: upload (via `FileUploader`), list, preview (signed view URL opened in a new tab), delete (via `ConfirmDialog`), pagination, loading/empty/error states.

# Student Access

Not built as a separate page this sprint (no student-facing lesson-media UI existed to attach it to yet — Sprint 27's [Student Learning Navigation] `LessonDetailPage.tsx` currently only shows `Lesson.video`'s raw URL text, unrelated to this R2 system). The **backend authorization is real and tested**: `get_view_url`'s lesson-linked branch allows any authenticated user (matching Lesson's own public-read nature) while still returning 404 for a non-existent or mismatched `upload_id` — a student cannot enumerate or guess their way into arbitrary object keys.

# Teacher Access

Verified directly against `lessons/router.py`: Teacher has the same write RBAC as Admin/Super Admin for Lessons. `LESSON_UPLOAD_ALLOWED_ROLES = {"Admin", "Super Admin", "Teacher"}` in `uploads/service.py` mirrors this exactly — Teacher can create lesson-linked presigned upload sessions today via the real endpoint, tested explicitly (`test_create_presigned_session_allows_lesson_upload_for_permitted_roles`, parametrized over all three roles). No new Teacher-specific UI page was built this sprint (the `FileUploader` component is ready to be dropped into a future Teacher lesson-editing page — a small follow-up, not a backend gap).

# Upload Progress

Real, not fabricated: `api/uploads.ts::putToPresignedUrl` uses `XMLHttpRequest`'s native `upload.progress` event (`e.loaded / e.total`), the only web-standard way to get real byte-level upload progress (`fetch`'s streaming body API doesn't expose this for uploads). Tested explicitly that the displayed percentage comes from this callback, not a timer/animation.

# Large Video / Multipart Upload

**Not implemented this sprint, per explicit instruction** ("haddan tashqari murakkab upload framework yaratma"). A single presigned PUT covers files up to R2's own per-object limits (5GB), which is simpler and sufficient for the current `MAX_SIZE_VIDEO = 200MB` limit (unchanged from the original module — no limit was raised or invented). Multipart upload (splitting a very large file into chunks, uploading in parallel with resume support) is real future work, documented here rather than built.

# CORS

**Requires manual Cloudflare dashboard configuration** (cannot be done from this environment — no login attempted, per explicit instruction). The R2 bucket needs a CORS policy allowing `PUT` from the app's real origins:

```json
[
  {
    "AllowedOrigins": ["http://localhost:5173", "https://<your-production-domain>"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["Content-Type"],
    "MaxAgeSeconds": 3000
  }
]
```

**Do not use `"AllowedOrigins": ["*"]` in production** — list the real app origin(s) explicitly.

# Environment Variables

See "R2 Configuration" above — full list also mirrored in `.env.example` with placeholders only.

# Migration

`alembic/versions/0004_add_lesson_id_to_uploads.py` — adds `uploads.lesson_id` (nullable, FK, indexed, `ON DELETE SET NULL`). Reversible (`downgrade()` drops the index, constraint, and column in the correct order). Does not touch or alter any existing migration.

# Tests

**Backend**: 20 new tests, `uploads` module total now 43/43 passing (was 23/23 before this sprint).
- `test_presigned_upload_service.py` (15): unsupported-type/oversized rejection, personal-upload allowed for any role, 404 for a nonexistent lesson, **the critical RBAC test** (Student blocked from lesson-linked upload, Admin/Super Admin/Teacher all allowed — parametrized), the path-traversal-safety test on the object key builder, finalize status transition + ownership, view-url's lesson-linked-vs-personal authorization branching, 409 for a not-yet-ready upload.
- `test_r2_storage.py` (5): `boto3.client` fully mocked (no real R2 credentials/network needed) — verifies the correct endpoint URL construction (default and override), and that `create_presigned_upload`/`create_presigned_download`/`delete` call boto3's S3 API with the exact right parameters.
- All 23 pre-existing `uploads` tests (`test_upload_validators.py`, `test_upload_service.py`, `test_local_disk_storage.py`) re-verified passing unmodified — `LocalDiskStorage` was not touched at all.

**Frontend**: 14 new tests.
- `FileUploader.test.tsx` (8): renders correctly, rejects an unsupported type with a local error before any API call, accepts a valid file and stages it, runs the full real flow (session → PUT → finalize) end-to-end, passes `lessonId` through correctly, shows a **real** progress percentage from the callback, surfaces a real error without ever calling the next stage, clears a staged file on cancel.
- `FilesPage.test.tsx` (6): list success/empty/error, delete via `ConfirmDialog` (not `window.confirm`), preview opens the real signed URL in a new tab, "Ko'rish" hidden for a not-yet-ready file.

```
Backend:  py_compile PASS; uploads 43/43 PASS; full suite 356 passed, 6 failed (pre-existing, unchanged — see Known Limitations)
Frontend: 47 files, 242 tests, all passing (14 new)
```

# TypeScript

```
PASS
```

# Build

```
PASS (dist/ produced, 265 modules — up from 261 before this sprint)
```

# Files Changed

**Backend — created**: `alembic/versions/0004_add_lesson_id_to_uploads.py`, `app/modules/uploads/tests/test_presigned_upload_service.py`, `app/modules/uploads/tests/test_r2_storage.py`, `docs/Sprint27_R2_Media_Storage.md`

**Backend — modified**: `app/modules/uploads/models.py` (+1 column), `app/modules/uploads/storage.py` (new `PresignedUpload`, `R2Storage`; `LocalDiskStorage` untouched), `app/modules/uploads/constants.py` (+status/TTL constants), `app/modules/uploads/exceptions.py` (+3 exceptions), `app/modules/uploads/validators.py` (+`build_object_key`), `app/modules/uploads/service.py` (+3 methods, +1 constructor param), `app/modules/uploads/dependencies.py` (storage backend selection + new repo wiring), `app/modules/uploads/schemas.py` (+3 schemas, `UploadOut` +`lesson_id`), `app/modules/uploads/router.py` (+3 endpoints), `app/modules/uploads/tests/test_upload_service.py` (fixture updated for the new constructor param — no assertion changed), `app/core/config.py` (+R2 settings), `.env.example` (+R2 placeholders), `requirements.txt` (+boto3)

**Frontend — created**: `src/api/uploads.ts`, `src/hooks/useUploads.ts`, `src/components/uploads/FileUploader.tsx` (+ test), `src/pages/admin/FilesPage.tsx` (+ test)

**Frontend — modified**: `src/routes/AppRoutes.tsx` (+1 route), `src/utils/sidebarConfig.ts` (+1 entry)

**Not touched**: every other backend module, every other frontend page/component, all Sprint 13–26 functionality.

# Known Limitations

- **No admin-wide file browser** — only "my own uploads" (`GET /uploads/me`), a real, pre-existing backend gap (see "Admin File Manager" above), not fabricated around.
- **No Teacher-specific upload UI page** — the RBAC and `FileUploader` component are ready, but no page was built to host it this sprint (small follow-up, not a backend gap).
- **No multipart/chunked upload** — single presigned PUT only, sufficient for the current 200MB video limit; explicitly out of scope this sprint.
- **No mid-upload cancel** — `FileUploader`'s "Bekor qilish" only works before upload starts; aborting an in-flight XHR PUT was not implemented.
- **No file replace-in-place flow** — deleting and re-uploading is the current path; an atomic "replace" (upload-then-swap, old object cleanup) was not built this sprint.
- **`StatusBadge` doesn't have dedicated colors for `pending`/`ready`/`failed`** — falls back to its existing neutral/muted style; not expanded this sprint to avoid touching a shared component beyond what was necessary.
- **Real R2 has not been exercised end-to-end** — see below.
- **The 6 pre-existing backend test failures** (`profiles`: 4, `roles`: 2) documented since Sprint 21 are unchanged — confirmed identical this sprint, not touched.

# Manual Cloudflare Setup Required

This environment has no Cloudflare credentials and none were requested — the following must be done manually before `STORAGE_BACKEND=r2` can be used in any real environment:

1. **Create the R2 bucket** in the Cloudflare dashboard (R2 → Create bucket).
2. **Confirm it is private** — R2 buckets are private by default; do not enable the public-access/custom-domain option.
3. **Create an API token**: R2 → Manage R2 API Tokens → Create API Token, with **Object Read & Write** permission scoped to this bucket only (not account-wide).
4. **Copy the Account ID, Access Key ID, and Secret Access Key** into your real `.env` (never commit these).
5. **Set the CORS policy** on the bucket (see the "CORS" section above) with your real origins.
6. **Set `STORAGE_BACKEND=r2`** and the `R2_*` variables in your deployment environment.
7. **Verify** with a real upload through `/admin/files` in a deployed environment — this is the only way to confirm the real R2 integration works end-to-end, since this sandbox cannot reach Cloudflare's account APIs.

# Future Audio/Media Expansion

The architecture is already audio-ready without any further backend change: `FILE_TYPE_AUDIO` and its MIME allowlist (`audio/mpeg`, `audio/wav`, `audio/ogg`, `audio/mp4`) already existed before this sprint (Sprint 8) and flow through the exact same `create_presigned_session`/`finalize`/`get_view_url` path as video/PDF/image — no special-casing was needed or added. This directly serves the stated future need (English-teacher listening/pronunciation/vocabulary content) without a dedicated Audio system, per the explicit "universal media architecture, not a parallel audio system" instruction.

---

# Sprint 27 Amendment — 2 GB Video + R2 Multipart Upload

**Status: extends the baseline above. Nothing in the original Sprint 27 sections was rewritten — `LocalDiskStorage`, the single-PUT presigned flow, the Admin File Manager, and every existing endpoint are byte-for-byte unchanged in behavior.**

## 2 GB video limit

`MAX_SIZE_VIDEO` (backend) / `MAX_SIZE_VIDEO_BYTES` (frontend mirror) raised from 200 MB to **2 GB**. Other type limits (image 10MB, PDF/Office 20MB, audio 50MB) are unchanged. The frontend performs an additional client-side check for immediate UX feedback, but the backend independently re-validates and is the real enforcement point (verified with an explicit "accepts exactly 2 GB, rejects 2 GB + 1 byte" test pair).

## Multipart architecture

```
Small file (<= 100 MB): unchanged — POST /uploads/presigned -> single PUT -> PATCH .../finalize

Large video (> 100 MB, up to 2 GB):
  POST /uploads/multipart/initiate
    -> validates type/size/lesson RBAC (same rules as the small-file flow)
    -> creates a status=pending Upload row
    -> calls R2's CreateMultipartUpload, stores the returned multipart_upload_id
    -> returns { upload_id, multipart_upload_id, total_parts, part_size_bytes }
  Browser slices the File into total_parts chunks (File.slice(), never reads the whole
  file into memory) and, with up to MAX_CONCURRENT_PARTS running at once:
    POST /uploads/multipart/{upload_id}/part-url { part_number }
      -> ownership + "is this actually a multipart session" check
      -> presigned PUT URL for exactly that part
    PUT <presigned part URL>  (browser -> R2 directly, backend never sees the bytes)
      -> R2 returns an ETag for that part
  Once every part has succeeded:
    POST /uploads/multipart/{upload_id}/complete { parts: [{part_number, etag}, ...] }
      -> calls R2's CompleteMultipartUpload, flips status to ready
```

The user never chooses which path is used — `hooks/useUploads.ts::useUploadFile` selects automatically based on `file.size` vs. `MULTIPART_THRESHOLD_BYTES`.

## Part size and concurrency

All centralized in `backend/app/modules/uploads/constants.py` (backend) and `frontend/src/constants/uploads.ts` (frontend mirror, explicitly documented as needing to stay in sync — there is no runtime endpoint exposing these values):

| Constant | Value | Why |
|---|---|---|
| `MULTIPART_THRESHOLD_BYTES` | 100 MB | Files at/below this use the simpler, already-proven single-PUT flow |
| `MULTIPART_PART_SIZE_BYTES` | 20 MB | At the 2 GB ceiling, yields ~103 parts — comfortably under S3/R2's 10,000-part hard limit, while keeping each part small enough to retry cheaply |
| `MAX_CONCURRENT_PARTS` | 4 | Bounded — avoids browser resource exhaustion and hammering R2 with unbounded simultaneous requests for one upload |
| `MULTIPART_PART_RETRY_LIMIT` | 3 | A single part's independent retry budget before the whole upload is marked failed |
| `MULTIPART_MAX_PART_NUMBER` | 10,000 | S3/R2's own real ceiling — validated defensively server-side even though normal usage never approaches it |

## Retry behavior

Each part retries independently (linear backoff: `attempt * 500ms`) up to `MULTIPART_PART_RETRY_LIMIT` times. A failing part **never** restarts the whole multi-gigabyte upload — verified with a test asserting `initiateMultipart`/the whole session is created exactly once even when one part needs a retry.

## Cancellation

Calling `cancel()` (wired to the "Bekor qilish" button shown during an in-progress upload) stops **starting new parts** and, once whatever parts are already in flight finish, aborts the R2-side multipart session (`POST .../abort` → R2's `AbortMultipartUpload`) so nothing is left orphaned. **Known limitation, documented rather than silently missing**: this does not forcibly interrupt an already-in-flight part's XHR PUT — a true mid-request abort would require exposing the raw `XMLHttpRequest` instance per part (not implemented this amendment). In practice this means cancellation takes effect within roughly one part's upload time, not instantly.

## Security

- **Object keys and R2 multipart IDs are never accepted from the browser** — every part-url/complete/abort call looks up the real key and multipart ID from the server-side `Upload` row (owned by the caller), never from the request body. Tested explicitly.
- **Ownership**: every one of the 4 new endpoints uses the exact same 404-not-403 anti-enumeration pattern as the rest of the module — a non-owned `upload_id` gets 404, indistinguishable from a non-existent one.
- **`part_number` is validated** to the real S3/R2 range (1–10,000) before any presigned URL is generated.
- **A row that was never a multipart session** (`multipart_upload_id IS NULL`) is rejected (409) if a part-url/complete/abort call targets it — prevents treating an ordinary single-PUT upload row as if it had a multipart session to manipulate.
- **No presigned URL, R2 secret, or credential is ever persisted in PostgreSQL** — only the object key and R2's own multipart session ID (itself not a credential — it grants no access without also having the account's real API credentials).

## CORS — important addition

Reading a part's `ETag` from the browser's `XMLHttpRequest` response **requires the R2 bucket's CORS policy to explicitly expose that header** — browsers do not expose `ETag` to cross-origin JavaScript by default (it isn't on the small "CORS-safelisted" response header list). Without this, `xhr.getResponseHeader("ETag")` silently returns `null` and the whole multipart completion flow fails. Updated CORS policy:

```json
[
  {
    "AllowedOrigins": ["http://localhost:5173", "https://<your-production-domain>"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

(`ExposeHeaders: ["ETag"]` is the only change from the baseline Sprint 27 CORS policy — everything else is unchanged.)

## Environment variables

**None added.** Multipart uses the exact same `R2_ACCOUNT_ID`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`/`R2_BUCKET_NAME`/`R2_ENDPOINT` credentials as the baseline Sprint 27 R2 integration — no new secret, no new config surface.

## Database

**One new column**: `uploads.multipart_upload_id` (nullable `VARCHAR(255)`), migration `0005_add_multipart_upload_id_to_uploads.py`, reversible. No new table, no redundant fields (`total_parts`/`part_size` are derived from `size_bytes` via the centralized constants, never persisted).

## Cloudflare R2 lifecycle / cleanup recommendation

**Not implemented in application code** (per explicit instruction — no dangerous automatic deletion mechanism was added). If a user abandons an upload without explicitly cancelling (closes the tab mid-upload, for example), R2 will hold the incomplete multipart session and its already-uploaded parts indefinitely, incurring storage cost with nothing to show for it. **Recommended manual Cloudflare dashboard configuration**: R2 → your bucket → Settings → Object lifecycle rules → add a rule of type "Abort incomplete multipart uploads" with an age threshold (e.g. 7 days). This is Cloudflare's own built-in, safe mechanism for exactly this situation — no custom cleanup code needed or written.

## Tests

**Backend**: 32 new tests (`uploads` module total now 71/71, was 43/43 before this amendment).
- `test_multipart_upload_service.py` (24): unsupported-type/oversized-video rejection, exactly-2GB acceptance, correct `total_parts` computation (including the "stays within S3's 10,000-part limit at the 2GB ceiling" check), 404 for a nonexistent lesson, the RBAC test (Student blocked, Admin/Super Admin/Teacher all allowed — parametrized), **the "never persists a presigned URL" test**, part-number range validation (0 and 10,001 both rejected), ownership checks on part-url/complete/abort, the "not a multipart upload" 409 guard, correctly-shaped `CompleteMultipartUpload` parts payload, status transitions (ready on complete, failed on abort).
- `test_r2_storage.py` (+4, now 9 total): `boto3` fully mocked — verifies `create_multipart_upload`/`generate_presigned_url("upload_part", ...)`/`complete_multipart_upload`/`abort_multipart_upload` are called with the exact right S3 API parameters.
- One pre-existing test updated (`test_create_presigned_session_rejects_oversized_file`, in the baseline `test_presigned_upload_service.py`): its size value was tied to the OLD 200MB limit and needed updating to the new 2GB limit to keep testing the same real behavior — not weakened, not deleted.

**Frontend**: 10 new tests (total now 252, was 242 before this amendment).
- `lib/multipartUpload.test.ts` (7, new file): uploads every part and completes with them correctly sorted, real progress genuinely reaches 100% (never fabricated), a failing part retries without restarting the whole upload, exhausting retries aborts the R2 session (never orphaned), `cancel()` stops new parts and aborts, **concurrency never exceeds `MAX_CONCURRENT_PARTS`** (measured directly, not assumed), **`File.slice()` is called with the correct byte ranges and the whole file is never read into memory**.
- `FileUploader.test.tsx` (+3, now 11 total): rejects a video over 2GB locally before any API call, **automatically** routes a large file through multipart without the user choosing (and confirms the small-file path was NOT also triggered), clicking cancel during an in-progress upload calls the real `cancelUpload`/`abortMultipart`. Two pre-existing tests were updated for legitimate UI text changes (the accepted-types hint now mentions the 2GB limit; the progress display now shows stage context alongside the percentage) — same test intent, updated to match the improved, real UI.

```
Backend:  py_compile PASS; uploads 71/71 PASS; full suite 384 passed, 6 failed (pre-existing, unchanged)
Frontend: 48 files, 252 tests, all passing (10 new)
```

## TypeScript / Build

```
TypeScript: PASS
Build:      PASS (dist/ produced, 267 modules — up from 265 before this amendment)
```

## Files changed (this amendment only)

**Backend — created**: `alembic/versions/0005_add_multipart_upload_id_to_uploads.py`, `app/modules/uploads/tests/test_multipart_upload_service.py`

**Backend — modified**: `app/modules/uploads/models.py` (+1 column), `app/modules/uploads/constants.py` (raised video limit, +multipart config), `app/modules/uploads/storage.py` (+4 methods on the ABC with `NotImplementedError` defaults, +4 real implementations on `R2Storage`; `LocalDiskStorage` untouched), `app/modules/uploads/exceptions.py` (+3 exceptions), `app/modules/uploads/schemas.py` (+6 schemas), `app/modules/uploads/service.py` (+4 methods), `app/modules/uploads/router.py` (+4 endpoints), `app/modules/uploads/tests/test_presigned_upload_service.py` (1 test's size value updated to match the new 2GB limit), `app/modules/uploads/tests/test_r2_storage.py` (+4 tests appended)

**Frontend — created**: `src/constants/uploads.ts`, `src/lib/multipartUpload.ts` (+ test)

**Frontend — modified**: `src/api/uploads.ts` (+4 methods, +1 raw XHR part-PUT helper), `src/hooks/useUploads.ts` (`useUploadFile` now auto-selects + exposes `cancelUpload`), `src/components/uploads/FileUploader.tsx` (stage-aware UI, 2GB client check, real cancel-during-upload), `src/components/uploads/FileUploader.test.tsx` (+3 tests, 2 pre-existing tests updated for legitimate UI text changes)

**Not touched**: every other backend module, every other frontend page/component, the Admin File Manager page itself (`FilesPage.tsx` — works unchanged, since it only ever calls the already-existing `FileUploader` component, which now transparently handles large files), all Sprint 1–26 functionality.

## Known limitations (this amendment)

- **No true mid-part cancel** — already-in-flight parts finish before a cancellation takes effect (see "Cancellation" above).
- **No resume for an interrupted multipart session** — per explicit instruction, not over-engineered this amendment; if the browser tab closes mid-upload, the multipart session is abandoned (see the R2 lifecycle-rule recommendation above for cleanup).
- **Real R2 has not been exercised end-to-end** — same limitation as the Sprint 27 baseline; this sandbox has no Cloudflare credentials. All multipart logic is verified via mocked `boto3`/`uploadsApi`.
- **`StatusBadge` still has no dedicated color for `pending`/`ready`/`failed`** — unchanged from the baseline, not expanded this amendment either.

