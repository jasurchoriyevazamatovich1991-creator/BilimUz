"""FastAPI dependency wiring for the uploads module."""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.lessons.repository import LessonRepository
from app.modules.uploads.repository import DocumentRepository, ImageRepository, UploadRepository, VideoRepository
from app.modules.uploads.service import UploadService
from app.modules.uploads.storage import LocalDiskStorage, R2Storage, StorageBackend

settings = get_settings()


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Sprint 27: chooses R2Storage only when STORAGE_BACKEND=r2 is set
    explicitly — every existing deployment/dev environment (which never
    sets this) gets the exact same LocalDiskStorage as before, unchanged."""
    if settings.STORAGE_BACKEND == "r2":
        return R2Storage(
            account_id=settings.R2_ACCOUNT_ID,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            bucket=settings.R2_BUCKET_NAME,
            endpoint=settings.R2_ENDPOINT,
        )
    return LocalDiskStorage()


def get_upload_repository(db: Session = Depends(get_db)) -> UploadRepository:
    return UploadRepository(db)


def get_upload_service(
    repo: UploadRepository = Depends(get_upload_repository),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> UploadService:
    return UploadService(repo, ImageRepository(db), VideoRepository(db), DocumentRepository(db), storage, LessonRepository(db))
