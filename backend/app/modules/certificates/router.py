"""
HTTP layer for /api/v1/certificates/* and /api/v1/certificate-templates.
Public verification endpoint requires no auth by design — that's the
entire point of a certificate.
"""
import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.certificates.dependencies import (
    get_certificate_service,
    get_template_service,
    get_verification_service,
)
from app.modules.certificates.schemas import (
    CertificateOut,
    IssueCertificateRequest,
    TemplateCreateRequest,
    TemplateOut,
    VerificationResultOut,
)
from app.modules.certificates.service import CertificateService, TemplateService, VerificationService
from app.modules.users.models import User

router = APIRouter(prefix="/certificates", tags=["Certificates"])
template_router = APIRouter(prefix="/certificate-templates", tags=["Certificate Templates"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Issue a certificate",
    description="Idempotent on (user_id, test_id) via the linked result — reissuing returns the "
                "existing certificate. 422 if the result isn't a passing one. pdf_url is always null "
                "in this version — PDF export is a future sprint (see README).",
)
def issue_certificate(
    data: IssueCertificateRequest,
    service: CertificateService = Depends(get_certificate_service),
    user: User = Depends(get_current_user),
):
    certificate = service.issue(data.result_id, user_id=user.id, template_id=data.template_id, actor_id=user.id)
    return success_response(CertificateOut.model_validate(certificate), "Sertifikat berildi.")


@router.get(
    "/me",
    summary="List my certificates",
    description="Paginated list of the current user's own certificates.",
)
def list_my_certificates(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    service: CertificateService = Depends(get_certificate_service),
    user: User = Depends(get_current_user),
):
    items, total = service.list_mine(user.id, page, per_page)
    data = {
        "items": [CertificateOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Mening sertifikatlarim.")


@router.get(
    "/{certificate_id}",
    summary="Get a certificate by ID",
    description="404 if not found or not yours.",
)
def get_certificate(
    certificate_id: uuid.UUID,
    service: CertificateService = Depends(get_certificate_service),
    user: User = Depends(get_current_user),
):
    certificate = service.get(certificate_id, user_id=user.id)
    return success_response(CertificateOut.model_validate(certificate), "Sertifikat topildi.")


@router.get(
    "/verify/{code}",
    summary="Publicly verify a certificate by its verification code",
    description="No authentication required — this is the whole point of a certificate. "
                "Increments the verification counter on every check. 404 (generic) for an unknown code.",
)
def verify_certificate(
    code: str,
    request: Request,
    service: VerificationService = Depends(get_verification_service),
):
    result: VerificationResultOut = service.verify(code, ip=request.client.host if request.client else None)
    return success_response(result, "Tekshiruv natijasi.")


@template_router.get(
    "",
    summary="List active certificate templates",
    description="Public — browsing templates before requesting a certificate.",
)
def list_templates(service: TemplateService = Depends(get_template_service)):
    templates = service.list_templates()
    return success_response([TemplateOut.model_validate(t) for t in templates], "Sertifikat shablonlari.")


@template_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a certificate template",
    description="Admin content management — the `design` field is a JSONB layout, rendering not implemented this sprint.",
)
def create_template(
    data: TemplateCreateRequest,
    service: TemplateService = Depends(get_template_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    template = service.create_template(data, actor_id=admin.id)
    return success_response(TemplateOut.model_validate(template), "Shablon yaratildi.")
