"""
HTTP layer for Mock Test entitlement management (Admin Management of
Mock Test Entitlements, Task D).

Two groups of endpoints, both documented against the exact roles this
codebase already uses elsewhere for admin-only surfaces:

- /entitlements/admin/* — Admin/Super Admin only (same
  require_roles("Admin", "Super Admin") already used by
  catalog/router.py and payments/router.py — this is the established
  convention for "admin configures something", not a new rule invented
  for this module. Moderator — which the admin PANEL itself is open to,
  per AppRoutes.tsx's "Admin, Super Admin, Moderator" comment — is
  deliberately NOT included: granting/revoking paid-adjacent access is
  a materially different trust level than the catalog/payments actions
  this mirrors, and nothing in the existing codebase grants Moderator
  that level of access anywhere, so it is not assumed here either (spec
  §3 — "do not assume every staff role has permission").
- /entitlements/me — any authenticated user, read-only, scoped to the
  caller's own user_id only (no user_id in the path/body — it comes
  from the token), so there is no way for a user to read or modify
  anyone else's entitlements through this endpoint (spec §3 — "ordinary
  users must not be able to modify their own entitlements" and, by
  construction here, not anyone else's either; this endpoint has no
  mutation at all).
"""
import uuid

from fastapi import APIRouter, Depends, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles, get_current_user
from app.modules.entitlements.dependencies import get_entitlement_service
from app.modules.entitlements.schemas import (
    EntitlementExtendRequest,
    EntitlementGrantRequest,
    EntitlementOut,
    EntitlementRevokeRequest,
)
from app.modules.entitlements.service import EntitlementService
from app.modules.users.models import User

router = APIRouter(prefix="/entitlements", tags=["Mock Test Entitlements"])


@router.post(
    "/admin/grant",
    status_code=status.HTTP_201_CREATED,
    summary="Grant a Mock Test entitlement (Admin)",
    description="Grants one user access to every published mock test under one "
                "subject/exam-direction catalog product (product_type='mock_test'). "
                "409 if the user already holds a current (active or scheduled) "
                "entitlement for that exact product — use POST /{id}/extend instead.",
)
def grant_entitlement(
    data: EntitlementGrantRequest,
    service: EntitlementService = Depends(get_entitlement_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    entitlement = service.grant_mock_test_entitlement(data, actor_id=admin.id)
    return success_response(service.get_display(entitlement.id), "Mock Test ruxsati berildi.")


@router.post(
    "/admin/{entitlement_id}/extend",
    summary="Extend or reactivate a Mock Test entitlement (Admin)",
    description="Updates end_date (and, if the row had already lapsed or been "
                "revoked, reactivates it) without creating a new, conflicting row.",
)
def extend_entitlement(
    entitlement_id: uuid.UUID,
    data: EntitlementExtendRequest,
    service: EntitlementService = Depends(get_entitlement_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    entitlement = service.extend_entitlement(entitlement_id, data, actor_id=admin.id)
    return success_response(service.get_display(entitlement.id), "Ruxsat muddati yangilandi.")


@router.post(
    "/admin/{entitlement_id}/revoke",
    summary="Revoke a Mock Test entitlement (Admin)",
    description="Sets exactly this one entitlement to revoked. Never touches any "
                "other entitlement for the same user or product.",
)
def revoke_entitlement(
    entitlement_id: uuid.UUID,
    data: EntitlementRevokeRequest,
    service: EntitlementService = Depends(get_entitlement_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    entitlement = service.revoke_entitlement(entitlement_id, actor_id=admin.id, reason=data.reason)
    return success_response(service.get_display(entitlement.id), "Ruxsat bekor qilindi.")


@router.get(
    "/admin/users/{user_id}",
    summary="List a user's Mock Test entitlements (Admin)",
    response_model=None,
)
def list_user_entitlements(
    user_id: uuid.UUID,
    service: EntitlementService = Depends(get_entitlement_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    items: list[EntitlementOut] = service.list_for_user_display(user_id)
    return success_response(items, "Foydalanuvchi ruxsatlari.")


@router.get(
    "/me",
    summary="List my own Mock Test entitlements",
    description="Read-only, scoped to the caller's own user_id — no admin controls "
                "exposed here (spec §5 — 'do not expose administrative controls to "
                "ordinary users').",
    response_model=None,
)
def list_my_entitlements(
    service: EntitlementService = Depends(get_entitlement_service),
    current_user: User = Depends(get_current_user),
):
    items: list[EntitlementOut] = service.list_for_user_display(current_user.id)
    return success_response(items, "Mening ruxsatlarim.")
