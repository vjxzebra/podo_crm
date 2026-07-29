from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.booking_requests.models import TelegramSubscription, WorkItemTelegramDelivery
from apps.work_items.models import WorkItem, WorkItemKind

MIGRATION_OLD = [("booking_requests", "0005_telegramupdate_callback_data_and_more")]
MIGRATION_NEW = [("booking_requests", "0006_workitemtelegramdelivery")]


@pytest.mark.django_db(transaction=True)
def test_work_item_telegram_delivery_migration_reverses_without_domain_data_loss() -> None:
    user = User.objects.create_user(
        email="migration-assignee@example.test",
        password=None,
        role=UserRole.RECEPTION,
        first_name="Migration",
        last_name="Assignee",
    )
    subscription = TelegramSubscription.objects.create(
        user=user,
        telegram_user_id=1101,
        chat_id=1201,
        username="migration",
        first_name="Migration",
        is_enabled=True,
        linked_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    item = WorkItem.objects.create(
        kind=WorkItemKind.OTHER,
        title="Migration work item",
        due_at=timezone.now() + timedelta(hours=1),
        assignee=user,
        created_by=user,
    )
    WorkItemTelegramDelivery.objects.create(
        work_item=item,
        subscription=subscription,
        chat_id=subscription.chat_id,
    )
    user_id = user.pk
    item_id = item.pk

    try:
        MigrationExecutor(connection).migrate(MIGRATION_OLD)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('booking_requests_workitemtelegramdelivery')")
            assert cursor.fetchone() == (None,)
        assert User.objects.filter(pk=user_id).exists()
        assert WorkItem.objects.filter(pk=item_id).exists()

        MigrationExecutor(connection).migrate(MIGRATION_NEW)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('booking_requests_workitemtelegramdelivery')")
            assert cursor.fetchone() == ("booking_requests_workitemtelegramdelivery",)
        assert User.objects.filter(pk=user_id).exists()
        assert WorkItem.objects.filter(pk=item_id).exists()
        assert WorkItemTelegramDelivery.objects.count() == 0
    finally:
        MigrationExecutor(connection).migrate(MIGRATION_NEW)
