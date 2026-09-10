"""
HTTP layer for /api/v1/uploads/*. Every endpoint requires authentication
— per the approved decision, /download is authenticated-only this
sprint, no public access.
"""
import uuid

from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user
from app.modules.uploads.constants import MULTIPART_PART_SIZE_BYTES
from app.modules.uploads.dependencies import get_upload_service
from app.modules.uploads.schemas import (
    CompleteMultipartUploadRequest,
    CreatePresignedUploadRequest,
    InitiateMultipartUploadOut,
    InitiateMultipartUploadRequest,
    PartUrlOut,
    PartUrlRequest,
    PresignedUploadOut,
    UploadOut,
    ViewUrlOut,
)
from app.modules.uploads.service import UploadService
from app.modules.users.models import User

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file (legacy, backend-mediated)",
    description="Multipart upload — file bytes pass through this backend. Size limits: images "
                "10 MB, PDF/Office documents 20 MB, audio 50 MB, video 20 MB (Sprint 29 — a "
                "deliberately small limit for this endpoint specifically; large video must use "
                "POST /uploads/presigned or /uploads/multipart/initiate instead, where the "
                "browser uploads directly to R2 up to 2 GB and this server never reads the "
                "bytes). MIME type must be on the allowlist — 422 otherwise.",
)
def upload_file(
    file: UploadFile,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    size = file.size or 0
    upload = service.upload(file.file, file.filename or "file", file.content_type or "", size, user_id=user.id)
    return success_response(UploadOut.model_validate(upload), "Fayl yuklandi.")


@router.post(
    "/presigned",
    status_code=status.HTTP_201_CREATED,
    summary="Create a presigned direct-to-storage upload session (Sprint 27)",
    description="Returns a short-lived URL the browser PUTs the file bytes to directly — "
                "file content never transits this backend. If `lesson_id` is provided, requires "
                "Admin/Super Admin/Teacher (matches Lessons' own write RBAC exactly); omit it for "
                "a personal upload (any authenticated user, same as the existing POST /uploads).",
)
def create_presigned_upload(
    body: CreatePresignedUploadRequest,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    upload, presigned = service.create_presigned_session(
        body.original_filename, body.content_type, body.size_bytes,
        user_id=user.id, user_role=user.role.name, lesson_id=body.lesson_id,
    )
    return success_response(
        PresignedUploadOut(upload_id=upload.id, upload_url=presigned.url, required_headers=presigned.required_headers),
        "Yuklash sessiyasi yaratildi.",
    )


@router.patch(
    "/{upload_id}/finalize",
    summary="Confirm a direct upload finished successfully (Sprint 27)",
    description="Called by the browser after the presigned PUT to R2 succeeds. Flips the upload "
                "from pending to ready. 404 if not found or not yours.",
)
def finalize_upload(
    upload_id: uuid.UUID,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    upload = service.finalize_upload(upload_id, user_id=user.id)
    return success_response(UploadOut.model_validate(upload), "Fayl tayyor.")


@router.get(
    "/{upload_id}/view-url",
    summary="Get a short-lived signed URL to view/play this file (Sprint 27)",
    description="Lesson-linked media: any authenticated user (matches the underlying Lesson's own "
                "public GET). Personal (non-lesson) uploads: owner only, 404 otherwise. 409 if the "
                "upload hasn't been finalized yet.",
)
def get_view_url(
    upload_id: uuid.UUID,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    url = service.get_view_url(upload_id, user_id=user.id)
    return success_response(ViewUrlOut(view_url=url), "Ko'rish havolasi yaratildi.")


# --- Sprint 27 Amendment: R2 Multipart Upload (2 GB video support) ---

@router.post(
    "/multipart/initiate",
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a multipart upload session for a large video (Sprint 27 Amendment)",
    description="Used for files above the multipart threshold (see MULTIPART_THRESHOLD_BYTES) — up to "
                "2 GB. Same validation/RBAC ordering as POST /uploads/presigned. Returns the real R2 "
                "multipart upload ID and the total part count the browser should slice the file into.",
)
def initiate_multipart_upload(
    body: InitiateMultipartUploadRequest,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    upload, multipart_upload_id, total_parts = service.initiate_multipart_upload(
        body.original_filename, body.content_type, body.size_bytes,
        user_id=user.id, user_role=user.role.name, lesson_id=body.lesson_id,
    )
    return success_response(
        InitiateMultipartUploadOut(
            upload_id=upload.id, multipart_upload_id=multipart_upload_id,
            total_parts=total_parts, part_size_bytes=MULTIPART_PART_SIZE_BYTES,
        ),
        "Ko'p qismli yuklash boshlandi.",
    )


@router.post(
    "/multipart/{upload_id}/part-url",
    summary="Get a presigned URL for one part of a multipart upload (Sprint 27 Amendment)",
    description="404 if the upload doesn't exist or isn't yours. 409 if this upload was never "
                "initiated as a multipart session. The object key and R2 multipart upload ID are "
                "always looked up server-side from the owned Upload row — never accepted from the request.",
)
def get_multipart_part_url(
    upload_id: uuid.UUID,
    body: PartUrlRequest,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    url = service.get_part_upload_url(upload_id, user_id=user.id, part_number=body.part_number)
    return success_response(PartUrlOut(part_number=body.part_number, upload_url=url), "Qism uchun havola yaratildi.")


@router.post(
    "/multipart/{upload_id}/complete",
    summary="Complete a multipart upload (Sprint 27 Amendment)",
    description="Called by the browser after every part has uploaded successfully. Backend calls R2's "
                "CompleteMultipartUpload with the given (part_number, ETag) pairs and flips the upload to ready.",
)
def complete_multipart_upload(
    upload_id: uuid.UUID,
    body: CompleteMultipartUploadRequest,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    parts = [(p.part_number, p.etag) for p in body.parts]
    upload = service.complete_multipart_upload(upload_id, user_id=user.id, parts=parts)
    return success_response(UploadOut.model_validate(upload), "Yuklash yakunlandi.")


@router.post(
    "/multipart/{upload_id}/abort",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Abort a multipart upload (Sprint 27 Amendment)",
    description="Cancels the R2-side multipart session (releasing already-uploaded parts) and marks "
                "the Upload row failed — never leaves an orphaned active multipart session on R2.",
)
def abort_multipart_upload(
    upload_id: uuid.UUID,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    service.abort_multipart_upload(upload_id, user_id=user.id)


@router.get(
    "/me",
    summary="List my uploads",
    description="Paginated list of the current user's own uploaded files.",
)
def list_my_uploads(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    items, total = service.list_mine(user.id, page, per_page)
    data = {
        "items": [UploadOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Mening fayllarim.")


@router.get(
    "/{upload_id}",
    summary="Get upload metadata",
    description="404 if not found or not yours.",
)
def get_upload(
    upload_id: uuid.UUID,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    upload = service.get(upload_id, user_id=user.id)
    return success_response(UploadOut.model_validate(upload), "Fayl topildi.")


@router.get(
    "/{upload_id}/download",
    summary="Download the file",
    description="Authentication required — no public access this sprint (approved scope boundary).",
)
def download_upload(
    upload_id: uuid.UUID,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    upload, stream = service.open_for_download(upload_id, user_id=user.id)
    return StreamingResponse(stream, media_type="application/octet-stream", headers={
        "Content-Disposition": f'attachment; filename="{upload.file_name}"'
    })


@router.delete(
    "/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an upload",
    description="Removes both the DB record and the physical file — deliberate exception to the "
                "platform's usual soft-delete-only convention (see README).",
)
def delete_upload(
    upload_id: uuid.UUID,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    service.delete(upload_id, user_id=user.id)
