from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import close_old_connections, connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.accounts.services import request_password_reset
from apps.notifications.models import Notification, NotificationKind, NotificationTone
from apps.notifications.services import create_notification, dispatch_due_reminders
from apps.work_items.models import WorkItem, WorkItemKind
from tests.scheduling.test_appointment_detail_and_transitions import create_appointment_response
from tests.scheduling.test_calendar_and_availability import create_appointment
from tests.scheduling.test_create_appointment import KYIV, scheduling_fixture
from tests.visits.test_visit_finish import _finish, _finish_payload, _visit_with_materials

PASSWORD = "test-only-password-placeholder"  # noqa: S105


def create_user(
    *,
    email: str,
    role: str = UserRole.ADMIN,
    is_active: bool = True,
) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="Тест",
        last_name="Сповіщення",
        is_active=is_active,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_test_notification(
    *,
    recipient: User,
    index: int,
    is_read: bool = False,
) -> Notification:
    notification = Notification.objects.create(
        recipient=recipient,
        event_key=f"test:event:{index}",
        kind=NotificationKind.WORK_ITEM_OVERDUE,
        title=f"Сповіщення {index}",
        message="Безпечний server-side текст.",
        tone=NotificationTone.CORAL,
        is_important=index % 2 == 0,
        deep_link=f"/work-items?item={uuid4()}",
        occurred_at=timezone.now() + timedelta(seconds=index),
    )
    if is_read:
        notification.read_at = timezone.now()
        notification.save(update_fields=("read_at",))
    return notification


@pytest.mark.django_db
def test_list_is_recipient_scoped_cursor_paginated_and_redacted() -> None:
    actor = create_user(email="actor@example.test", role=UserRole.RECEPTION)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    for index in range(32):
        create_test_notification(recipient=actor, index=index, is_read=index % 2 == 0)
    create_test_notification(recipient=foreign, index=99)

    client = authenticated_client(actor)
    first_page = client.get("/api/v1/notifications")

    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["total_count"] == 32
    assert first_body["unread_count"] == 16
    assert len(first_body["notifications"]) == 30
    assert first_body["next_cursor"]
    assert set(first_body["notifications"][0]) == {
        "id",
        "kind",
        "title",
        "message",
        "tone",
        "is_important",
        "deep_link",
        "occurred_at",
        "created_at",
        "read_at",
        "is_read",
    }

    second_page = client.get(
        "/api/v1/notifications",
        {"cursor": first_body["next_cursor"]},
    )
    unread = client.get("/api/v1/notifications", {"status": "unread"})

    assert second_page.status_code == 200
    assert len(second_page.json()["notifications"]) == 2
    assert second_page.json()["next_cursor"] is None
    assert unread.status_code == 200
    assert len(unread.json()["notifications"]) == 16
    assert all(not item["is_read"] for item in unread.json()["notifications"])
    assert foreign.notifications.count() == 1


@pytest.mark.django_db
def test_read_mutations_are_idempotent_strict_and_hide_foreign_ids() -> None:
    actor = create_user(email="actor@example.test")
    foreign = create_user(email="foreign@example.test")
    first = create_test_notification(recipient=actor, index=1)
    second = create_test_notification(recipient=actor, index=2)
    foreign_notification = create_test_notification(recipient=foreign, index=3)
    client = authenticated_client(actor)

    malformed = client.post(
        f"/api/v1/notifications/{first.pk}/read",
        [],
        format="json",
    )
    read = client.post(f"/api/v1/notifications/{first.pk}/read")
    repeated = client.post(f"/api/v1/notifications/{first.pk}/read")
    hidden = client.post(f"/api/v1/notifications/{foreign_notification.pk}/read")

    assert malformed.status_code == 422
    assert read.status_code == repeated.status_code == 200
    assert read.json()["read_at"] == repeated.json()["read_at"]
    assert hidden.status_code == 404

    marked = client.post("/api/v1/notifications/read-all")
    marked_again = client.post("/api/v1/notifications/read-all")

    assert marked.status_code == marked_again.status_code == 200
    assert marked.json() == {"marked_count": 1, "unread_count": 0}
    assert marked_again.json() == {"marked_count": 0, "unread_count": 0}
    second.refresh_from_db()
    foreign_notification.refresh_from_db()
    assert second.read_at is not None
    assert foreign_notification.read_at is None


