from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.booking_requests.models import (
    TelegramDeliveryStatus,
    TelegramSubscription,
    WorkItemTelegramDelivery,
)
from apps.booking_requests.telegram_services import (
    dispatch_due_work_item_telegram_deliveries,
    process_telegram_update,
    store_telegram_update,
)
from apps.booking_requests.telegram_transport import TelegramMessageResult
from apps.work_items.models import WorkItem, WorkItemKind
from apps.work_items.services import create_work_item, update_work_item

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="Тест",
        last_name=role,
        is_active=True,
    )


def create_subscription(
    user: User,
    *,
    telegram_user_id: int,
    chat_id: int,
) -> TelegramSubscription:
    return TelegramSubscription.objects.create(
        user=user,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        username=f"user{telegram_user_id}",
        first_name="Telegram",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )


def create_assigned_work_item(
    *,
    actor: User,
    assignee: User,
    due_at=None,
) -> WorkItem:
    return create_work_item(
        actor=actor,
        correlation_id="work-item-telegram-create",
        data={
            "kind": WorkItemKind.OTHER,
            "title": "Передзвонити пацієнту",
            "due_at": due_at or timezone.now() + timedelta(hours=1),
            "assignee_id": assignee.pk,
            "comment": "Уточнити зручний час",
            "is_important": True,
        },
    )


def callback_update(
    *,
    update_id: int,
    work_item_id,
    telegram_user_id: int,
    chat_id: int,
) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"callback-{update_id}",
            "data": f"wi:c:{work_item_id}",
            "from": {"id": telegram_user_id},
            "message": {
                "message_id": 9001,
                "chat": {"id": chat_id, "type": "private"},
            },
        },
    }


class FakeTelegramClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.edit_calls: list[dict] = []
        self.answer_calls: list[dict] = []

    def send_message(self, **kwargs) -> TelegramMessageResult:
        self.calls.append(kwargs)
        return TelegramMessageResult(message_id=9000 + len(self.calls))

    def edit_message_text(self, **kwargs) -> None:
        self.edit_calls.append(kwargs)

    def answer_callback_query(self, **kwargs) -> None:
        self.answer_calls.append(kwargs)


@pytest.mark.django_db
@override_settings(CRM_PUBLIC_URL="https://crm.rozhenko.km.ua")
def test_assigned_work_item_is_delivered_only_to_assignee_with_actions() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    other = create_user(email="other@example.test", role=UserRole.RECEPTION)
    assignee_subscription = create_subscription(
        podologist,
        telegram_user_id=101,
        chat_id=201,
    )
    create_subscription(other, telegram_user_id=102, chat_id=202)

    item = create_assigned_work_item(actor=admin, assignee=podologist)
    fake = FakeTelegramClient()

    assert WorkItemTelegramDelivery.objects.count() == 1
    delivery = WorkItemTelegramDelivery.objects.get(work_item=item)
    assert delivery.subscription == assignee_subscription
    assert dispatch_due_work_item_telegram_deliveries(client=fake) == 1

    delivery.refresh_from_db()
    assert delivery.status == TelegramDeliveryStatus.SENT
    assert delivery.message_id == 9001
    assert delivery.last_synced_work_item_version == item.version
    assert delivery.last_synced_is_overdue is False
    assert fake.calls[0]["chat_id"] == 201
    assert "Статус: 🟡 Відкрита" in fake.calls[0]["text"]
    assert "Важлива: Так" in fake.calls[0]["text"]
    assert fake.calls[0]["reply_markup"]["inline_keyboard"][0][0] == {
        "text": "✅ Виконати справу",
        "callback_data": f"wi:c:{item.pk}",
    }
    assert (
        fake.calls[0]["reply_markup"]["inline_keyboard"][1][0]["url"]
        == f"https://crm.rozhenko.km.ua/work-items?item={item.pk}"
    )


