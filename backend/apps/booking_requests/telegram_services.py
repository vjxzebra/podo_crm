import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.db.models.query import QuerySet
from django.utils import timezone
from rest_framework import status

from apps.accounts.access import AccessScope, has_scope
from apps.accounts.models import User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.booking_requests.models import (
    BookingRequest,
    BookingRequestStatus,
    TelegramDelivery,
    TelegramDeliveryStatus,
    TelegramLinkIntent,
    TelegramSubscription,
    TelegramUpdate,
    TelegramUpdateState,
    TelegramUpdateType,
)
from apps.booking_requests.telegram_transport import TelegramBotClient, TelegramTransportError
from config.api.exceptions import ApiProblem

logger = logging.getLogger("podoria")

TELEGRAM_SAFE_ERROR = "Не вдалося підключити Telegram. Створіть нове посилання у CRM."
MAX_WEBHOOK_BYTES = 64 * 1024


class TelegramSendClient(Protocol):
    def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> Any:
        pass

    def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> Any:
        pass

    def answer_callback_query(self, *, callback_query_id: str, text: str = "") -> Any:
        pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_payload() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def _bot_username() -> str:
    return str(settings.TELEGRAM_BOT_USERNAME).strip().lstrip("@")


def _crm_public_url() -> str:
    return str(settings.CRM_PUBLIC_URL).rstrip("/")


def _subscription_snapshot(subscription: TelegramSubscription) -> dict[str, Any]:
    return {
        "is_enabled": subscription.is_enabled,
        "username": bool(subscription.username),
        "first_name": bool(subscription.first_name),
        "linked_at": subscription.linked_at,
        "disabled_at": subscription.disabled_at,
        "last_seen_at": subscription.last_seen_at,
    }