@pytest.mark.django_db
def test_list_validates_filter_and_requires_authentication() -> None:
    actor = create_user(email="actor@example.test")

    invalid = authenticated_client(actor).get("/api/v1/notifications", {"status": "later"})
    anonymous = APIClient().get("/api/v1/notifications")

    assert invalid.status_code == 422
    assert anonymous.status_code == 401


@pytest.mark.django_db
def test_session_exposes_only_the_actor_unread_count() -> None:
    actor = create_user(email="actor@example.test")
    foreign = create_user(email="foreign@example.test")
    create_test_notification(recipient=actor, index=1)
    create_test_notification(recipient=actor, index=2, is_read=True)
    create_test_notification(recipient=foreign, index=3)

    response = authenticated_client(actor).get("/api/v1/session")

    assert response.status_code == 200
    assert response.json()["notification_unread_count"] == 1


@pytest.mark.django_db
def test_create_notification_normalizes_links_and_skips_inactive_users() -> None:
    podologist = create_user(
        email="podologist@example.test",
        role=UserRole.PODOLOGIST,
    )
    inactive = create_user(email="inactive@example.test", is_active=False)

    inaccessible, created = create_notification(
        recipient=podologist,
        event_key="link:finance",
        kind=NotificationKind.APPOINTMENT_ARRIVED,
        title="Готово",
        message="Перейдіть до запису.",
        deep_link="/finance?operation=PAYMENT:secret",
    )
    unsafe, _ = create_notification(
        recipient=podologist,
        event_key="link:unsafe",
        kind=NotificationKind.APPOINTMENT_ARRIVED,
        title="Готово",
        message="Перейдіть до запису.",
        deep_link="//outside.example/steal",
    )
    skipped, skipped_created = create_notification(
        recipient=inactive,
        event_key="inactive:event",
        kind=NotificationKind.WORK_ITEM_OVERDUE,
        title="Прострочено",
        message="Справа очікує.",
        deep_link="/work-items",
    )

    assert created is True
    assert inaccessible is not None and inaccessible.deep_link == "/"
    assert unsafe is not None and unsafe.deep_link == "/"
    assert skipped is None and skipped_created is False
    assert not inactive.notifications.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_create_is_deduplicated() -> None:
    recipient = create_user(email="recipient@example.test")
    barrier = Barrier(2)

    def create_once() -> bool:
        close_old_connections()
        local_recipient = User.objects.get(pk=recipient.pk)
        barrier.wait(timeout=5)
        _, created = create_notification(
            recipient=local_recipient,
            event_key="concurrent:event",
            kind=NotificationKind.WORK_ITEM_OVERDUE,
            title="Прострочено",
            message="Справа очікує.",
            deep_link="/work-items",
        )
        connections.close_all()
        return created

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create_once(), range(2)))

    assert sorted(results) == [False, True]
    assert (
        Notification.objects.filter(
            recipient=recipient,
            event_key="concurrent:event",
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_due_reminders_are_repeat_safe_and_follow_schedule_changes() -> None:
    specialist, service, room, patient = scheduling_fixture()
    now = timezone.now().replace(microsecond=0)
    starts_at = now + timedelta(minutes=15)
    appointment = create_appointment(
        patient=patient,
        specialist=specialist,
        service=service,
        room=room,
        starts_at=starts_at,
    )

    first = dispatch_due_reminders(now=now)
    repeated = dispatch_due_reminders(now=now)
    appointment.time_range = (
        starts_at + timedelta(seconds=30),
        starts_at + timedelta(minutes=service.duration_minutes, seconds=30),
    )
    appointment.save(update_fields=("time_range", "updated_at"))
    rescheduled = dispatch_due_reminders(now=now)
    appointment.status_id = "CANCELED"
    appointment.save(update_fields=("status", "updated_at"))
    canceled = dispatch_due_reminders(now=now)

    assert (first, repeated, rescheduled, canceled) == (1, 0, 1, 0)
    assert (
        Notification.objects.filter(
            recipient=specialist,
            kind=NotificationKind.APPOINTMENT_UPCOMING,
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_overdue_work_item_reminders_filter_state_and_inactive_assignees() -> None:
    actor = create_user(email="creator@example.test")
    assignee = create_user(email="assignee@example.test", role=UserRole.RECEPTION)
    inactive = create_user(email="inactive@example.test", is_active=False)
    now = timezone.now().replace(microsecond=0)
    item = WorkItem.objects.create(
        kind=WorkItemKind.OTHER,
        title="Зателефонувати пацієнту",
        due_at=now - timedelta(minutes=2),
        assignee=assignee,
        created_by=actor,
    )
    WorkItem.objects.create(
        kind=WorkItemKind.OTHER,
        title="Не надсилати неактивному",
        due_at=now - timedelta(minutes=2),
        assignee=inactive,
        created_by=actor,
    )

    assert dispatch_due_reminders(now=now) == 1
    assert dispatch_due_reminders(now=now) == 0

    item.due_at = now - timedelta(minutes=1)
    item.save(update_fields=("due_at", "updated_at"))
    assert dispatch_due_reminders(now=now) == 1

    item.is_completed = True
    item.completed_at = now
    item.completed_by = actor
    item.save(update_fields=("is_completed", "completed_at", "completed_by", "updated_at"))
    item.due_at = now - timedelta(seconds=30)
    item.save(update_fields=("due_at", "updated_at"))
    assert dispatch_due_reminders(now=now) == 0
    assert not inactive.notifications.exists()


@pytest.mark.django_db
def test_password_reset_event_notifies_active_admins_once(
    django_capture_on_commit_callbacks,
) -> None:
    first_admin = create_user(email="first-admin@example.test")
    second_admin = create_user(email="second-admin@example.test")
    inactive_admin = create_user(email="inactive-admin@example.test", is_active=False)
    target = create_user(email="target@example.test", role=UserRole.PODOLOGIST)

    with django_capture_on_commit_callbacks(execute=True):
        reset_request = request_password_reset(user=target, correlation_id="notification-test")
    with django_capture_on_commit_callbacks(execute=True):
        repeated = request_password_reset(user=target, correlation_id="notification-repeat")

    assert repeated.pk == reset_request.pk
    assert (
        Notification.objects.filter(
            kind=NotificationKind.PASSWORD_RESET_REQUESTED,
        ).count()
        == 2
    )
    assert first_admin.notifications.count() == second_admin.notifications.count() == 1
    assert inactive_admin.notifications.count() == 0
    assert first_admin.notifications.get().deep_link == "/password-resets"


@pytest.mark.django_db
def test_appointment_status_events_notify_the_assigned_podologist_on_commit(
    django_capture_on_commit_callbacks,
) -> None:
    specialist, service, room, patient = scheduling_fixture()
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    arrived_source = create_appointment_response(
        actor=reception,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    client = authenticated_client(reception)
    confirmed = client.post(
        f"/api/v1/appointments/{arrived_source['id']}/status",
        {"version": arrived_source["version"], "status_code": "CONFIRMED"},
        format="json",
    )
    with django_capture_on_commit_callbacks(execute=True):
        arrived = client.post(
            f"/api/v1/appointments/{arrived_source['id']}/status",
            {"version": confirmed.json()["version"], "status_code": "ARRIVED"},
            format="json",
        )

    canceled_source = create_appointment_response(
        actor=reception,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
        starts_at=datetime(2026, 7, 27, 12, 0, tzinfo=KYIV),
    )
    with django_capture_on_commit_callbacks(execute=True):
        canceled = client.post(
            f"/api/v1/appointments/{canceled_source['id']}/cancel",
            {"version": canceled_source["version"], "reason": "Пацієнтка захворіла"},
            format="json",
        )

    assert arrived.status_code == canceled.status_code == 200
    assert set(specialist.notifications.values_list("kind", flat=True)) == {
        NotificationKind.APPOINTMENT_ARRIVED,
        NotificationKind.APPOINTMENT_CANCELED,
    }
    assert all(
        notification.deep_link.startswith("/calendar?appointment=")
        for notification in specialist.notifications.all()
    )


@pytest.mark.django_db
def test_visit_finish_event_notifies_active_finance_roles_on_commit(
    django_capture_on_commit_callbacks,
) -> None:
    admin = create_user(email="admin@example.test")
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    _, visit, _ = _visit_with_materials(admin=admin)

    with django_capture_on_commit_callbacks(execute=True):
        response = _finish(
            authenticated_client(admin),
            str(visit.pk),
            _finish_payload(version=visit.version),
        )

    assert response.status_code == 201
    for recipient in (admin, reception):
        notification = recipient.notifications.get(kind=NotificationKind.VISIT_PAYMENT_READY)
        assert notification.deep_link.startswith("/finance?operation=PAYMENT:")
