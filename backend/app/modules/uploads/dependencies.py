"""FastAPI dependency wiring for the uploads module."""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.uploads.repository import DocumentRepository, ImageRepository, UploadRepository, VideoRepository
from app.modules.uploads.service import UploadService
from app.modules.uploads.storage import LocalDiskStorage, StorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    return LocalDiskStorage()


def get_upload_repository(db: Session = Depends(get_db)) -> UploadRepository:
    return UploadRepository(db)


def get_upload_service(
    repo: UploadRepository = Depends(get_upload_repository),
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage_backend),
) -> UploadService:
    return UploadService(repo, ImageRepository(db), VideoRepository(db), DocumentRepository(db), storage)
