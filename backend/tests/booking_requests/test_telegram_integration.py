from datetime import timedelta
from io import StringIO
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.booking_requests.models import (
    BookingRequestSource,
    BookingRequestStatus,
    TelegramDelivery,
    TelegramDeliveryStatus,
    TelegramLinkIntent,
    TelegramSubscription,
    TelegramUpdate,
)
from apps.booking_requests.services import create_booking_request, process_booking_request
from apps.booking_requests.telegram_services import (
    dispatch_due_telegram_deliveries,
    process_telegram_update,
    store_telegram_update,
)
from apps.booking_requests.telegram_transport import TelegramMessageResult, TelegramTransportError

PASSWORD = "correct horse battery staple"  # noqa: S105
WEBHOOK_SECRET = "unit-test-webhook-secret"  # noqa: S105
WRONG_WEBHOOK_SECRET = "wrong-unit-test-webhook-secret"  # noqa: S105


def create_user(*, email: str, role: str, is_active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="Тест",
        last_name=role,
        is_active=is_active,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def telegram_start_update(
    *,
    update_id: int,
    payload: str,
    telegram_user_id: int = 1001,
    chat_id: int = 2002,
    chat_type: str = "private",
) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "text": f"/start {payload}",
            "from": {
                "id": telegram_user_id,
                "username": "crm_worker",
                "first_name": "CRM",
            },
            "chat": {"id": chat_id, "type": chat_type},
        },
    }


def telegram_callback_update(
    *,
    update_id: int,
    data: str,
    callback_query_id: str = "callback-1",
    telegram_user_id: int = 1001,
    chat_id: int = 2002,
    chat_type: str = "private",
    message_id: int = 3003,
) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_query_id,
            "data": data,
            "from": {
                "id": telegram_user_id,
                "username": "crm_worker",
                "first_name": "CRM",
            },
            "message": {
                "message_id": message_id,
                "chat": {"id": chat_id, "type": chat_type},
            },
        },
    }


class FakeTelegramClient:
    def __init__(
        self,
        *,
        error: TelegramTransportError | None = None,
        edit_error: TelegramTransportError | None = None,
        answer_error: TelegramTransportError | None = None,
    ) -> None:
        self.error = error
        self.edit_error = edit_error
        self.answer_error = answer_error
        self.calls: list[dict] = []
        self.edit_calls: list[dict] = []
        self.answer_calls: list[dict] = []

    def send_message(self, **kwargs) -> TelegramMessageResult:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return TelegramMessageResult(message_id=9000 + len(self.calls))

    def edit_message_text(self, **kwargs) -> None:
        self.edit_calls.append(kwargs)
        if self.edit_error is not None:
            raise self.edit_error

    def answer_callback_query(self, **kwargs) -> None:
        self.answer_calls.append(kwargs)
        if self.answer_error is not None:
            raise self.answer_error


@pytest.mark.django_db
def test_personal_link_intent_is_one_time_private_and_digest_only() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)

    response = client.post("/api/v1/telegram/link-intents", {}, format="json")

    assert response.status_code == 201
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    payload = parse_qs(urlparse(body["url"]).query)["start"][0]
    assert len(payload) >= 40
    intent = TelegramLinkIntent.objects.get(user=admin)
    assert payload not in intent.payload_digest

    with override_settings(TELEGRAM_WEBHOOK_SECRET=WEBHOOK_SECRET):
        linked = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            telegram_start_update(update_id=1, payload=payload),
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
        )
        replay = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            telegram_start_update(update_id=1, payload=payload),
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
        )

    assert linked.status_code == replay.status_code == 200
    subscription = TelegramSubscription.objects.get(user=admin)
    assert subscription.is_enabled is True
    assert subscription.telegram_user_id == 1001
    assert subscription.chat_id == 2002
    assert TelegramUpdate.objects.count() == 1
    intent.refresh_from_db()
    assert intent.used_at is not None
    assert AuditEvent.objects.filter(action=AuditAction.TELEGRAM_SUBSCRIPTION_LINKED).count() == 1

    second = APIClient().post(
        "/api/v1/integrations/telegram/webhook",
        telegram_start_update(update_id=2, payload=payload, telegram_user_id=1002, chat_id=2003),
        format="json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
    )
    assert second.status_code == 503