def ensure_telegram_access(user: User) -> None:
    if not has_scope(user, AccessScope.BOOKING_REQUESTS):
        raise ApiProblem(
            code="permission_denied",
            message="Недостатньо прав для цієї дії.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def get_telegram_subscription_for(user: User) -> TelegramSubscription | None:
    ensure_telegram_access(user)
    return TelegramSubscription.objects.filter(user=user).first()


@transaction.atomic
def create_telegram_link_intent(*, actor: User) -> tuple[str, TelegramLinkIntent]:
    ensure_telegram_access(actor)
    payload = _new_payload()
    intent = TelegramLinkIntent.objects.create(
        user=actor,
        payload_digest=_digest(payload),
        expires_at=timezone.now() + timedelta(seconds=settings.TELEGRAM_LINK_INTENT_TTL_SECONDS),
    )
    return payload, intent


@transaction.atomic
def disconnect_telegram_subscription(
    *, actor: User, correlation_id: str
) -> TelegramSubscription | None:
    ensure_telegram_access(actor)
    subscription = TelegramSubscription.objects.select_for_update().filter(user=actor).first()
    if subscription is None:
        return None
    if subscription.is_enabled:
        before = _subscription_snapshot(subscription)
        subscription.is_enabled = False
        subscription.disabled_at = timezone.now()
        subscription.save(update_fields=("is_enabled", "disabled_at", "updated_at"))
        record_audit_event(
            actor=actor,
            action=AuditAction.TELEGRAM_SUBSCRIPTION_UNLINKED,
            object_type="telegram_subscription",
            object_id=actor.pk,
            object_label=actor.display_name,
            correlation_id=correlation_id,
            before=before,
            after=_subscription_snapshot(subscription),
            description="Працівник відключив Telegram-сповіщення.",
        )
    return subscription


def eligible_telegram_subscriptions() -> QuerySet[TelegramSubscription]:
    return (
        TelegramSubscription.objects.select_related("user")
        .filter(is_enabled=True, user__is_active=True, user__role__in=("admin", "reception"))
        .order_by("user_id")
    )


def enqueue_booking_request_delivery_rows(item: BookingRequest) -> int:
    created = 0
    for subscription in eligible_telegram_subscriptions().iterator():
        _, was_created = TelegramDelivery.objects.get_or_create(
            booking_request=item,
            subscription=subscription,
            defaults={"chat_id": subscription.chat_id},
        )
        created += int(was_created)
    return created


def enqueue_booking_request_telegram_delivery_on_commit(item: BookingRequest) -> None:
    enqueue_booking_request_delivery_rows(item)
    dispatch_telegram_delivery_on_commit(item)


def dispatch_telegram_delivery_on_commit(item: BookingRequest) -> None:

    def dispatch_safely() -> None:
        try:
            from apps.booking_requests.tasks import dispatch_telegram_booking_request_deliveries

            dispatch_telegram_booking_request_deliveries.delay()
        except Exception:
            logger.exception(
                "telegram_delivery_enqueue_failed",
                extra={"booking_request": item.public_number},
            )

    transaction.on_commit(dispatch_safely)


def booking_request_telegram_text(item: BookingRequest) -> str:
    preferred = "Не вказано"
    if item.preferred_at is not None:
        preferred = timezone.localtime(item.preferred_at).strftime("%d.%m.%Y, %H:%M")
    created = timezone.localtime(item.created_at).strftime("%d.%m.%Y, %H:%M")
    status_label = "✅ Оброблено" if item.status == BookingRequestStatus.PROCESSED else "Нова"
    lines = [
        f"Заявка {item.public_number}",
        f"Статус: {status_label}",
        f"Джерело: {item.get_source_display()}",
        f"Ім'я: {item.client_name or 'Не вказано'}",
        f"Телефон: {item.phone or 'Не вказано'}",
        f"Послуга: {item.service or 'Не вказано'}",
        f"Контакт: {item.contact_handle or 'Не вказано'}",
        f"Бажаний час: {preferred}",
        f"Коментар: {item.message or 'Не вказано'}",
        f"Створено: {created}",
    ]
    if item.status == BookingRequestStatus.PROCESSED:
        processed_at = "Не вказано"
        if item.processed_at is not None:
            processed_at = timezone.localtime(item.processed_at).strftime("%d.%m.%Y, %H:%M")
        lines.extend(
            [
                f"Обробив: {item.processed_by_display_name or 'Не вказано'}",
                f"Оброблено: {processed_at}",
            ]
        )
    return "\n".join(lines)


def booking_request_reply_markup(item: BookingRequest) -> dict[str, Any]:
    keyboard = []
    if item.status != BookingRequestStatus.PROCESSED:
        keyboard.append([{"text": "✅ Оброблено", "callback_data": f"br:p:{item.pk}"}])
    keyboard.append(
        [
            {
                "text": "Відкрити в CRM",
                "url": f"{_crm_public_url()}/booking-requests?request={item.pk}",
            }
        ]
    )
    return {
        "inline_keyboard": keyboard,
    }


def _sanitize_error_message(value: str) -> str:
    return value.replace(str(settings.TELEGRAM_BOT_TOKEN), "[redacted]")[:255]


def _next_attempt(error: TelegramTransportError, attempt_count: int) -> datetime:
    if error.retry_after is not None:
        return timezone.now() + timedelta(seconds=max(1, error.retry_after))
    delay = min(
        settings.TELEGRAM_DELIVERY_RETRY_MAX_SECONDS,
        settings.TELEGRAM_DELIVERY_RETRY_BASE_SECONDS * (2 ** max(0, attempt_count - 1)),
    )
    return timezone.now() + timedelta(seconds=delay)


def _mark_delivery_transport_failure(
    delivery: TelegramDelivery,
    subscription: TelegramSubscription,
    error: TelegramTransportError,
) -> None:
    delivery.attempt_count += 1
    delivery.error_code = error.code[:64]
    delivery.error_message = _sanitize_error_message(str(error))
    if (
        error.status_code in (400, 403)
        or delivery.attempt_count >= settings.TELEGRAM_DELIVERY_MAX_ATTEMPTS
    ):
        delivery.status = TelegramDeliveryStatus.PERMANENT_FAILURE
        if error.status_code == 403:
            subscription.is_enabled = False
            subscription.disabled_at = timezone.now()
            subscription.save(update_fields=("is_enabled", "disabled_at", "updated_at"))
    else:
        delivery.status = TelegramDeliveryStatus.RETRY
        delivery.next_attempt_at = _next_attempt(error, delivery.attempt_count)
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


def dispatch_due_telegram_deliveries(
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
                TelegramDelivery.objects.select_related(
                    "booking_request",
                    "subscription",
                    "subscription__user",
                )
                .select_for_update(skip_locked=True)
                .filter(
                    Q(status=TelegramDeliveryStatus.PENDING)
                    | Q(status=TelegramDeliveryStatus.RETRY, next_attempt_at__lte=current_time)
                    | Q(
                        status=TelegramDeliveryStatus.SENT,
                        message_id__isnull=False,
                        booking_request__status=BookingRequestStatus.PROCESSED,
                        last_synced_request_version__lt=F("booking_request__version"),
                    )
                )
                .order_by("created_at")
                .first()
            )
            if delivery is None:
                break
            subscription = delivery.subscription
            if (
                not subscription.is_enabled
                or not subscription.user.is_active
                or not has_scope(subscription.user, AccessScope.BOOKING_REQUESTS)
            ):
                delivery.status = TelegramDeliveryStatus.PERMANENT_FAILURE
                delivery.error_code = "ineligible_subscription"
                delivery.error_message = "Subscription is not eligible."
                delivery.save(update_fields=("status", "error_code", "error_message", "updated_at"))
                continue
            try:
                message_id = delivery.message_id
                if (
                    message_id is not None
                    and delivery.booking_request.status == BookingRequestStatus.PROCESSED
                    and delivery.last_synced_request_version < delivery.booking_request.version
                ):
                    bot.edit_message_text(
                        chat_id=delivery.chat_id,
                        message_id=message_id,
                        text=booking_request_telegram_text(delivery.booking_request),
                        reply_markup=booking_request_reply_markup(delivery.booking_request),
                    )
                    delivery.status = TelegramDeliveryStatus.SENT
                    delivery.attempt_count += 1
                    delivery.next_attempt_at = None
                    delivery.error_code = ""
                    delivery.error_message = ""
                    delivery.last_synced_request_version = delivery.booking_request.version
                    delivery.save(
                        update_fields=(
                            "status",
                            "attempt_count",
                            "next_attempt_at",
                            "error_code",
                            "error_message",
                            "last_synced_request_version",
                            "updated_at",
                        )
                    )
                    dispatched += 1
                    continue
                result = bot.send_message(
                    chat_id=delivery.chat_id,
                    text=booking_request_telegram_text(delivery.booking_request),
                    reply_markup=booking_request_reply_markup(delivery.booking_request),
                )
            except TelegramTransportError as exc:
                _mark_delivery_transport_failure(delivery, subscription, exc)
                continue
            delivery.status = TelegramDeliveryStatus.SENT
            delivery.message_id = result.message_id
            delivery.attempt_count += 1
            delivery.next_attempt_at = None
            delivery.error_code = ""
            delivery.error_message = ""
            delivery.last_synced_request_version = delivery.booking_request.version
            delivery.save(
                update_fields=(
                    "status",
                    "message_id",
                    "attempt_count",
                    "next_attempt_at",
                    "error_code",
                    "error_message",
                    "last_synced_request_version",
                    "updated_at",
                )
            )
            dispatched += 1
    return dispatched


def normalize_telegram_update(update: dict[str, Any]) -> dict[str, Any]:
    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        raise ValueError("update_id is required.")
    message = update.get("message")
    if isinstance(message, dict):
        chat_value = message.get("chat")
        chat: dict[str, Any] = chat_value if isinstance(chat_value, dict) else {}
        sender_value = message.get("from")
        sender: dict[str, Any] = sender_value if isinstance(sender_value, dict) else {}
        text_value = message.get("text")
        text = text_value if isinstance(text_value, str) else ""
        command = text.split(maxsplit=1)[0] if text.startswith("/") else ""
        message_id = message.get("message_id")
        return {
            "update_id": update_id,
            "update_type": TelegramUpdateType.MESSAGE,
            "telegram_user_id": sender.get("id") if isinstance(sender.get("id"), int) else None,
            "chat_id": chat.get("id") if isinstance(chat.get("id"), int) else None,
            "chat_type": str(chat.get("type") or "")[:16],
            "message_id": message_id if isinstance(message_id, int) else None,
            "command": command[:32],
        }
    callback = update.get("callback_query")
    if isinstance(callback, dict):
        sender_value = callback.get("from")
        sender = sender_value if isinstance(sender_value, dict) else {}
        message_value = callback.get("message")
        message = message_value if isinstance(message_value, dict) else {}
        chat_value = message.get("chat")
        chat = chat_value if isinstance(chat_value, dict) else {}
        data_value = callback.get("data")
        callback_id = callback.get("id")
        message_id = message.get("message_id")
        return {
            "update_id": update_id,
            "update_type": TelegramUpdateType.CALLBACK_QUERY,
            "telegram_user_id": sender.get("id") if isinstance(sender.get("id"), int) else None,
            "chat_id": chat.get("id") if isinstance(chat.get("id"), int) else None,
            "chat_type": str(chat.get("type") or "")[:16],
            "message_id": message_id if isinstance(message_id, int) else None,
            "command": "",
            "callback_query_id": str(callback_id or "")[:128],
            "callback_data": data_value[:64] if isinstance(data_value, str) else "",
        }
    return {
        "update_id": update_id,
        "update_type": TelegramUpdateType.UNKNOWN,
        "telegram_user_id": None,
        "chat_id": None,
        "chat_type": "",
        "message_id": None,
        "command": "",
    }


@transaction.atomic
def store_telegram_update(update: dict[str, Any]) -> tuple[TelegramUpdate, bool]:
    normalized = normalize_telegram_update(update)
    item, created = TelegramUpdate.objects.get_or_create(
        update_id=normalized["update_id"],
        defaults=normalized,
    )
    return item, created


def process_telegram_update(update_id: int, *, client: TelegramBotClient | None = None) -> str:
    update = TelegramUpdate.objects.filter(update_id=update_id).first()
    if update is None or update.state != TelegramUpdateState.RECEIVED:
        return "skipped"
    if update.update_type == TelegramUpdateType.CALLBACK_QUERY:
        return _process_callback_update(update, client=client)
    if update.update_type != TelegramUpdateType.MESSAGE or update.command not in (
        "/start",
        "/stop",
    ):
        update.state = TelegramUpdateState.IGNORED
        update.processed_at = timezone.now()
        update.save(update_fields=("state", "processed_at", "updated_at"))
        return "ignored"
    if update.command == "/stop":
        return _process_stop_update(update)
    return _process_start_update(update, client=client)


def _send_safe_message(client: TelegramSendClient | None, chat_id: int | None, text: str) -> None:
    if chat_id is None:
        return
    try:
        (client or TelegramBotClient()).send_message(chat_id=chat_id, text=text)
    except TelegramTransportError:
        logger.info("telegram_safe_message_failed", extra={"chat_id_present": True})


def _answer_callback_safely(
    client: TelegramSendClient | None,
    callback_query_id: str,
    text: str,
) -> None:
    if not callback_query_id:
        return
    try:
        (client or TelegramBotClient()).answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
        )
    except TelegramTransportError:
        logger.info("telegram_callback_answer_failed", extra={"callback_id_present": True})


