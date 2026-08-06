from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.booking_requests.models import (
    TelegramDeliveryStatus,
    TelegramSubscription,
    WorkItemTelegramDelivery,
)
from apps.booking_requests.telegram_transport import TelegramMessageResult, TelegramTransportError
from apps.notifications.models import (
    Notification,
    NotificationKind,
    NotificationTelegramDelivery,
)
from apps.notifications.services import create_notification, dispatch_due_reminders
from apps.notifications.telegram_services import (
    dispatch_due_notification_telegram_deliveries,
    enqueue_notification_telegram_delivery,
    notification_reply_markup,
)
from apps.work_items.models import WorkItemKind
from apps.work_items.services import create_work_item

PASSWORD = "test-only-password-placeholder"  # noqa: S105


def create_user(
    *,
    email: str,
    role: str = UserRole.RECEPTION,
    is_active: bool = True,
) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="Тест",
        last_name="Telegram",
        is_active=is_active,
    )


def create_subscription(
    user: User,
    *,
    telegram_user_id: int,
    chat_id: int,
    is_enabled: bool = True,
) -> TelegramSubscription:
    now = timezone.now()
    return TelegramSubscription.objects.create(
        user=user,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        username=f"user{telegram_user_id}",
        first_name="Telegram",
        is_enabled=is_enabled,
        linked_at=now,
        disabled_at=None if is_enabled else now,
        last_seen_at=now,
    )


