"""FastAPI dependency wiring for the catalog module."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.catalog.repository import CatalogProductRepository
from app.modules.catalog.service import CatalogProductService


def get_catalog_product_repository(db: Session = Depends(get_db)) -> CatalogProductRepository:
    return CatalogProductRepository(db)


def get_catalog_product_service(repo: CatalogProductRepository = Depends(get_catalog_product_repository)) -> CatalogProductService:
    return CatalogProductService(repo)
