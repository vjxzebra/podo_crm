from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.billing.models import CashShift
from apps.billing.services import close_cash_shift

MIGRATION_OLD = [("billing", "0004_refund_cash_adjustments")]
MIGRATION_NEW = [("billing", "0005_cash_shift_close_history")]
MIGRATION_LATEST = [("billing", "0010_pricing_contract")]


@pytest.mark.django_db(transaction=True)
def test_forward_backfills_typed_actor_labels_while_append_only_trigger_is_restored() -> None:
    actor = User.objects.create_user(
        email="migration-old@example.test",
        password=None,
        role=UserRole.RECEPTION,
        first_name="Історичне",
        last_name="Ім’я",
    )
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_OLD)
    try:
        old_apps = executor.loader.project_state(MIGRATION_OLD).apps
        OldCashShift = old_apps.get_model("billing", "CashShift")
        OldCashLedgerEntry = old_apps.get_model("billing", "CashLedgerEntry")
        OldCashAdjustment = old_apps.get_model("billing", "CashAdjustment")
        shift_id = uuid4()
        ledger_id = uuid4()
        shift = OldCashShift.objects.create(
            id=shift_id,
            public_number=f"CSH-{shift_id.hex[:12].upper()}",
            employee_id=actor.pk,
            status="OPEN",
        )
        with transaction.atomic():
            ledger = OldCashLedgerEntry.objects.create(
                id=ledger_id,
                public_number=f"TXN-{ledger_id.hex[:12].upper()}",
                cash_shift=shift,
                created_by_id=actor.pk,
                kind="DEPOSIT",
                amount_minor=700,
                payment_method="",
                idempotency_key="migration-deposit",
                payload_hash="a" * 64,
            )
            OldCashAdjustment.objects.create(
                ledger_entry=ledger,
                reason="Історичний рух",
                comment="",
                employee_name_snapshot="Історичне Ім’я",
                employee_email_snapshot="migration-old@example.test",
            )

        old_apps.get_model("accounts", "User").objects.filter(pk=actor.pk).update(
            first_name="Нове",
            last_name="Ім’я",
            email="migration-new@example.test",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_NEW)
        new_apps = executor.loader.project_state(MIGRATION_NEW).apps
        migrated_shift = new_apps.get_model("billing", "CashShift").objects.get(pk=shift_id)
        migrated_entry = new_apps.get_model("billing", "CashLedgerEntry").objects.get(pk=ledger_id)
        assert migrated_shift.employee_name_snapshot == "Нове Ім’я"
        assert migrated_shift.employee_email_snapshot == "migration-new@example.test"
        assert migrated_entry.actor_name_snapshot == "Історичне Ім’я"
        assert migrated_entry.actor_email_snapshot == "migration-old@example.test"
        assert migrated_entry.actor_role_snapshot == UserRole.RECEPTION

        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE billing_cashledgerentry SET actor_name_snapshot = %s WHERE id = %s",
                ["Підміна", ledger_id],
            )
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            mismatched_id = uuid4()
            cursor.execute(
                """
                INSERT INTO billing_cashshift (
                    id, public_number, employee_id,
                    employee_name_snapshot, employee_email_snapshot,
                    employee_role_snapshot, status, opened_at,
                    closed_at, expected_cash_at_close_minor,
                    actual_cash_at_close_minor, discrepancy_minor, close_comment,
                    closed_by_id, closed_by_name_snapshot, closed_by_email_snapshot,
                    closed_by_role_snapshot, close_idempotency_key, close_payload_hash
                ) VALUES (
                    %s, %s, %s, 'Підміна', %s, %s, 'OPEN', NOW(),
                    NULL, NULL, NULL, NULL, '', NULL, '', '', '', '', ''
                )
                """,
                [
                    mismatched_id,
                    f"CSH-{mismatched_id.hex[:12].upper()}",
                    actor.pk,
                    "migration-new@example.test",
                    UserRole.RECEPTION,
                ],
            )

        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_OLD)
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_reverse_migration_rejects_loss_of_closed_reconciliation_metadata() -> None:
    actor = User.objects.create_user(
        email="migration-closed@example.test",
        password=None,
        role=UserRole.RECEPTION,
    )
    shift = CashShift.objects.create(employee=actor)
    close_cash_shift(
        actor=actor,
        shift_id=shift.pk,
        correlation_id="migration-reverse-gate",
        idempotency_key="migration-close",
        data={
            "actual_cash_minor": 0,
            "expected_operations_count": 0,
            "cash_count_confirmed": True,
            "comment": "",
        },
    )

    try:
        executor = MigrationExecutor(connection)
        with pytest.raises(RuntimeError, match="Cannot reverse billing.0008"):
            executor.migrate(MIGRATION_OLD)

        applied = MigrationExecutor(connection).loader.applied_migrations
        assert ("billing", "0008_cash_drawer_contract") in applied
        assert ("billing", "0009_pricing_expand") not in applied
        assert ("billing", "0010_pricing_contract") not in applied
    finally:
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_forward_preflight_rejects_legacy_closed_shift_without_inventing_metadata() -> None:
    actor = User.objects.create_user(
        email="migration-legacy-closed@example.test",
        password=None,
        role=UserRole.RECEPTION,
    )
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_OLD)
    old_apps = executor.loader.project_state(MIGRATION_OLD).apps
    LegacyCashShift = old_apps.get_model("billing", "CashShift")
    shift_id = uuid4()
    LegacyCashShift.objects.create(
        id=shift_id,
        public_number=f"CSH-{shift_id.hex[:12].upper()}",
        employee_id=actor.pk,
        status="CLOSED",
        closed_at=timezone.now(),
        expected_cash_at_close_minor=0,
        actual_cash_at_close_minor=0,
        discrepancy_minor=0,
        close_comment="",
    )
    try:
        executor = MigrationExecutor(connection)
        with pytest.raises(RuntimeError, match="Cannot install TP-704"):
            executor.migrate(MIGRATION_NEW)
        assert ("billing", "0005_cash_shift_close_history") not in (
            MigrationExecutor(connection).loader.applied_migrations
        )
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "DROP TRIGGER IF EXISTS billing_cash_shift_lifecycle ON billing_cashshift"
            )
            cursor.execute("DELETE FROM billing_cashshift WHERE id = %s", [shift_id])
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)
