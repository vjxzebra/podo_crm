import logging
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.booking_requests.models import (
    TelegramDeliveryStatus,
    TelegramSubscription,
)
from apps.booking_requests.telegram_transport import TelegramBotClient, TelegramTransportError
from apps.notifications.models import (
    Notification,
    NotificationKind,
    NotificationTelegramDelivery,
)

logger = logging.getLogger("podoria")


class TelegramSendClient(Protocol):
    def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> Any:
        pass


def _safe_relative_deep_link(value: str) -> str:
    candidate = value.strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
        or len(candidate) > 500
    ):
        return "/"
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return "/"
    return candidate


def _safe_crm_url(deep_link: str) -> str:
    configured = str(settings.CRM_PUBLIC_URL).strip()
    parsed = urlsplit(configured)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return ""
    base_path = parsed.path.rstrip("/")
    base_url = urlunsplit((parsed.scheme, parsed.netloc, base_path, "", ""))
    return f"{base_url}{_safe_relative_deep_link(deep_link)}"


def notification_telegram_text(notification: Notification) -> str:
    occurred_at = timezone.localtime(notification.occurred_at).strftime("%d.%m.%Y, %H:%M")
    lines = [
        f"🔔 {notification.title}",
        notification.message,
        f"Час: {occurred_at}",
    ]
    crm_url = _safe_crm_url(notification.deep_link)
    if crm_url:
        lines.append(f"Відкрити в CRM: {crm_url}")
    return "\n".join(lines)


def notification_reply_markup(notification: Notification) -> dict[str, Any] | None:
    crm_url = _safe_crm_url(notification.deep_link)
    if not crm_url:
        return None
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Відкрити в CRM",
                    "url": crm_url,
                }
            ]
        ]
    }


def enqueue_notification_telegram_delivery(notification_id: UUID) -> bool:
    notification = (
        Notification.objects.select_related("recipient").filter(pk=notification_id).first()
    )
    if (
        notification is None
        or notification.kind == NotificationKind.WORK_ITEM_OVERDUE
        or not notification.recipient.is_active
    ):
        return False
    subscription = (
        TelegramSubscription.objects.select_related("user")
        .filter(
            user_id=notification.recipient_id,
            is_enabled=True,
            user__is_active=True,
        )
        .first()
    )
    if subscription is None:
        return False
    _, created = NotificationTelegramDelivery.objects.get_or_create(
        notification=notification,
        subscription=subscription,
        defaults={"chat_id": subscription.chat_id},
    )
    return created


def enqueue_notification_telegram_delivery_on_commit(notification: Notification) -> None:
    notification_id = notification.pk
    try:
        with transaction.atomic():
            created = enqueue_notification_telegram_delivery(notification_id)
    except Exception:
        logger.exception(
            "notification_telegram_delivery_create_failed",
            extra={"notification_id": str(notification_id)},
        )
        return
    if not created:
        return

    def dispatch_safely() -> None:
        try:
            from apps.notifications.tasks import dispatch_notification_telegram_deliveries

            dispatch_notification_telegram_deliveries.delay()
        except Exception:
            logger.exception(
                "notification_telegram_dispatch_enqueue_failed",
                extra={"notification_id": str(notification_id)},
            )

    transaction.on_commit(dispatch_safely)


def _sanitize_error_message(value: str) -> str:
    token = str(settings.TELEGRAM_BOT_TOKEN)
    sanitized = value.replace(token, "[redacted]") if token else value
    return sanitized[:255]


def _next_attempt(
    error: TelegramTransportError,
    attempt_count: int,
    *,
    now: datetime,
) -> datetime:
    if error.retry_after is not None:
        return now + timedelta(seconds=max(1, error.retry_after))
    delay = min(
        settings.TELEGRAM_DELIVERY_RETRY_MAX_SECONDS,
        settings.TELEGRAM_DELIVERY_RETRY_BASE_SECONDS * (2 ** max(0, attempt_count - 1)),
    )
    return now + timedelta(seconds=delay)