def _mark_update(update: TelegramUpdate, state: str, *, code: str = "", message: str = "") -> None:
    update.state = state
    update.error_code = code[:64]
    update.error_message = message[:255]
    update.processed_at = timezone.now()
    update.save(
        update_fields=(
            "state",
            "error_code",
            "error_message",
            "processed_at",
            "updated_at",
        )
    )


def _booking_request_id_from_callback(data: str) -> UUID | None:
    prefix = "br:p:"
    if not data.startswith(prefix):
        return None
    try:
        return UUID(data.removeprefix(prefix))
    except ValueError:
        return None


@transaction.atomic
def _process_callback_update(
    update: TelegramUpdate,
    *,
    client: TelegramSendClient | None = None,
) -> str:
    update = TelegramUpdate.objects.select_for_update().get(update_id=update.update_id)
    if update.state != TelegramUpdateState.RECEIVED:
        return "skipped"
    safe_denied = "Не вдалося виконати дію."
    booking_request_id = _booking_request_id_from_callback(update.callback_data)
    if (
        booking_request_id is None
        or update.chat_type != "private"
        or update.chat_id is None
        or update.telegram_user_id is None
    ):
        _answer_callback_safely(client, update.callback_query_id, safe_denied)
        _mark_update(update, TelegramUpdateState.IGNORED, code="invalid_callback")
        return "ignored"
    subscription = (
        TelegramSubscription.objects.select_for_update()
        .select_related("user")
        .filter(
            chat_id=update.chat_id,
            telegram_user_id=update.telegram_user_id,
            is_enabled=True,
        )
        .first()
    )
    if (
        subscription is None
        or not subscription.user.is_active
        or not has_scope(subscription.user, AccessScope.BOOKING_REQUESTS)
    ):
        _answer_callback_safely(client, update.callback_query_id, safe_denied)
        _mark_update(update, TelegramUpdateState.IGNORED, code="unauthorized_callback")
        return "unauthorized"
    item = (
        BookingRequest.objects.filter(pk=booking_request_id).only("id", "status", "version").first()
    )
    if item is None:
        _answer_callback_safely(client, update.callback_query_id, safe_denied)
        _mark_update(update, TelegramUpdateState.IGNORED, code="unknown_callback_target")
        return "not_found"
    was_processed = item.status == BookingRequestStatus.PROCESSED
    try:
        from apps.booking_requests.services import process_booking_request

        process_booking_request(
            actor=subscription.user,
            booking_request_id=booking_request_id,
            requested_version=item.version,
            correlation_id=f"telegram-update-{update.update_id}",
        )
    except ApiProblem:
        _answer_callback_safely(client, update.callback_query_id, safe_denied)
        _mark_update(update, TelegramUpdateState.IGNORED, code="callback_process_failed")
        return "failed"
    subscription.last_seen_at = timezone.now()
    subscription.save(update_fields=("last_seen_at", "updated_at"))
    _mark_update(update, TelegramUpdateState.PROCESSED)
    _answer_callback_safely(
        client,
        update.callback_query_id,
        "Заявку вже оброблено." if was_processed else "Заявку оброблено.",
    )
    return "already_processed" if was_processed else "processed"


