import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.billing.models import (
    CashAdjustment,
    CashLedgerEntry,
    CashLedgerEntryKind,
    CashShift,
    ImmutableCashLedgerEntryError,
    ImmutableCashShiftError,
    PaymentMethod,
)


def create_user(email: str) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=UserRole.RECEPTION,
    )


def create_entry(
    *,
    shift: CashShift,
    actor: User,
    kind: str = CashLedgerEntryKind.DEPOSIT,
    amount_minor: int = 1_000,
    payment_method: str | None = None,
    key: str = "model-entry",
) -> CashLedgerEntry:
    with transaction.atomic():
        entry = CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=kind,
            amount_minor=amount_minor,
            payment_method=payment_method,
            idempotency_key=key,
            payload_hash="a" * 64,
        )
        if kind in (CashLedgerEntryKind.DEPOSIT, CashLedgerEntryKind.WITHDRAWAL):
            CashAdjustment.objects.create(
                ledger_entry=entry,
                reason="Тестова касова операція",
                employee_name_snapshot=actor.display_name,
                employee_email_snapshot=actor.email,
            )
    return entry


@pytest.mark.django_db(transaction=True)
def test_partial_unique_allows_one_open_shift_per_employee_but_not_globally() -> None:
    first_actor = create_user("first@example.test")
    second_actor = create_user("second@example.test")
    first = CashShift.objects.create(employee=first_actor)
    second = CashShift.objects.create(employee=second_actor)

    assert first.public_number.startswith("CSH-")
    assert second.public_number.startswith("CSH-")
    with pytest.raises(IntegrityError), transaction.atomic():
        CashShift.objects.create(employee=first_actor)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("kind", "amount_minor", "payment_method"),
    [
        (CashLedgerEntryKind.PAYMENT, 0, PaymentMethod.CASH),
        (CashLedgerEntryKind.PAYMENT, 100, None),
        (CashLedgerEntryKind.REFUND, 100, None),
        (CashLedgerEntryKind.DEPOSIT, 100, PaymentMethod.CASH),
        (CashLedgerEntryKind.WITHDRAWAL, 100, PaymentMethod.CARD),
        (CashLedgerEntryKind.PAYMENT, 100, "CRYPTO"),
        ("UNKNOWN", 100, PaymentMethod.CASH),
    ],
)
def test_ledger_database_constraints_reject_zero_or_inconsistent_method(
    kind: str,
    amount_minor: int,
    payment_method: str | None,
) -> None:
    actor = create_user(f"{kind}-{amount_minor}-{payment_method}@example.test")
    shift = CashShift.objects.create(employee=actor)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_entry(
            shift=shift,
            actor=actor,
            kind=kind,
            amount_minor=amount_minor,
            payment_method=payment_method,
        )


@pytest.mark.django_db(transaction=True)
def test_cash_movement_idempotency_key_is_unique_per_actor_endpoint_family() -> None:
    actor = create_user("actor@example.test")
    other = create_user("other@example.test")
    shift = CashShift.objects.create(employee=actor)
    other_shift = CashShift.objects.create(employee=other)
    create_entry(shift=shift, actor=actor, key="same-key")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_entry(shift=shift, actor=actor, key="same-key")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_entry(
            shift=shift,
            actor=actor,
            kind=CashLedgerEntryKind.WITHDRAWAL,
            key="same-key",
        )
    other_entry = create_entry(
        shift=other_shift,
        actor=other,
        key="same-key",
    )
    assert other_entry.created_by_id == other.pk


@pytest.mark.django_db(transaction=True)
def test_ledger_entries_are_immutable_through_model_queryset_and_database_trigger() -> None:
    actor = create_user("actor@example.test")
    shift = CashShift.objects.create(employee=actor)
    entry = create_entry(shift=shift, actor=actor)

    entry.amount_minor = 2_000
    with pytest.raises(ImmutableCashLedgerEntryError):
        entry.save()
    with pytest.raises(ImmutableCashLedgerEntryError):
        entry.delete()
    with pytest.raises(ImmutableCashLedgerEntryError):
        CashLedgerEntry.objects.filter(pk=entry.pk).update(amount_minor=2_000)
    with pytest.raises(ImmutableCashLedgerEntryError):
        CashLedgerEntry.objects.filter(pk=entry.pk).delete()

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_cashledgerentry SET amount_minor = %s WHERE id = %s",
            [2_000, entry.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM billing_cashledgerentry WHERE id = %s",
            [entry.pk],
        )
    entry.refresh_from_db()
    assert entry.amount_minor == 1_000


@pytest.mark.django_db(transaction=True)
def test_shift_lifecycle_is_guarded_by_model_queryset_and_database_trigger() -> None:
    actor = create_user("actor@example.test")
    other = create_user("other@example.test")
    shift = CashShift.objects.create(employee=actor)

    shift.public_number = "CSH-CHANGED"
    with pytest.raises(ImmutableCashShiftError):
        shift.save()
    with pytest.raises(ImmutableCashShiftError):
        shift.delete()
    with pytest.raises(ImmutableCashShiftError):
        CashShift.objects.filter(pk=shift.pk).update(status="CLOSED")
    with pytest.raises(ImmutableCashShiftError):
        CashShift.objects.filter(pk=shift.pk).delete()

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_cashshift SET employee_id = %s WHERE id = %s",
            [other.pk, shift.pk],
        )

    shift.refresh_from_db()
    shift.status = "CLOSED"
    shift.closed_at = timezone.now()
    shift.expected_cash_at_close_minor = 0
    shift.actual_cash_at_close_minor = 0
    shift.discrepancy_minor = 0
    shift.closed_by = actor
    shift.closed_by_name_snapshot = actor.display_name
    shift.closed_by_email_snapshot = actor.email
    shift.closed_by_role_snapshot = actor.role
    shift.close_idempotency_key = "model-close"
    shift.close_payload_hash = "a" * 64
    shift.save()

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE billing_cashshift
            SET status = 'OPEN',
                closed_at = NULL,
                expected_cash_at_close_minor = NULL,
                actual_cash_at_close_minor = NULL,
                discrepancy_minor = NULL,
                close_comment = '',
                closed_by_id = NULL,
                closed_by_name_snapshot = '',
                closed_by_email_snapshot = '',
                closed_by_role_snapshot = '',
                close_idempotency_key = '',
                close_payload_hash = ''
            WHERE id = %s
            """,
            [shift.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM billing_cashshift WHERE id = %s", [shift.pk])

    shift.refresh_from_db()
    assert shift.status == "CLOSED"
    assert shift.employee_id == actor.pk