@pytest.mark.django_db
def test_link_rejects_podologist_expired_group_and_taken_identity() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    other = create_user(email="other@example.test", role=UserRole.RECEPTION)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    forbidden = authenticated_client(podologist).post(
        "/api/v1/telegram/link-intents", {}, format="json"
    )
    assert forbidden.status_code == 403

    response = authenticated_client(admin).post("/api/v1/telegram/link-intents", {}, format="json")
    payload = parse_qs(urlparse(response.json()["url"]).query)["start"][0]
    intent = TelegramLinkIntent.objects.get(user=admin)
    intent.expires_at = timezone.now() - timedelta(seconds=1)
    intent.save(update_fields=("expires_at",))
    with override_settings(TELEGRAM_WEBHOOK_SECRET=WEBHOOK_SECRET):
        expired = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            telegram_start_update(update_id=10, payload=payload),
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
        )
    assert expired.status_code == 200
    assert not TelegramSubscription.objects.filter(user=admin).exists()

    fresh = authenticated_client(admin).post("/api/v1/telegram/link-intents", {}, format="json")
    fresh_payload = parse_qs(urlparse(fresh.json()["url"]).query)["start"][0]
    with override_settings(TELEGRAM_WEBHOOK_SECRET=WEBHOOK_SECRET):
        group = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            telegram_start_update(update_id=11, payload=fresh_payload, chat_type="group"),
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
        )
    assert group.status_code == 200
    assert not TelegramSubscription.objects.filter(user=admin).exists()

    TelegramSubscription.objects.create(
        user=other,
        telegram_user_id=3001,
        chat_id=4001,
        username="other",
        first_name="Other",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    fresh_two = authenticated_client(admin).post("/api/v1/telegram/link-intents", {}, format="json")
    taken_payload = parse_qs(urlparse(fresh_two.json()["url"]).query)["start"][0]
    with override_settings(TELEGRAM_WEBHOOK_SECRET=WEBHOOK_SECRET):
        taken = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            telegram_start_update(
                update_id=12,
                payload=taken_payload,
                telegram_user_id=3001,
                chat_id=5001,
            ),
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
        )
    assert taken.status_code == 200
    assert not TelegramSubscription.objects.filter(user=admin).exists()


@pytest.mark.django_db
def test_subscription_api_reports_and_disconnects_with_pii_safe_audit() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    subscription = TelegramSubscription.objects.create(
        user=reception,
        telegram_user_id=7001,
        chat_id=8001,
        username="frontdesk",
        first_name="Front",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    client = authenticated_client(reception)

    current = client.get("/api/v1/telegram/subscription")
    disconnected = client.delete("/api/v1/telegram/subscription")

    assert current.status_code == 200
    assert current["Cache-Control"] == "no-store"
    assert current.json()["is_linked"] is True
    assert disconnected.status_code == 204
    subscription.refresh_from_db()
    assert subscription.is_enabled is False
    event = AuditEvent.objects.get(action=AuditAction.TELEGRAM_SUBSCRIPTION_UNLINKED)
    assert "7001" not in str(event.after)
    assert "8001" not in str(event.after)


@pytest.mark.django_db
def test_webhook_secret_and_update_dedupe() -> None:
    update = {
        "update_id": 50,
        "message": {"text": "/unknown", "from": {"id": 1}, "chat": {"id": 2, "type": "private"}},
    }

    missing_config = APIClient().post(
        "/api/v1/integrations/telegram/webhook", update, format="json"
    )
    with override_settings(TELEGRAM_WEBHOOK_SECRET=WEBHOOK_SECRET):
        wrong_secret = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            update,
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WRONG_WEBHOOK_SECRET,
        )
        first = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            update,
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
        )
        duplicate = APIClient().post(
            "/api/v1/integrations/telegram/webhook",
            update,
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=WEBHOOK_SECRET,
        )

    assert missing_config.status_code == 503
    assert wrong_secret.status_code == 401
    assert first.status_code == duplicate.status_code == 200
    assert TelegramUpdate.objects.filter(update_id=50).count() == 1