@pytest.mark.django_db
def test_assignee_callback_completes_work_item_and_syncs_message() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    create_subscription(podologist, telegram_user_id=301, chat_id=401)
    item = create_assigned_work_item(actor=admin, assignee=podologist)
    initial_client = FakeTelegramClient()
    dispatch_due_work_item_telegram_deliveries(client=initial_client)

    update, created = store_telegram_update(
        callback_update(
            update_id=500,
            work_item_id=item.pk,
            telegram_user_id=301,
            chat_id=401,
        )
    )
    assert created is True
    callback_client = FakeTelegramClient()

    assert process_telegram_update(update.update_id, client=callback_client) == "completed"

    item.refresh_from_db()
    assert item.is_completed is True
    assert item.completed_by == podologist
    assert (
        AuditEvent.objects.filter(
            action=AuditAction.WORK_ITEM_COMPLETED,
            object_id=str(item.pk),
        ).count()
        == 1
    )
    assert callback_client.answer_calls[0]["text"] == "Справу виконано."

    sync_client = FakeTelegramClient()
    assert dispatch_due_work_item_telegram_deliveries(client=sync_client) == 1
    assert "Статус: ✅ Виконана" in sync_client.edit_calls[0]["text"]
    keyboard = sync_client.edit_calls[0]["reply_markup"]["inline_keyboard"]
    assert all("callback_data" not in button for row in keyboard for button in row)


@pytest.mark.django_db
def test_callback_from_non_assignee_is_denied() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    assignee = create_user(email="assignee@example.test", role=UserRole.PODOLOGIST)
    other = create_user(email="other@example.test", role=UserRole.RECEPTION)
    create_subscription(assignee, telegram_user_id=501, chat_id=601)
    create_subscription(other, telegram_user_id=502, chat_id=602)
    item = create_assigned_work_item(actor=admin, assignee=assignee)
    update, _ = store_telegram_update(
        callback_update(
            update_id=700,
            work_item_id=item.pk,
            telegram_user_id=502,
            chat_id=602,
        )
    )
    fake = FakeTelegramClient()

    assert process_telegram_update(update.update_id, client=fake) == "unauthorized"

    item.refresh_from_db()
    assert item.is_completed is False
    assert fake.answer_calls[0]["text"] == "Не вдалося виконати дію."


@pytest.mark.django_db
def test_reassignment_updates_old_message_and_sends_to_new_assignee() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    first = create_user(email="first@example.test", role=UserRole.PODOLOGIST)
    second = create_user(email="second@example.test", role=UserRole.RECEPTION)
    create_subscription(first, telegram_user_id=701, chat_id=801)
    create_subscription(second, telegram_user_id=702, chat_id=802)
    item = create_assigned_work_item(actor=admin, assignee=first)
    dispatch_due_work_item_telegram_deliveries(client=FakeTelegramClient())

    updated = update_work_item(
        actor=admin,
        work_item_id=item.pk,
        correlation_id="work-item-reassigned",
        data={"version": item.version, "assignee_id": second.pk},
    )
    fake = FakeTelegramClient()

    assert dispatch_due_work_item_telegram_deliveries(client=fake) == 2
    assert len(fake.edit_calls) == 1
    assert len(fake.calls) == 1
    assert "Статус: ↪️ Перепризначено" in fake.edit_calls[0]["text"]
    assert fake.edit_calls[0]["reply_markup"]["inline_keyboard"] == []
    assert fake.calls[0]["chat_id"] == 802
    assert "Статус: 🟡 Відкрита" in fake.calls[0]["text"]
    assert WorkItemTelegramDelivery.objects.filter(work_item=updated).count() == 2


@pytest.mark.django_db
def test_due_dispatch_edits_open_message_to_overdue_once() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    assignee = create_user(email="assignee@example.test", role=UserRole.RECEPTION)
    create_subscription(assignee, telegram_user_id=901, chat_id=1001)
    due_at = timezone.now() + timedelta(minutes=10)
    item = create_assigned_work_item(actor=admin, assignee=assignee, due_at=due_at)
    dispatch_due_work_item_telegram_deliveries(
        now=due_at - timedelta(minutes=1),
        client=FakeTelegramClient(),
    )
    fake = FakeTelegramClient()

    assert (
        dispatch_due_work_item_telegram_deliveries(
            now=due_at + timedelta(minutes=1),
            client=fake,
        )
        == 1
    )
    assert "Статус: 🔴 Прострочена" in fake.edit_calls[0]["text"]
    delivery = WorkItemTelegramDelivery.objects.get(work_item=item)
    assert delivery.last_synced_is_overdue is True
    assert (
        dispatch_due_work_item_telegram_deliveries(
            now=due_at + timedelta(minutes=2),
            client=FakeTelegramClient(),
        )
        == 0
    )
