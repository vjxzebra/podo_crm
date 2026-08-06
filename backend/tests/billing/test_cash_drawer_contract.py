from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.accounts.models import User, UserRole
from apps.billing.models import CashShift, CashShiftOpeningBasis
from apps.billing.services import close_cash_shift, open_cash_shift

MIGRATION_BEFORE_DRAWER = [("billing", "0006_global_search_indexes")]
MIGRATION_EXPANDED = [("billing", "0007_cash_drawer_expand")]
MIGRATION_CONTRACTED = [("billing", "0008_cash_drawer_contract")]
MIGRATION_LATEST = [("billing", "0010_pricing_contract")]


def create_user(email: str) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=UserRole.RECEPTION,
        first_name="Касир",
        last_name="Тестовий",
    )


def legacy_shift(OldCashShift, actor: User):
    shift_id = uuid4()
    return OldCashShift.objects.create(
        id=shift_id,
        public_number=f"CSH-{shift_id.hex[:12].upper()}",
        employee_id=actor.pk,
        employee_name_snapshot=actor.display_name,
        employee_email_snapshot=actor.email,
        employee_role_snapshot=actor.role,
        status="OPEN",
    )


@pytest.mark.django_db(transaction=True)
def test_expand_backfills_one_legacy_open_shift_without_rewriting_cash_history() -> None:
    actor = create_user("legacy-drawer@example.test")
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_BEFORE_DRAWER)
    try:
        old_apps = executor.loader.project_state(MIGRATION_BEFORE_DRAWER).apps
        old_shift = legacy_shift(old_apps.get_model("billing", "CashShift"), actor)

        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_EXPANDED)
        expanded_apps = executor.loader.project_state(MIGRATION_EXPANDED).apps
        expanded = expanded_apps.get_model("billing", "CashShift").objects.get(pk=old_shift.pk)
        assert expanded.drawer_id == "main"
        assert expanded.opening_cash_minor == 0
        assert expanded.opening_basis == "LEGACY"
        assert expanded.opening_source_shift_id is None
        assert expanded.status == "OPEN"
        assert expanded.expected_cash_at_close_minor is None

        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_CONTRACTED)
        contracted_apps = executor.loader.project_state(MIGRATION_CONTRACTED).apps
        contracted = contracted_apps.get_model("billing", "CashShift").objects.get(pk=old_shift.pk)
        assert contracted.drawer_id == "main"
        assert contracted.opening_basis == "LEGACY"
    finally:
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_expand_preflight_rejects_multiple_open_shifts_without_choosing_an_owner() -> None:
    actors = [create_user(f"legacy-open-{index}@example.test") for index in range(2)]
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_BEFORE_DRAWER)
    old_apps = executor.loader.project_state(MIGRATION_BEFORE_DRAWER).apps
    OldCashShift = old_apps.get_model("billing", "CashShift")
    shift_ids = [legacy_shift(OldCashShift, actor).pk for actor in actors]
    try:
        with pytest.raises(RuntimeError, match="more than one OPEN cash shift"):
            MigrationExecutor(connection).migrate(MIGRATION_EXPANDED)
        assert ("billing", "0007_cash_drawer_expand") not in (
            MigrationExecutor(connection).loader.applied_migrations
        )
        assert set(OldCashShift.objects.values_list("pk", flat=True)) >= set(shift_ids)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER TABLE billing_cashshift DISABLE TRIGGER billing_cash_shift_lifecycle"
            )
            cursor.execute("DELETE FROM billing_cashshift WHERE id = ANY(%s)", [shift_ids])
            cursor.execute(
                "ALTER TABLE billing_cashshift ENABLE TRIGGER billing_cash_shift_lifecycle"
            )
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_database_guards_reject_forged_opening_modes_mutation_and_source_reuse() -> None:
    first_owner = create_user("raw-first@example.test")
    second_owner = create_user("raw-second@example.test")
    third_owner = create_user("raw-third@example.test")
    first = open_cash_shift(actor=first_owner, correlation_id="raw-first-open")
    close_cash_shift(
        actor=first_owner,
        shift_id=first.pk,
        correlation_id="raw-first-close",
        idempotency_key="raw-first-close",
        data={
            "actual_cash_minor": 700,
            "expected_operations_count": 0,
            "cash_count_confirmed": True,
            "comment": "Фактичний залишок",
        },
    )
    second = open_cash_shift(actor=second_owner, correlation_id="raw-second-open")
    assert second.opening_source_shift_id == first.pk
    close_cash_shift(
        actor=second_owner,
        shift_id=second.pk,
        correlation_id="raw-second-close",
        idempotency_key="raw-second-close",
        data={
            "actual_cash_minor": 700,
            "expected_operations_count": 0,
            "cash_count_confirmed": True,
            "comment": "",
        },
    )

    def raw_insert(*, basis: str, opening: int, source_id=None) -> None:
        shift_id = uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO billing_cashshift (
                    id, public_number, employee_id,
                    employee_name_snapshot, employee_email_snapshot,
                    employee_role_snapshot, drawer_key, opening_cash_minor,
                    opening_source_shift_id, opening_basis, status, opened_at,
                    closed_at, expected_cash_at_close_minor,
                    actual_cash_at_close_minor, discrepancy_minor, close_comment,
                    closed_by_id, closed_by_name_snapshot, closed_by_email_snapshot,
                    closed_by_role_snapshot, close_idempotency_key, close_payload_hash
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, 'main', %s, %s, %s, 'OPEN', NOW(),
                    NULL, NULL, NULL, NULL, '', NULL, '', '', '', '', ''
                )
                """,
                [
                    shift_id,
                    f"CSH-{shift_id.hex[:12].upper()}",
                    third_owner.pk,
                    third_owner.display_name,
                    third_owner.email,
                    third_owner.role,
                    opening,
                    source_id,
                    basis,
                ],
            )

    with pytest.raises(DatabaseError), transaction.atomic():
        raw_insert(basis=CashShiftOpeningBasis.LEGACY, opening=0)
    with pytest.raises(DatabaseError), transaction.atomic():
        raw_insert(basis=CashShiftOpeningBasis.INITIAL, opening=0)
    with pytest.raises(DatabaseError), transaction.atomic():
        raw_insert(
            basis=CashShiftOpeningBasis.CARRY_FORWARD,
            opening=700,
            source_id=first.pk,
        )

    third = open_cash_shift(actor=third_owner, correlation_id="raw-third-open")
    assert third.opening_source_shift_id == second.pk
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_cashshift SET opening_cash_minor = 0 WHERE id = %s",
            [third.pk],
        )

    assert CashShift.objects.get(pk=third.pk).opening_cash_minor == 700
    assert CashShift.objects.filter(opening_basis="LEGACY").count() == 0
