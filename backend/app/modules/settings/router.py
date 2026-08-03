"""
HTTP layer for /api/v1/settings/*. Provider-credential endpoints
(smtp/payment/ai) are Super Admin only for BOTH read and write — stricter
than every other module's Admin+SuperAdmin pattern, since even non-secret
fields here (host, port, provider name) describe infrastructure topology.
"""
from fastapi import APIRouter, Depends, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import require_roles
from app.modules.settings.dependencies import (
    get_ai_settings_service,
    get_general_settings_service,
    get_payment_settings_service,
    get_smtp_settings_service,
)
from app.modules.settings.schemas import (
    AiSettingsOut,
    AiSettingsUpsertRequest,
    GeneralSettingOut,
    GeneralSettingUpsertRequest,
    PaymentSettingsOut,
    PaymentSettingsUpsertRequest,
    SmtpSettingsOut,
    SmtpSettingsUpsertRequest,
)
from app.modules.settings.service import (
    AiSettingsService,
    GeneralSettingsService,
    PaymentSettingsService,
    SmtpSettingsService,
)
from app.modules.users.models import User

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/general", summary="List general settings", description="Non-secret, key-value platform configuration.")
def list_general(
    service: GeneralSettingsService = Depends(get_general_settings_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    items = service.list_all()
    return success_response([GeneralSettingOut.model_validate(i) for i in items], "Umumiy sozlamalar.")


@router.put("/general/{key}", summary="Upsert a general setting", description="Create or update a key-value setting.")
def upsert_general(
    key: str,
    data: GeneralSettingUpsertRequest,
    service: GeneralSettingsService = Depends(get_general_settings_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    setting = service.upsert(key, data.value, actor_id=admin.id)
    return success_response(GeneralSettingOut.model_validate(setting), "Sozlama saqlandi.")


@router.get(
    "/smtp",
    summary="Get SMTP configuration",
    description="The `password` field does not exist in this response — structurally absent, not masked.",
)
def get_smtp(
    service: SmtpSettingsService = Depends(get_smtp_settings_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    smtp = service.get()
    return success_response(SmtpSettingsOut.model_validate(smtp) if smtp else None, "SMTP sozlamalari.")


@router.put(
    "/smtp",
    summary="Set SMTP configuration",
    description="`password` is encrypted before storage (Fernet, app.core.security.encryption) and never returned.",
)
def set_smtp(
    data: SmtpSettingsUpsertRequest,
    service: SmtpSettingsService = Depends(get_smtp_settings_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    smtp = service.upsert(data.host, data.port, data.username, data.password, data.from_email, actor_id=admin.id)
    return success_response(SmtpSettingsOut.model_validate(smtp), "SMTP sozlamalari saqlandi.")


@router.get(
    "/payment/{provider}",
    summary="Get payment provider configuration",
    description="`secret_key` does not exist in this response.",
)
def get_payment(
    provider: str,
    service: PaymentSettingsService = Depends(get_payment_settings_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    payment = service.get(provider)
    return success_response(PaymentSettingsOut.model_validate(payment), "To'lov sozlamalari.")


@router.put(
    "/payment",
    status_code=status.HTTP_200_OK,
    summary="Set payment provider configuration",
    description="`secret_key` is encrypted before storage and never returned. One row per provider (unique constraint).",
)
def set_payment(
    data: PaymentSettingsUpsertRequest,
    service: PaymentSettingsService = Depends(get_payment_settings_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    payment = service.upsert(data.provider, data.merchant_id, data.secret_key, actor_id=admin.id)
    return success_response(PaymentSettingsOut.model_validate(payment), "To'lov sozlamalari saqlandi.")


@router.get("/ai", summary="Get AI provider configuration", description="`api_key` does not exist in this response.")
def get_ai(
    service: AiSettingsService = Depends(get_ai_settings_service),
    _admin: User = Depends(require_roles("Super Admin")),
):
    ai = service.get()
    return success_response(AiSettingsOut.model_validate(ai) if ai else None, "AI sozlamalari.")


@router.put(
    "/ai",
    summary="Set AI provider configuration",
    description="`api_key` is encrypted before storage and never returned.",
)
def set_ai(
    data: AiSettingsUpsertRequest,
    service: AiSettingsService = Depends(get_ai_settings_service),
    admin: User = Depends(require_roles("Super Admin")),
):
    ai = service.upsert(data.provider, data.api_key, data.model, actor_id=admin.id)
    return success_response(AiSettingsOut.model_validate(ai), "AI sozlamalari saqlandi.")