def _mark_transport_failure(
    delivery: NotificationTelegramDelivery,
    subscription: TelegramSubscription,
    error: TelegramTransportError,
    *,
    now: datetime,
) -> None:
    delivery.attempt_count += 1
    delivery.error_code = error.code[:64]
    delivery.error_message = _sanitize_error_message(str(error))
    if (
        error.status_code in (400, 403)
        or delivery.attempt_count >= settings.TELEGRAM_DELIVERY_MAX_ATTEMPTS
    ):
        delivery.status = TelegramDeliveryStatus.PERMANENT_FAILURE
        delivery.next_attempt_at = None
        if error.status_code == 403:
            subscription.is_enabled = False
            subscription.disabled_at = now
            subscription.save(update_fields=("is_enabled", "disabled_at", "updated_at"))
    else:
        delivery.status = TelegramDeliveryStatus.RETRY
        delivery.next_attempt_at = _next_attempt(error, delivery.attempt_count, now=now)
    delivery.save(
        update_fields=(
            "status",
            "attempt_count",
            "next_attempt_at",
            "error_code",
            "error_message",
            "updated_at",
        )
    )


def _mark_permanent_failure(
    delivery: NotificationTelegramDelivery,
    *,
    code: str,
    message: str,
) -> None:
    delivery.status = TelegramDeliveryStatus.PERMANENT_FAILURE
    delivery.next_attempt_at = None
    delivery.error_code = code
    delivery.error_message = message
    delivery.save(
        update_fields=(
            "status",
            "next_attempt_at",
            "error_code",
            "error_message",
            "updated_at",
        )
    )


def dispatch_due_notification_telegram_deliveries(
    *,
    now: datetime | None = None,
    client: TelegramSendClient | None = None,
    limit: int = 50,
) -> int:
    current_time = now or timezone.now()
    bot: TelegramSendClient = client or TelegramBotClient()
    dispatched = 0
    for _ in range(limit):
        with transaction.atomic():
            delivery = (
                NotificationTelegramDelivery.objects.select_related(
                    "notification",
                    "notification__recipient",
                    "subscription",
                    "subscription__user",
                )
                .select_for_update(of=("self",), skip_locked=True)
                .filter(
                    Q(status=TelegramDeliveryStatus.PENDING)
                    | Q(status=TelegramDeliveryStatus.RETRY, next_attempt_at__lte=current_time)
                )
                .order_by("created_at", "id")
                .first()
            )
            if delivery is None:
                break
            notification = delivery.notification
            subscription = delivery.subscription
            if notification.kind == NotificationKind.WORK_ITEM_OVERDUE:
                _mark_permanent_failure(
                    delivery,
                    code="work_item_delivery_owned",
                    message="Work item Telegram delivery owns this notification kind.",
                )
                continue
            if (
                notification.recipient_id != subscription.user_id
                or not notification.recipient.is_active
                or not subscription.user.is_active
                or not subscription.is_enabled
                or delivery.chat_id != subscription.chat_id
            ):
                _mark_permanent_failure(
                    delivery,
                    code="ineligible_subscription",
                    message="Subscription is not eligible for this notification.",
                )
                continue
            try:
                result = bot.send_message(
                    chat_id=delivery.chat_id,
                    text=notification_telegram_text(notification),
                    reply_markup=notification_reply_markup(notification),
                )
            except TelegramTransportError as exc:
                _mark_transport_failure(
                    delivery,
                    subscription,
                    exc,
                    now=current_time,
                )
                continue
            delivery.status = TelegramDeliveryStatus.SENT
            delivery.message_id = result.message_id
            delivery.attempt_count += 1
            delivery.next_attempt_at = None
            delivery.error_code = ""
            delivery.error_message = ""
            delivery.save(
                update_fields=(
                    "status",
                    "message_id",
                    "attempt_count",
                    "next_attempt_at",
                    "error_code",
                    "error_message",
                    "updated_at",
                )
            )
            dispatched += 1
    return dispatched