class FakeTelegramClient:
    def __init__(self, *, error: TelegramTransportError | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def send_message(self, **kwargs) -> TelegramMessageResult:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return TelegramMessageResult(message_id=9000 + len(self.calls))


def create_mirrored_notification(
    *,
    recipient: User,
    event_key: str,
    kind: str = NotificationKind.APPOINTMENT_ARRIVED,
    deep_link: str = "/calendar",
    django_capture_on_commit_callbacks,
) -> Notification:
    with (
        patch("apps.notifications.tasks.dispatch_notification_telegram_deliveries.delay"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        notification, created = create_notification(
            recipient=recipient,
            event_key=event_key,
            kind=kind,
            title="Персональне сповіщення",
            message="Подія стосується лише одержувача.",
            deep_link=deep_link,
            occurred_at=timezone.now().replace(microsecond=0),
        )
    assert created is True
    assert notification is not None
    return notification


@pytest.mark.django_db
@override_settings(CRM_PUBLIC_URL="https://crm.example.test")
def test_notification_is_mirrored_only_to_exact_recipient(
    django_capture_on_commit_callbacks,
) -> None:
    recipient = create_user(email="recipient@example.test")
    other = create_user(email="other@example.test", role=UserRole.ADMIN)
    recipient_subscription = create_subscription(
        recipient,
        telegram_user_id=101,
        chat_id=201,
    )
    create_subscription(other, telegram_user_id=102, chat_id=202)
    notification = create_mirrored_notification(
        recipient=recipient,
        event_key="recipient-only:event",
        deep_link="/calendar?appointment=123",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )

    assert NotificationTelegramDelivery.objects.count() == 1
    delivery = NotificationTelegramDelivery.objects.get()
    assert delivery.notification == notification
    assert delivery.subscription == recipient_subscription
    assert enqueue_notification_telegram_delivery(notification.pk) is False

    fake = FakeTelegramClient()
    assert dispatch_due_notification_telegram_deliveries(client=fake) == 1
    assert dispatch_due_notification_telegram_deliveries(client=fake) == 0

    delivery.refresh_from_db()
    notification.refresh_from_db()
    assert delivery.status == TelegramDeliveryStatus.SENT
    assert delivery.message_id == 9001
    assert delivery.attempt_count == 1
    assert fake.calls[0]["chat_id"] == 201
    assert "Персональне сповіщення" in fake.calls[0]["text"]
    assert "Подія стосується лише одержувача." in fake.calls[0]["text"]
    assert "Час:" in fake.calls[0]["text"]
    assert "https://crm.example.test/calendar?appointment=123" in fake.calls[0]["text"]
    assert fake.calls[0]["reply_markup"] == {
        "inline_keyboard": [
            [
                {
                    "text": "Відкрити в CRM",
                    "url": "https://crm.example.test/calendar?appointment=123",
                }
            ]
        ]
    }
    assert notification.read_at is None


@pytest.mark.django_db
def test_unlinked_disabled_and_work_item_notifications_are_not_enqueued(
    django_capture_on_commit_callbacks,
) -> None:
    unlinked = create_user(email="unlinked@example.test")
    disabled = create_user(email="disabled@example.test")
    work_item_recipient = create_user(email="work-item@example.test")
    create_subscription(
        disabled,
        telegram_user_id=301,
        chat_id=401,
        is_enabled=False,
    )
    create_subscription(work_item_recipient, telegram_user_id=302, chat_id=402)

    create_mirrored_notification(
        recipient=unlinked,
        event_key="unlinked:event",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )
    create_mirrored_notification(
        recipient=disabled,
        event_key="disabled:event",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )
    create_mirrored_notification(
        recipient=work_item_recipient,
        event_key="work-item:overdue:event",
        kind=NotificationKind.WORK_ITEM_OVERDUE,
        deep_link="/work-items?item=123",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )

    assert Notification.objects.count() == 3
    assert NotificationTelegramDelivery.objects.count() == 0


@pytest.mark.django_db
def test_overdue_work_item_keeps_its_existing_personal_delivery_without_duplicate(
    django_capture_on_commit_callbacks,
) -> None:
    actor = create_user(email="work-item-actor@example.test", role=UserRole.ADMIN)
    assignee = create_user(email="work-item-assignee@example.test")
    create_subscription(assignee, telegram_user_id=401, chat_id=501)
    now = timezone.now().replace(microsecond=0)
    item = create_work_item(
        actor=actor,
        correlation_id="notification-telegram-no-work-item-duplicate",
        data={
            "kind": WorkItemKind.OTHER,
            "title": "Прострочена персональна справа",
            "due_at": now - timedelta(minutes=1),
            "assignee_id": assignee.pk,
            "comment": "",
            "is_important": True,
        },
    )

    assert WorkItemTelegramDelivery.objects.filter(work_item=item).count() == 1
    with (
        patch("apps.notifications.tasks.dispatch_notification_telegram_deliveries.delay"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert dispatch_due_reminders(now=now) == 1

    assert (
        Notification.objects.filter(
            recipient=assignee,
            kind=NotificationKind.WORK_ITEM_OVERDUE,
        ).count()
        == 1
    )
    assert NotificationTelegramDelivery.objects.count() == 0
    assert WorkItemTelegramDelivery.objects.filter(work_item=item).count() == 1


@pytest.mark.django_db
@override_settings(
    TELEGRAM_BOT_TOKEN="unit-test-token-placeholder",  # noqa: S106
    TELEGRAM_DELIVERY_RETRY_BASE_SECONDS=60,
    TELEGRAM_DELIVERY_RETRY_MAX_SECONDS=3600,
    TELEGRAM_DELIVERY_MAX_ATTEMPTS=3,
)
def test_transient_failure_retries_with_sanitized_error_then_sends(
    django_capture_on_commit_callbacks,
) -> None:
    recipient = create_user(email="retry@example.test")
    create_subscription(recipient, telegram_user_id=501, chat_id=601)
    notification = create_mirrored_notification(
        recipient=recipient,
        event_key="retry:event",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )
    now = timezone.now().replace(microsecond=0)
    retry_client = FakeTelegramClient(
        error=TelegramTransportError(
            code="network_error",
            message="unit-test-token-placeholder transport failed",
            retry_after=7,
        )
    )

    assert dispatch_due_notification_telegram_deliveries(now=now, client=retry_client) == 0

    delivery = NotificationTelegramDelivery.objects.get(notification=notification)
    assert delivery.status == TelegramDeliveryStatus.RETRY
    assert delivery.attempt_count == 1
    assert delivery.next_attempt_at == now + timedelta(seconds=7)
    assert delivery.error_code == "network_error"
    assert "unit-test-token-placeholder" not in delivery.error_message
    assert "[redacted]" in delivery.error_message
    assert (
        dispatch_due_notification_telegram_deliveries(
            now=now + timedelta(seconds=6),
            client=FakeTelegramClient(),
        )
        == 0
    )

    success_client = FakeTelegramClient()
    assert (
        dispatch_due_notification_telegram_deliveries(
            now=now + timedelta(seconds=7),
            client=success_client,
        )
        == 1
    )
    delivery.refresh_from_db()
    assert delivery.status == TelegramDeliveryStatus.SENT
    assert delivery.attempt_count == 2
    assert delivery.next_attempt_at is None
    assert delivery.error_code == delivery.error_message == ""


@pytest.mark.django_db
def test_blocked_and_ineligible_recipients_do_not_leak_to_other_chat(
    django_capture_on_commit_callbacks,
) -> None:
    recipient = create_user(email="blocked@example.test")
    subscription = create_subscription(recipient, telegram_user_id=701, chat_id=801)
    notification = create_mirrored_notification(
        recipient=recipient,
        event_key="permanent:event",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )
    permanent_client = FakeTelegramClient(
        error=TelegramTransportError(
            code="http_403",
            message="Bot was blocked.",
            status_code=403,
        )
    )

    assert dispatch_due_notification_telegram_deliveries(client=permanent_client) == 0
    delivery = NotificationTelegramDelivery.objects.get(notification=notification)
    assert delivery.status == TelegramDeliveryStatus.PERMANENT_FAILURE
    assert delivery.next_attempt_at is None
    subscription.refresh_from_db()
    assert subscription.is_enabled is False
    assert subscription.disabled_at is not None

    inactive_recipient = create_user(email="inactive-before-send@example.test")
    create_subscription(inactive_recipient, telegram_user_id=702, chat_id=802)
    second = create_mirrored_notification(
        recipient=inactive_recipient,
        event_key="inactive-before-send:event",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )
    inactive_recipient.is_active = False
    inactive_recipient.save(update_fields=("is_active",))
    no_send = FakeTelegramClient()
    assert dispatch_due_notification_telegram_deliveries(client=no_send) == 0
    assert no_send.calls == []
    assert (
        NotificationTelegramDelivery.objects.get(notification=second).status
        == TelegramDeliveryStatus.PERMANENT_FAILURE
    )


@pytest.mark.django_db
def test_delivery_and_task_enqueue_failures_do_not_rollback_notification(
    django_capture_on_commit_callbacks,
) -> None:
    recipient = create_user(email="isolated@example.test")
    create_subscription(recipient, telegram_user_id=901, chat_id=1001)

    with (
        patch(
            "apps.notifications.tasks.dispatch_notification_telegram_deliveries.delay",
            side_effect=RuntimeError("broker unavailable"),
        ),
        django_capture_on_commit_callbacks(execute=True),
    ):
        notification, created = create_notification(
            recipient=recipient,
            event_key="isolated:event",
            kind=NotificationKind.APPOINTMENT_ARRIVED,
            title="Збережене сповіщення",
            message="Помилка черги не відкочує запис.",
            deep_link="/calendar",
        )

    assert created is True
    assert notification is not None
    assert Notification.objects.filter(pk=notification.pk).exists()
    assert NotificationTelegramDelivery.objects.filter(notification=notification).exists()

    with patch(
        "apps.notifications.telegram_services.enqueue_notification_telegram_delivery",
        side_effect=RuntimeError("delivery storage unavailable"),
    ):
        second, second_created = create_notification(
            recipient=recipient,
            event_key="isolated-delivery:event",
            kind=NotificationKind.APPOINTMENT_ARRIVED,
            title="Ще одне збережене сповіщення",
            message="Помилка outbox не відкочує запис.",
            deep_link="/calendar",
        )

    assert second_created is True
    assert second is not None
    assert Notification.objects.filter(pk=second.pk).exists()
    assert not NotificationTelegramDelivery.objects.filter(notification=second).exists()


@pytest.mark.django_db
@override_settings(CRM_PUBLIC_URL="https://crm.example.test")
def test_unsafe_stored_deep_link_falls_back_to_crm_root() -> None:
    recipient = create_user(email="safe-link@example.test")
    notification = Notification.objects.create(
        recipient=recipient,
        event_key="unsafe-stored-link:event",
        kind=NotificationKind.APPOINTMENT_ARRIVED,
        title="Безпечне посилання",
        message="Фрагмент не має потрапити у Telegram.",
        deep_link="/calendar#outside",
    )

    assert notification_reply_markup(notification) == {
        "inline_keyboard": [
            [
                {
                    "text": "Відкрити в CRM",
                    "url": "https://crm.example.test/",
                }
            ]
        ]
    }


@pytest.mark.django_db
def test_database_prevents_duplicate_notification_subscription_delivery(
    django_capture_on_commit_callbacks,
) -> None:
    recipient = create_user(email="unique@example.test")
    subscription = create_subscription(recipient, telegram_user_id=1101, chat_id=1201)
    notification = create_mirrored_notification(
        recipient=recipient,
        event_key="unique:event",
        django_capture_on_commit_callbacks=django_capture_on_commit_callbacks,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        NotificationTelegramDelivery.objects.create(
            notification=notification,
            subscription=subscription,
            chat_id=subscription.chat_id,
        )

    assert NotificationTelegramDelivery.objects.filter(notification=notification).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_delivery_enqueue_creates_one_outbox_row() -> None:
    recipient = create_user(email="concurrent-delivery@example.test")
    create_subscription(recipient, telegram_user_id=1301, chat_id=1401)
    notification = Notification.objects.create(
        recipient=recipient,
        event_key="concurrent-delivery:event",
        kind=NotificationKind.APPOINTMENT_ARRIVED,
        title="Одне сповіщення",
        message="Має бути один outbox-запис.",
        deep_link="/calendar",
    )
    barrier = Barrier(2)

    def enqueue_once() -> bool:
        close_old_connections()
        barrier.wait(timeout=5)
        created = enqueue_notification_telegram_delivery(notification.pk)
        connections.close_all()
        return created

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: enqueue_once(), range(2)))

    assert sorted(results) == [False, True]
    assert NotificationTelegramDelivery.objects.filter(notification=notification).count() == 1
