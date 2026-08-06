from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import User, UserRole
from apps.notifications.models import Notification, NotificationKind

MIGRATION_ZERO = [("notifications", None)]
MIGRATION_CURRENT = [("notifications", "0002_notificationtelegramdelivery")]


def create_user(email: str) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=UserRole.ADMIN,
    )


@pytest.mark.django_db
def test_database_constraints_protect_notification_state() -> None:
    recipient = create_user("constraint-recipient@example.test")
    notification = Notification.objects.create(
        recipient=recipient,
        event_key="constraint:event",
        kind=NotificationKind.WORK_ITEM_OVERDUE,
        title="Прострочено",
        message="Справа очікує.",
        deep_link="/work-items",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Notification.objects.create(
            recipient=recipient,
            event_key="constraint:event",
            kind=NotificationKind.WORK_ITEM_OVERDUE,
            title="Дублікат",
            message="Не має зберегтися.",
            deep_link="/work-items",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Notification.objects.create(
            recipient=recipient,
            event_key="",
            kind=NotificationKind.WORK_ITEM_OVERDUE,
            title="Порожній ключ",
            message="Не має зберегтися.",
            deep_link="/work-items",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Notification.objects.create(
            recipient=recipient,
            event_key="constraint:unsafe-link",
            kind=NotificationKind.WORK_ITEM_OVERDUE,
            title="Зовнішнє посилання",
            message="Не має зберегтися.",
            deep_link="https://outside.example/",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Notification.objects.filter(pk=notification.pk).update(
            read_at=notification.created_at - timedelta(seconds=1)
        )


@pytest.mark.django_db(transaction=True)
def test_notification_migration_reverses_and_reapplies_without_touching_accounts() -> None:
    recipient = create_user("migration-recipient@example.test")
    Notification.objects.create(
        recipient=recipient,
        event_key="migration:event",
        kind=NotificationKind.WORK_ITEM_OVERDUE,
        title="Прострочено",
        message="Справа очікує.",
        deep_link="/work-items",
    )
    account_snapshot = list(User.objects.values_list("pk", "email", "role"))
    executor = MigrationExecutor(connection)

    try:
        executor.migrate(MIGRATION_ZERO)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('notifications_notification')")
            assert cursor.fetchone() == (None,)
        assert list(User.objects.values_list("pk", "email", "role")) == account_snapshot

        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_CURRENT)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('notifications_notification')")
            assert cursor.fetchone() == ("notifications_notification",)
        assert list(User.objects.values_list("pk", "email", "role")) == account_snapshot
        assert Notification.objects.count() == 0
    finally:
        MigrationExecutor(connection).migrate(MIGRATION_CURRENT)