@transaction.atomic
def _process_stop_update(update: TelegramUpdate) -> str:
    if update.chat_id is None:
        return "stopped"
    subscription = (
        TelegramSubscription.objects.select_for_update().filter(chat_id=update.chat_id).first()
    )
    if subscription is not None and subscription.is_enabled:
        subscription.is_enabled = False
        subscription.disabled_at = timezone.now()
        subscription.last_seen_at = timezone.now()
        subscription.save(update_fields=("is_enabled", "disabled_at", "last_seen_at", "updated_at"))
    update.state = TelegramUpdateState.PROCESSED
    update.processed_at = timezone.now()
    update.save(update_fields=("state", "processed_at", "updated_at"))
    return "stopped"


def _start_payload_from_update(update: TelegramUpdate) -> str:
    # The raw payload is intentionally not persisted; the webhook reads it only in memory.
    return ""


def process_start_payload_update(
    *,
    update: dict[str, Any],
    client: TelegramSendClient | None = None,
) -> str:
    message_value = update.get("message")
    message = message_value if isinstance(message_value, dict) else {}
    text_value = message.get("text")
    text = text_value if isinstance(text_value, str) else ""
    parts = text.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else ""
    stored, created = store_telegram_update(update)
    if not created:
        return "duplicate"
    return _process_start_update(stored, payload=payload, original_update=update, client=client)


