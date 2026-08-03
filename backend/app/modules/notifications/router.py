"""
HTTP layer for /api/v1/notifications/*. Own notifications: any
authenticated user. Everything else (create for others, templates,
queueing, processing): Admin, Super Admin.

POST /queue/process/* returns 501 Not Implemented if called — honestly,
via ProviderNotConfiguredException — since no real SMTP/SMS provider
ships this sprint (approved scope boundary, see providers.py).
"""
import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.schemas import success_response
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.notifications.dependencies import (
    get_notification_service,
    get_queue_service,
    get_template_service,
)
from app.modules.notifications.schemas import (
    CreateNotificationRequest,
    EnqueueEmailRequest,
    EnqueueSmsRequest,
    NotificationOut,
    ProcessQueueRequest,
    ProcessQueueResponse,
    QueueItemOut,
    TemplateCreateRequest,
    TemplateOut,
)
from app.modules.notifications.service import NotificationService, QueueService, TemplateService
from app.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/me", summary="List my notifications", description="Paginated, optionally filtered by ?is_read=.")
def list_my_notifications(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    is_read: bool | None = Query(default=None),
    service: NotificationService = Depends(get_notification_service),
    user: User = Depends(get_current_user),
):
    items, total = service.list_mine(user.id, page, per_page, is_read)
    data = {
        "items": [NotificationOut.model_validate(i) for i in items],
        "meta": {"page": page, "per_page": per_page, "total": total, "total_pages": (total + per_page - 1) // per_page},
    }
    return success_response(data, "Bildirishnomalarim.")


@router.patch("/{notification_id}/read", summary="Mark one notification as read")
def mark_read(
    notification_id: uuid.UUID,
    service: NotificationService = Depends(get_notification_service),
    user: User = Depends(get_current_user),
):
    notification = service.mark_read(notification_id, user_id=user.id)
    return success_response(NotificationOut.model_validate(notification), "O'qilgan deb belgilandi.")


@router.patch("/me/read-all", summary="Mark all my notifications as read")
def mark_all_read(
    service: NotificationService = Depends(get_notification_service),
    user: User = Depends(get_current_user),
):
    count = service.mark_all_read(user.id)
    return success_response({"marked_count": count}, "Barchasi o'qilgan deb belgilandi.")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create an in-app notification for a user",
    description="Direct write to `notifications` — no queue, no delivery step needed for in-app.",
)
def create_notification(
    data: CreateNotificationRequest,
    service: NotificationService = Depends(get_notification_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    notification = service.create(data.user_id, data.title, data.message, data.channel, actor_id=admin.id)
    return success_response(NotificationOut.model_validate(notification), "Bildirishnoma yaratildi.")


@router.get("/templates", summary="List active notification templates")
def list_templates(
    service: TemplateService = Depends(get_template_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    templates = service.list_active()
    return success_response([TemplateOut.model_validate(t) for t in templates], "Shablonlar.")


@router.post("/templates", status_code=status.HTTP_201_CREATED, summary="Create a notification template")
def create_template(
    data: TemplateCreateRequest,
    service: TemplateService = Depends(get_template_service),
    admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    template = service.create(data.code, data.channel, data.subject, data.body, actor_id=admin.id)
    return success_response(TemplateOut.model_validate(template), "Shablon yaratildi.")


@router.post(
    "/queue/email",
    status_code=status.HTTP_201_CREATED,
    summary="Enqueue an email",
    description="Always succeeds instantly (status='pending') — actual delivery happens via a "
                "separate POST /queue/process/email call, not automatically.",
)
def enqueue_email(
    data: EnqueueEmailRequest,
    service: QueueService = Depends(get_queue_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    item = service.enqueue_email(data.to_email, data.subject, data.body)
    return success_response(QueueItemOut.model_validate(item), "Email navbatga qo'shildi.")


@router.post(
    "/queue/sms",
    status_code=status.HTTP_201_CREATED,
    summary="Enqueue an SMS",
    description="Always succeeds instantly (status='pending') — actual delivery happens via a "
                "separate POST /queue/process/sms call, not automatically.",
)
def enqueue_sms(
    data: EnqueueSmsRequest,
    service: QueueService = Depends(get_queue_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    item = service.enqueue_sms(data.to_phone, data.message)
    return success_response(QueueItemOut.model_validate(item), "SMS navbatga qo'shildi.")


@router.post(
    "/queue/process/email",
    summary="Process the pending email queue (delivery engine trigger)",
    description="501 Not Implemented — no real SMTP provider is configured this sprint "
                "(approved scope boundary: queue/trigger architecture and provider interfaces only).",
)
def process_email_queue(
    data: ProcessQueueRequest = ProcessQueueRequest(),
    service: QueueService = Depends(get_queue_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    result: ProcessQueueResponse = service.process_email_queue(data.batch_size)
    return success_response(result, "Email navbati qayta ishlandi.")


@router.post(
    "/queue/process/sms",
    summary="Process the pending SMS queue (delivery engine trigger)",
    description="501 Not Implemented — no real SMS provider is configured this sprint "
                "(approved scope boundary: queue/trigger architecture and provider interfaces only).",
)
def process_sms_queue(
    data: ProcessQueueRequest = ProcessQueueRequest(),
    service: QueueService = Depends(get_queue_service),
    _admin: User = Depends(require_roles("Admin", "Super Admin")),
):
    result: ProcessQueueResponse = service.process_sms_queue(data.batch_size)
    return success_response(result, "SMS navbati qayta ishlandi.")