@pytest.mark.django_db
def test_new_booking_request_creates_durable_delivery_and_dispatches_plain_text() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    TelegramSubscription.objects.create(
        user=admin,
        telegram_user_id=11,
        chat_id=22,
        username="admin",
        first_name="Admin",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    TelegramSubscription.objects.create(
        user=podologist,
        telegram_user_id=33,
        chat_id=44,
        username="pod",
        first_name="Pod",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )

    item = create_booking_request(
        data={
            "source": BookingRequestSource.INSTAGRAM,
            "client_name": "<Марія>",
            "phone": "+380671112233",
            "message": "Потрібен час",
        },
        correlation_id="telegram-delivery",
    )
    fake = FakeTelegramClient()
    sent_count = dispatch_due_telegram_deliveries(client=fake)

    assert TelegramDelivery.objects.count() == 1
    delivery = TelegramDelivery.objects.get(booking_request=item)
    assert sent_count == 1
    assert delivery.status == TelegramDeliveryStatus.SENT
    assert delivery.message_id == 9001
    assert delivery.last_synced_request_version == item.version
    assert fake.calls[0]["chat_id"] == 22
    assert "parse_mode" not in fake.calls[0]
    assert "<Марія>" in fake.calls[0]["text"]
    assert (
        fake.calls[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"br:p:{item.pk}"
    )


@pytest.mark.django_db
def test_authorized_callback_processes_request_and_edits_all_sent_copies() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    TelegramSubscription.objects.create(
        user=admin,
        telegram_user_id=1001,
        chat_id=2002,
        username="admin",
        first_name="Admin",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    TelegramSubscription.objects.create(
        user=reception,
        telegram_user_id=1002,
        chat_id=2003,
        username="frontdesk",
        first_name="Front",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    item = create_booking_request(
        data={"source": BookingRequestSource.FACEBOOK, "client_name": "Марія"},
        correlation_id="callback-process",
    )
    send_client = FakeTelegramClient()
    assert dispatch_due_telegram_deliveries(client=send_client) == 2

    stored, created = store_telegram_update(
        telegram_callback_update(update_id=70, data=f"br:p:{item.pk}")
    )
    assert created is True
    callback_client = FakeTelegramClient()
    result = process_telegram_update(stored.update_id, client=callback_client)

    item.refresh_from_db()
    assert result == "processed"
    assert item.status == BookingRequestStatus.PROCESSED
    assert item.processed_by == admin
    assert callback_client.answer_calls == [
        {"callback_query_id": "callback-1", "text": "Заявку оброблено."}
    ]
    assert AuditEvent.objects.filter(action=AuditAction.BOOKING_REQUEST_PROCESSED).count() == 1

    repeated, _ = store_telegram_update(
        telegram_callback_update(
            update_id=72,
            data=f"br:p:{item.pk}",
            callback_query_id="callback-2",
            telegram_user_id=1002,
            chat_id=2003,
        )
    )
    repeated_client = FakeTelegramClient()
    repeated_result = process_telegram_update(repeated.update_id, client=repeated_client)
    item.refresh_from_db()
    assert repeated_result == "already_processed"
    assert item.processed_by == admin
    assert repeated_client.answer_calls == [
        {"callback_query_id": "callback-2", "text": "Заявку вже оброблено."}
    ]
    assert AuditEvent.objects.filter(action=AuditAction.BOOKING_REQUEST_PROCESSED).count() == 1

    edit_client = FakeTelegramClient()
    assert dispatch_due_telegram_deliveries(client=edit_client) == 2
    assert len(edit_client.edit_calls) == 2
    assert all("✅ Оброблено" in call["text"] for call in edit_client.edit_calls)
    assert all("Обробив: Тест admin" in call["text"] for call in edit_client.edit_calls)
    assert all("callback_data" not in str(call["reply_markup"]) for call in edit_client.edit_calls)
    assert (
        TelegramDelivery.objects.filter(
            booking_request=item,
            status=TelegramDeliveryStatus.SENT,
            last_synced_request_version=item.version,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_unauthorized_callback_does_not_disclose_or_process_request() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    TelegramSubscription.objects.create(
        user=podologist,
        telegram_user_id=1001,
        chat_id=2002,
        username="pod",
        first_name="Pod",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    item = create_booking_request(
        data={"source": BookingRequestSource.WEBSITE},
        correlation_id="callback-denied",
        actor=admin,
    )
    stored, _ = store_telegram_update(
        telegram_callback_update(update_id=71, data=f"br:p:{item.pk}")
    )
    fake = FakeTelegramClient()

    result = process_telegram_update(stored.update_id, client=fake)

    item.refresh_from_db()
    assert result == "unauthorized"
    assert item.status == BookingRequestStatus.NEW
    assert fake.answer_calls == [
        {"callback_query_id": "callback-1", "text": "Не вдалося виконати дію."}
    ]
    assert AuditEvent.objects.filter(action=AuditAction.BOOKING_REQUEST_PROCESSED).count() == 0


@pytest.mark.django_db
def test_cross_chat_edit_retry_and_blocked_chat_disable_subscription() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    subscription = TelegramSubscription.objects.create(
        user=admin,
        telegram_user_id=1001,
        chat_id=2002,
        username="admin",
        first_name="Admin",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    item = create_booking_request(
        data={"source": BookingRequestSource.INSTAGRAM},
        correlation_id="edit-retry",
    )
    delivery = TelegramDelivery.objects.get(booking_request=item)
    delivery.status = TelegramDeliveryStatus.SENT
    delivery.message_id = 9001
    delivery.last_synced_request_version = item.version
    delivery.save(
        update_fields=("status", "message_id", "last_synced_request_version", "updated_at")
    )
    process_booking_request(
        actor=admin,
        booking_request_id=item.pk,
        requested_version=item.version,
        correlation_id="edit-retry-process",
    )
    retry_client = FakeTelegramClient(
        edit_error=TelegramTransportError(
            code="http_429",
            message="Too Many Requests",
            status_code=429,
            retry_after=7,
        )
    )

    dispatch_due_telegram_deliveries(client=retry_client)
    delivery.refresh_from_db()
    assert delivery.status == TelegramDeliveryStatus.RETRY
    assert delivery.next_attempt_at is not None
    assert delivery.error_code == "http_429"

    delivery.next_attempt_at = timezone.now()
    delivery.save(update_fields=("next_attempt_at", "updated_at"))
    blocked_client = FakeTelegramClient(
        edit_error=TelegramTransportError(
            code="http_403",
            message="Forbidden",
            status_code=403,
        )
    )
    dispatch_due_telegram_deliveries(client=blocked_client)

    delivery.refresh_from_db()
    subscription.refresh_from_db()
    assert delivery.status == TelegramDeliveryStatus.PERMANENT_FAILURE
    assert subscription.is_enabled is False


@pytest.mark.django_db
def test_telegram_delivery_status_command_reports_safe_counts() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    TelegramSubscription.objects.create(
        user=admin,
        telegram_user_id=7777,
        chat_id=8888,
        username="admin",
        first_name="Admin",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    create_booking_request(
        data={"source": BookingRequestSource.WEBSITE},
        correlation_id="status-command",
    )
    output = StringIO()

    call_command("telegram_delivery_status", stdout=output)

    text = output.getvalue()
    assert "Telegram delivery status:" in text
    assert "- PENDING: 1" in text
    assert "8888" not in text
    assert "7777" not in text


@pytest.mark.django_db
def test_delivery_retry_and_blocked_chat_disable_subscription() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    subscription = TelegramSubscription.objects.create(
        user=admin,
        telegram_user_id=101,
        chat_id=202,
        username="admin",
        first_name="Admin",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    item = create_booking_request(
        data={"source": BookingRequestSource.WEBSITE}, correlation_id="retry"
    )
    retry_client = FakeTelegramClient(
        error=TelegramTransportError(
            code="http_429",
            message="Too Many Requests",
            status_code=429,
            retry_after=7,
        )
    )

    dispatch_due_telegram_deliveries(client=retry_client)
    delivery = TelegramDelivery.objects.get(booking_request=item)
    assert delivery.status == TelegramDeliveryStatus.RETRY
    assert delivery.next_attempt_at is not None
    assert delivery.error_code == "http_429"

    delivery.status = TelegramDeliveryStatus.PENDING
    delivery.next_attempt_at = None
    delivery.save(update_fields=("status", "next_attempt_at", "updated_at"))
    blocked_client = FakeTelegramClient(
        error=TelegramTransportError(
            code="http_403",
            message="Forbidden",
            status_code=403,
        )
    )
    dispatch_due_telegram_deliveries(client=blocked_client)
    delivery.refresh_from_db()
    subscription.refresh_from_db()
    assert delivery.status == TelegramDeliveryStatus.PERMANENT_FAILURE
    assert subscription.is_enabled is False