@transaction.atomic
def _process_start_update(
    update: TelegramUpdate,
    *,
    payload: str | None = None,
    original_update: dict[str, Any] | None = None,
    client: TelegramSendClient | None = None,
) -> str:
    message: dict[str, Any] = {}
    if isinstance(original_update, dict):
        message_value = original_update.get("message")
        if isinstance(message_value, dict):
            message = message_value
    chat_value = message.get("chat")
    chat: dict[str, Any] = chat_value if isinstance(chat_value, dict) else {}
    sender_value = message.get("from")
    sender: dict[str, Any] = sender_value if isinstance(sender_value, dict) else {}
    if chat.get("type") != "private" or update.chat_id is None or update.telegram_user_id is None:
        update.state = TelegramUpdateState.IGNORED
        update.processed_at = timezone.now()
        update.save(update_fields=("state", "processed_at", "updated_at"))
        _send_safe_message(client, update.chat_id, "Підключення доступне лише у приватному чаті.")
        return "not_private"
    raw_payload = payload if payload is not None else _start_payload_from_update(update)
    if not raw_payload:
        update.state = TelegramUpdateState.IGNORED
        update.processed_at = timezone.now()
        update.save(update_fields=("state", "processed_at", "updated_at"))
        _send_safe_message(client, update.chat_id, "Почніть підключення з авторизованої CRM.")
        return "missing_payload"
    intent = (
        TelegramLinkIntent.objects.select_for_update()
        .select_related("user")
        .filter(payload_digest=_digest(raw_payload))
        .first()
    )
    now = timezone.now()
    if intent is None or intent.used_at is not None or intent.expires_at <= now:
        update.state = TelegramUpdateState.IGNORED
        update.processed_at = now
        update.save(update_fields=("state", "processed_at", "updated_at"))
        _send_safe_message(client, update.chat_id, TELEGRAM_SAFE_ERROR)
        return "expired"
    if not has_scope(intent.user, AccessScope.BOOKING_REQUESTS):
        update.state = TelegramUpdateState.IGNORED
        update.processed_at = now
        update.save(update_fields=("state", "processed_at", "updated_at"))
        _send_safe_message(client, update.chat_id, TELEGRAM_SAFE_ERROR)
        return "ineligible"
    if (
        TelegramSubscription.objects.exclude(user=intent.user)
        .filter(Q(telegram_user_id=update.telegram_user_id) | Q(chat_id=update.chat_id))
        .exists()
    ):
        update.state = TelegramUpdateState.IGNORED
        update.processed_at = now
        update.save(update_fields=("state", "processed_at", "updated_at"))
        _send_safe_message(
            client, update.chat_id, "Цей Telegram уже підключено до іншого працівника."
        )
        return "identity_taken"
    defaults = {
        "telegram_user_id": update.telegram_user_id,
        "chat_id": update.chat_id,
        "username": str(sender.get("username") or "")[:100],
        "first_name": str(sender.get("first_name") or "")[:160],
        "is_enabled": True,
        "linked_at": now,
        "disabled_at": None,
        "last_seen_at": now,
    }
    try:
        subscription, created = TelegramSubscription.objects.update_or_create(
            user=intent.user,
            defaults=defaults,
        )
    except IntegrityError:
        update.state = TelegramUpdateState.IGNORED
        update.processed_at = now
        update.save(update_fields=("state", "processed_at", "updated_at"))
        _send_safe_message(
            client, update.chat_id, "Цей Telegram уже підключено до іншого працівника."
        )
        return "identity_taken"
    intent.used_at = now
    intent.save(update_fields=("used_at",))
    update.state = TelegramUpdateState.PROCESSED
    update.processed_at = now
    update.save(update_fields=("state", "processed_at", "updated_at"))
    if created:
        record_audit_event(
            actor=intent.user,
            action=AuditAction.TELEGRAM_SUBSCRIPTION_LINKED,
            object_type="telegram_subscription",
            object_id=intent.user.pk,
            object_label=intent.user.display_name,
            correlation_id=f"telegram-update-{update.update_id}",
            after=_subscription_snapshot(subscription),
            description="Працівник підключив Telegram-сповіщення.",
        )
    _send_safe_message(
        client,
        update.chat_id,
        "Telegram підключено. Нові заявки надходитимуть у цей приватний чат.",
    )
    return "linked"
