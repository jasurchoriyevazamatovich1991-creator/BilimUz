"""Data-access layer for Upload, Image, Video, Document — four
repositories in one file, same cohesive-module reasoning as
questions/repository.py."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.uploads.models import Document, Image, Upload, Video


class UploadRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, upload_id: uuid.UUID) -> Upload | None:
        stmt = select(Upload).where(Upload.id == upload_id, Upload.deleted_at.is_(None))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID, page: int, per_page: int) -> tuple[list[Upload], int]:
        stmt = select(Upload).where(Upload.user_id == user_id, Upload.deleted_at.is_(None))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Upload.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def create(self, upload: Upload) -> Upload:
        self.db.add(upload)
        self.db.flush()
        return upload

    def soft_delete(self, upload: Upload) -> None:
        upload.deleted_at = datetime.now(timezone.utc)
        upload.status = "archived"
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()


class ImageRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, image: Image) -> Image:
        self.db.add(image)
        self.db.flush()
        return image


class VideoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, video: Video) -> Video:
        self.db.add(video)
        self.db.flush()
        return video


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document
