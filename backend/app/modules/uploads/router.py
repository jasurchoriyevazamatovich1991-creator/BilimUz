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
from app.modules.uploads.dependencies import get_upload_service
from app.modules.uploads.schemas import UploadOut
from app.modules.uploads.service import UploadService
from app.modules.users.models import User

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file",
    description="Multipart upload. Size limits: images 10 MB, PDF/Office documents 20 MB, "
                "audio 50 MB, video 200 MB. MIME type must be on the allowlist — 422 otherwise.",
)
def upload_file(
    file: UploadFile,
    service: UploadService = Depends(get_upload_service),
    user: User = Depends(get_current_user),
):
    size = file.size or 0
    upload = service.upload(file.file, file.filename or "file", file.content_type or "", size, user_id=user.id)
    return success_response(UploadOut.model_validate(upload), "Fayl yuklandi.")


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
