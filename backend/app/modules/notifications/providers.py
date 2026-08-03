"""
EmailProvider / SmsProvider interfaces — infrastructure used by
NotificationService, same relationship StorageBackend has to
UploadService (Sprint 8, uploads module). NOT a new architectural layer.

Per the approved Sprint 8 scope: NO real SMTP or SMS provider ships this
sprint. `UnconfiguredEmailProvider`/`UnconfiguredSmsProvider` are the
only implementations — they do not pretend to send anything. Calling
`.send()` raises `ProviderNotConfiguredException` honestly, so a queued
row stays 'pending' (never silently marked 'sent' for a message that was
never actually delivered). A future sprint adds a real implementation
(e.g. SmtplibEmailProvider, EskizSmsProvider) and wires it in via the
same `get_email_provider()`/`get_sms_provider()` dependency functions —
zero change to NotificationService.
"""
from abc import ABC, abstractmethod

from app.modules.notifications.exceptions import ProviderNotConfiguredException


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to_email: str, subject: str, body: str) -> None:
        """Raises on any failure (including 'not configured'). Returns
        normally (no return value) only on confirmed successful send."""
        ...


class SmsProvider(ABC):
    @abstractmethod
    def send(self, to_phone: str, message: str) -> None:
        ...


class UnconfiguredEmailProvider(EmailProvider):
    """The only EmailProvider implementation this sprint. Honest, not
    fake: real SMTP integration is explicitly deferred (see module docstring)."""

    def send(self, to_email: str, subject: str, body: str) -> None:
        raise ProviderNotConfiguredException(
            "Email provayder ulanmagan — haqiqiy SMTP integratsiyasi keyingi sprintga qoldirilgan"
        )


class UnconfiguredSmsProvider(SmsProvider):
    """The only SmsProvider implementation this sprint."""

    def send(self, to_phone: str, message: str) -> None:
        raise ProviderNotConfiguredException(
            "SMS provayder ulanmagan — haqiqiy SMS integratsiyasi keyingi sprintga qoldirilgan"
        )
