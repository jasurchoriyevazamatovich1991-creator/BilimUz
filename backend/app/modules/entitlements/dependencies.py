"""FastAPI dependency wiring for the entitlements module. No router
depends on these yet this phase — kept ready for the phase that adds
the admin grant/revoke endpoints and the student `/entitlements/me`
endpoint, and used directly by this module's own unit tests via plain
constructor calls (these Depends()-wrapped functions are for the HTTP
layer specifically)."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.catalog.dependencies import get_catalog_product_repository
from app.modules.catalog.repository import CatalogProductRepository
from app.modules.entitlements.repository import EntitlementRepository
from app.modules.entitlements.service import EntitlementService
from app.modules.users.dependencies import get_user_repository
from app.modules.users.repository import UserRepository


def get_entitlement_repository(db: Session = Depends(get_db)) -> EntitlementRepository:
    return EntitlementRepository(db)


def get_entitlement_service(
    repo: EntitlementRepository = Depends(get_entitlement_repository),
    product_repo: CatalogProductRepository = Depends(get_catalog_product_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> EntitlementService:
    return EntitlementService(repo, product_repo, user_repo)
