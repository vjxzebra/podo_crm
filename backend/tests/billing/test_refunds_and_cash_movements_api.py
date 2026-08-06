from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import DatabaseError, close_old_connections, connections, transaction
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.billing.models import (
    CashAdjustment,
    CashLedgerEntry,
    CashLedgerEntryKind,
    CashShift,
    ImmutableCashAdjustmentError,
    ImmutableRefundError,
    Payment,
    PaymentMethod,
    ReceivableStatus,
    Refund,
)
from apps.billing.services import _payload_hash
from tests.billing.test_payments_api import completed_receivable
from tests.billing.test_payments_api import post_payment as post_full_payment


def create_user(*, email: str, role: str = UserRole.RECEPTION) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=role,
        first_name="Марина",
        last_name="Коваль",
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def post_refund(
    client: APIClient,
    payment_id: str,
    *,
    key: str = "refund-key-1",
    reason: str = "Помилково проведена оплата",
    **extra: object,
):
    return client.post(
        f"/api/v1/payments/{payment_id}/refunds",
        {"reason": reason, **extra},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_REQUEST_ID="tp703-refund",
    )


def post_movement(
    client: APIClient,
    *,
    movement_type: str,
    amount_minor: int,
    key: str = "cash-key-1",
    reason: str = "Службова потреба",
    comment: str = "",
    **extra: object,
):
    return client.post(
        "/api/v1/cash-movements",
        {
            "type": movement_type,
            "amount_minor": amount_minor,
            "reason": reason,
            "comment": comment,
            **extra,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_REQUEST_ID="tp703-cash",
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("payment_method", "expected_cash"),
    [
        (PaymentMethod.CASH, 0),
        (PaymentMethod.CARD, 0),
        (PaymentMethod.TRANSFER, 0),
    ],
)
def test_full_refund_inherits_server_facts_links_projection_and_audit(
    payment_method: str,
    expected_cash: int,
) -> None:
    actor = create_user(email=f"refund-{payment_method.lower()}@example.test")
    shift = CashShift.objects.create(employee=actor)
    receivable = completed_receivable(index=1)
    client = authenticated_client(actor)
    paid = post_full_payment(
        client,
        receivable,
        key=f"pay-{payment_method}",
        payment_method=payment_method,
    )
    payment = paid.json()["operation"]["payment"]

    response = post_refund(
        client,
        payment["id"],
        key=f"refund-{payment_method}",
        reason="  Помилково проведена оплата  ",
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["replayed"] is False
    operation = body["operation"]
    assert set(operation) == {
        "id",
        "type",
        "status",
        "occurred_at",
        "amount_minor",
        "patient",
        "visit",
        "original_payment",
        "refund",
    }
    assert operation["type"] == "REFUND"
    assert operation["status"] == "POSTED"
    assert operation["amount_minor"] == receivable.amount_minor
    assert operation["original_payment"]["id"] == payment["id"]
    assert operation["original_payment"]["payment_method"] == payment_method
    assert operation["refund"]["reason"] == "Помилково проведена оплата"
    assert operation["refund"]["cash_shift"]["id"] == str(shift.pk)
    assert operation["refund"]["actor"] == {
        "id": actor.pk,
        "name": actor.display_name,
    }

    receivable.refresh_from_db()
    assert receivable.status == ReceivableStatus.REFUNDED
    refund = Refund.objects.select_related("ledger_entry").get()
    assert str(refund.original_payment_id) == payment["id"]
    assert refund.ledger_entry.amount_minor == receivable.amount_minor
    assert refund.ledger_entry.payment_method == payment_method
    assert (
        AuditEvent.objects.filter(
            action=AuditAction.REFUND_POSTED,
            object_id=str(refund.pk),
        ).count()
        == 1
    )

    listing = client.get("/api/v1/finance/operations").json()["operations"]
    assert [item["type"] for item in listing] == ["REFUND", "PAYMENT"]
    payment_row = next(item for item in listing if item["type"] == "PAYMENT")
    assert payment_row["status"] == "REFUNDED"
    assert payment_row["refund"] == operation["refund"]
    assert (
        client.get("/api/v1/cash-shifts/current").json()["shift"]["totals"]["expected_cash_minor"]
        == expected_cash
    )


@pytest.mark.django_db(transaction=True)
def test_refund_can_reverse_historical_other_actor_payment_into_own_shift() -> None:
    original_actor = create_user(email="original@example.test")
    CashShift.objects.create(employee=original_actor)
    receivable = completed_receivable(index=2)
    paid = post_full_payment(
        authenticated_client(original_actor),
        receivable,
        key="historical-payment",
        payment_method=PaymentMethod.CARD,
    )
    payment = paid.json()["operation"]["payment"]
    original_shift = CashShift.objects.get(employee=original_actor)
    original_shift.status = "CLOSED"
    original_shift.closed_at = timezone.now()
    original_shift.expected_cash_at_close_minor = 0
    original_shift.actual_cash_at_close_minor = 0
    original_shift.discrepancy_minor = 0
    original_shift.closed_by = original_actor
    original_shift.closed_by_name_snapshot = original_actor.display_name
    original_shift.closed_by_email_snapshot = original_actor.email
    original_shift.closed_by_role_snapshot = original_actor.role
    original_shift.close_idempotency_key = "historical-close"
    original_shift.close_payload_hash = "a" * 64
    original_shift.save()
    refund_actor = create_user(email="refund-actor@example.test", role=UserRole.ADMIN)
    refund_client = authenticated_client(refund_actor)
    opened = refund_client.post("/api/v1/cash-shifts", format="json")
    assert opened.status_code == 201, opened.json()
    refund_shift = CashShift.objects.get(pk=opened.json()["id"])

    response = post_refund(
        refund_client,
        payment["id"],
        key="historical-refund",
    )

    assert response.status_code == 201, response.json()
    operation = response.json()["operation"]
    assert operation["original_payment"]["actor"]["id"] == original_actor.pk
    assert operation["refund"]["actor"]["id"] == refund_actor.pk
    assert operation["refund"]["cash_shift"]["id"] == str(refund_shift.pk)


@pytest.mark.django_db(transaction=True)
def test_cash_refund_requires_current_shift_cash_and_rolls_back_cleanly() -> None:
    original_actor = create_user(email="cash-original@example.test")
    CashShift.objects.create(employee=original_actor)
    receivable = completed_receivable(index=3)
    paid = post_full_payment(
        authenticated_client(original_actor),
        receivable,
        key="cash-original-payment",
        payment_method=PaymentMethod.CASH,
    )
    original_shift = CashShift.objects.get(employee=original_actor)
    closed = authenticated_client(original_actor).post(
        f"/api/v1/cash-shifts/{original_shift.pk}/close",
        {
            "actual_cash_minor": 0,
            "expected_operations_count": 1,
            "cash_count_confirmed": True,
            "comment": "Готівку вилучено перед передачею каси",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="cash-original-close",
    )
    assert closed.status_code == 201, closed.json()
    refund_actor = create_user(email="cash-refund@example.test")
    refund_client = authenticated_client(refund_actor)
    opened = refund_client.post("/api/v1/cash-shifts", format="json")
    assert opened.status_code == 201, opened.json()
    ledger_before = CashLedgerEntry.objects.count()

    response = post_refund(
        refund_client,
        paid.json()["operation"]["payment"]["id"],
        key="insufficient-cash-refund",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_cash"
    assert Refund.objects.count() == 0
    assert CashLedgerEntry.objects.count() == ledger_before
    receivable.refresh_from_db()
    assert receivable.status == ReceivableStatus.PAID
    assert not AuditEvent.objects.filter(action=AuditAction.REFUND_POSTED).exists()


@pytest.mark.django_db(transaction=True)
def test_refund_replays_exact_key_and_rejects_mismatch_or_second_refund() -> None:
    actor = create_user(email="refund-replay@example.test")
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable(index=4)
    client = authenticated_client(actor)
    paid = post_full_payment(client, receivable, key="replay-payment")
    payment_id = paid.json()["operation"]["payment"]["id"]

    first = post_refund(client, payment_id, key="stable-refund", reason="Причина")
    replay = post_refund(client, payment_id, key="stable-refund", reason="Причина")
    mismatch = post_refund(client, payment_id, key="stable-refund", reason="Інша причина")
    second = post_refund(client, payment_id, key="new-refund", reason="Причина")

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["operation"] == first.json()["operation"]
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert second.status_code == 409
    assert second.json()["code"] == "payment_already_refunded"
    assert Refund.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_cash_deposit_withdrawal_boundary_projection_and_idempotency_family() -> None:
    actor = create_user(email="cash@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)

    deposit = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=10_000,
        key="movement-deposit",
        reason="  Розмінні кошти  ",
        comment="  Ранкова каса  ",
    )
    replay = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=10_000,
        key="movement-deposit",
        reason="Розмінні кошти",
        comment="Ранкова каса",
    )
    mismatch = post_movement(
        client,
        movement_type=CashLedgerEntryKind.WITHDRAWAL,
        amount_minor=10_000,
        key="movement-deposit",
    )
    withdrawal = post_movement(
        client,
        movement_type=CashLedgerEntryKind.WITHDRAWAL,
        amount_minor=10_000,
        key="movement-withdrawal",
        reason="Інкасація",
    )

    assert deposit.status_code == 201, deposit.json()
    assert replay.status_code == 200
    assert replay.json()["operation"] == deposit.json()["operation"]
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert withdrawal.status_code == 201, withdrawal.json()
    operation = deposit.json()["operation"]
    assert set(operation) == {
        "id",
        "type",
        "status",
        "occurred_at",
        "amount_minor",
        "cash_adjustment",
    }
    assert operation["cash_adjustment"]["reason"] == "Розмінні кошти"
    assert operation["cash_adjustment"]["comment"] == "Ранкова каса"
    assert "patient" not in operation
    assert "payment_method" not in operation
    current = client.get("/api/v1/cash-shifts/current").json()["shift"]
    assert current["id"] == str(shift.pk)
    assert current["totals"]["deposits_minor"] == 10_000
    assert current["totals"]["withdrawals_minor"] == 10_000
    assert current["totals"]["expected_cash_minor"] == 0
    assert CashAdjustment.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_cash_movement_strict_schema_shift_cash_and_role_guards() -> None:
    actor = create_user(email="cash-guards@example.test")
    client = authenticated_client(actor)
    no_shift = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=100,
        key="no-shift",
    )
    CashShift.objects.create(employee=actor)
    unknown = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=100,
        key="unknown-field",
        patient_id="not-allowed",
    )
    oversized = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=9_007_199_254_740_992,
        key="oversized",
    )
    insufficient = post_movement(
        client,
        movement_type=CashLedgerEntryKind.WITHDRAWAL,
        amount_minor=1,
        key="insufficient",
    )
    podologist = create_user(email="cash-podologist@example.test", role=UserRole.PODOLOGIST)
    forbidden = post_movement(
        authenticated_client(podologist),
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=1,
        key="forbidden",
    )

    assert no_shift.status_code == 409
    assert no_shift.json()["code"] == "cash_shift_required"
    assert unknown.status_code == 422
    assert "patient_id" in unknown.json()["fields"]
    assert oversized.status_code == 422
    assert insufficient.status_code == 409
    assert insufficient.json()["code"] == "insufficient_cash"
    assert forbidden.status_code == 403
    assert CashAdjustment.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_refund_contract_rejects_client_financial_fields_and_validates_picker_filters() -> None:
    actor = create_user(email="refund-contract@example.test")
    CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    receivable = completed_receivable(index=5)
    paid = post_full_payment(client, receivable, key="contract-payment")
    payment_id = paid.json()["operation"]["payment"]["id"]

    unknown = post_refund(
        client,
        payment_id,
        key="unknown-refund",
        amount_minor=1,
        payment_method="CARD",
    )
    invalid_picker = client.get(
        "/api/v1/finance/operations",
        {"refundable_only": "true", "type": "REFUND"},
    )
    picker = client.get(
        "/api/v1/finance/operations",
        {
            "type": "PAYMENT",
            "status": "PAID",
            "refundable_only": "true",
            "amount_minor": receivable.amount_minor,
        },
    )

    assert unknown.status_code == 422
    assert set(unknown.json()["fields"]) == {"amount_minor", "payment_method"}
    assert invalid_picker.status_code == 422
    assert [item["id"] for item in picker.json()["operations"]] == [str(receivable.pk)]
    assert Refund.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_finance_union_filters_and_keyset_cursor_cover_all_tagged_variants() -> None:
    actor = create_user(email="union@example.test")
    CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    receivable = completed_receivable(index=6)
    paid = post_full_payment(client, receivable, key="union-payment")
    post_refund(
        client,
        paid.json()["operation"]["payment"]["id"],
        key="union-refund",
        reason="Повернення для пошуку",
    )
    post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=321,
        key="union-deposit",
        reason="Резерв для пошуку",
    )
    post_movement(
        client,
        movement_type=CashLedgerEntryKind.WITHDRAWAL,
        amount_minor=123,
        key="union-withdrawal",
        reason="Інкасація для пошуку",
    )

    assert [
        row["type"]
        for row in client.get("/api/v1/finance/operations", {"type": "REFUND"}).json()["operations"]
    ] == ["REFUND"]
    assert [
        row["type"]
        for row in client.get("/api/v1/finance/operations", {"search": "Резерв для пошуку"}).json()[
            "operations"
        ]
    ] == ["DEPOSIT"]
    assert [
        row["type"]
        for row in client.get("/api/v1/finance/operations", {"amount_minor": 123}).json()[
            "operations"
        ]
    ] == ["WITHDRAWAL"]

    with patch("apps.billing.services._FINANCE_PAGE_SIZE", 2):
        first = client.get("/api/v1/finance/operations").json()
        second = client.get("/api/v1/finance/operations", {"cursor": first["next_cursor"]}).json()
    rows = [*first["operations"], *second["operations"]]
    assert len(first["operations"]) == 2
    assert len(rows) == 4
    assert len({(row["type"], row["id"]) for row in rows}) == 4
    invalid = client.get("/api/v1/finance/operations", {"cursor": "tampered"})
    assert invalid.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_refund_and_cash_movement_roll_back_when_audit_write_fails() -> None:
    actor = create_user(email="audit-rollback@example.test")
    CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    receivable = completed_receivable(index=7)
    paid = post_full_payment(client, receivable, key="rollback-payment")
    ledger_before = CashLedgerEntry.objects.count()

    with patch("apps.billing.services.record_audit_event", side_effect=RuntimeError("audit")):
        refund = post_refund(
            client,
            paid.json()["operation"]["payment"]["id"],
            key="rollback-refund",
        )
        movement = post_movement(
            client,
            movement_type=CashLedgerEntryKind.DEPOSIT,
            amount_minor=100,
            key="rollback-movement",
        )

    assert refund.status_code == 500
    assert movement.status_code == 500
    assert Refund.objects.count() == 0
    assert CashAdjustment.objects.count() == 0
    assert CashLedgerEntry.objects.count() == ledger_before
    receivable.refresh_from_db()
    assert receivable.status == ReceivableStatus.PAID


@pytest.mark.django_db(transaction=True)
def test_concurrent_refunds_and_outgoing_cash_allow_only_one_safe_result() -> None:
    actor = create_user(email="concurrent-refund@example.test")
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable(index=8)
    paid = post_full_payment(
        authenticated_client(actor),
        receivable,
        key="concurrent-payment",
    )
    payment_id = paid.json()["operation"]["payment"]["id"]
    barrier = Barrier(2)

    def refund_worker(key: str) -> tuple[int, str]:
        close_old_connections()
        worker_actor = User.objects.get(pk=actor.pk)
        barrier.wait()
        response = post_refund(authenticated_client(worker_actor), payment_id, key=key)
        connections.close_all()
        return response.status_code, response.json().get("code", "ok")

    with ThreadPoolExecutor(max_workers=2) as pool:
        refund_results = list(pool.map(refund_worker, ("refund-a", "refund-b")))

    assert sorted(code for code, _ in refund_results) == [201, 409]
    assert {value for _, value in refund_results} == {"ok", "payment_already_refunded"}
    assert Refund.objects.count() == 1

    actor_shift = CashShift.objects.get(employee=actor)
    closed = authenticated_client(actor).post(
        f"/api/v1/cash-shifts/{actor_shift.pk}/close",
        {
            "actual_cash_minor": 0,
            "expected_operations_count": 2,
            "cash_count_confirmed": True,
            "comment": "",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="concurrent-refund-close",
    )
    assert closed.status_code == 201, closed.json()

    cash_actor = create_user(email="concurrent-cash@example.test")
    cash_client = authenticated_client(cash_actor)
    opened = cash_client.post("/api/v1/cash-shifts", format="json")
    assert opened.status_code == 201, opened.json()
    deposit = post_movement(
        cash_client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=100,
        key="concurrent-deposit",
    )
    assert deposit.status_code == 201
    cash_barrier = Barrier(2)

    def withdrawal_worker(key: str) -> tuple[int, str]:
        close_old_connections()
        worker_actor = User.objects.get(pk=cash_actor.pk)
        cash_barrier.wait()
        response = post_movement(
            authenticated_client(worker_actor),
            movement_type=CashLedgerEntryKind.WITHDRAWAL,
            amount_minor=75,
            key=key,
        )
        connections.close_all()
        return response.status_code, response.json().get("code", "ok")

    with ThreadPoolExecutor(max_workers=2) as pool:
        withdrawal_results = list(pool.map(withdrawal_worker, ("withdraw-a", "withdraw-b")))

    assert sorted(code for code, _ in withdrawal_results) == [201, 409]
    assert {value for _, value in withdrawal_results} == {"ok", "insufficient_cash"}


@pytest.mark.django_db(transaction=True)
def test_refund_and_cash_adjustment_model_and_database_guards_are_append_only() -> None:
    actor = create_user(email="raw-guards@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    receivable = completed_receivable(index=9)
    paid = post_full_payment(client, receivable, key="raw-payment")
    refunded = post_refund(
        client,
        paid.json()["operation"]["payment"]["id"],
        key="raw-refund",
    )
    deposited = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=100,
        key="raw-deposit",
    )
    assert refunded.status_code == deposited.status_code == 201
    refund = Refund.objects.get()
    adjustment = CashAdjustment.objects.get()

    refund.reason = "Зміна"
    with pytest.raises(ImmutableRefundError):
        refund.save()
    with pytest.raises(ImmutableRefundError):
        Refund.objects.filter(pk=refund.pk).update(reason="Зміна")
    adjustment.comment = "Зміна"
    with pytest.raises(ImmutableCashAdjustmentError):
        adjustment.save()
    with pytest.raises(ImmutableCashAdjustmentError):
        CashAdjustment.objects.filter(pk=adjustment.pk).update(comment="Зміна")
    with (
        pytest.raises(DatabaseError),
        transaction.atomic(),
        connections["default"].cursor() as cursor,
    ):
        cursor.execute("DELETE FROM billing_refund WHERE id = %s", [refund.pk])
    with (
        pytest.raises(DatabaseError),
        transaction.atomic(),
        connections["default"].cursor() as cursor,
    ):
        cursor.execute("DELETE FROM billing_cashadjustment WHERE id = %s", [adjustment.pk])

    with pytest.raises(DatabaseError), transaction.atomic():
        CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=CashLedgerEntryKind.DEPOSIT,
            amount_minor=1,
            payment_method="",
            idempotency_key="orphan-deposit",
            payload_hash="f" * 64,
        )


@pytest.mark.django_db(transaction=True)
def test_raw_tp703_guards_reject_orphan_refund_wrong_snapshot_and_negative_cash() -> None:
    actor = create_user(email="raw-aggregate@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    receivable = completed_receivable(index=10)
    paid = post_full_payment(
        client,
        receivable,
        key="raw-aggregate-payment",
        payment_method=PaymentMethod.CARD,
    )
    payment = Payment.objects.get(pk=paid.json()["operation"]["payment"]["id"])

    with pytest.raises(DatabaseError), transaction.atomic():
        CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=CashLedgerEntryKind.REFUND,
            amount_minor=payment.ledger_entry.amount_minor,
            payment_method=PaymentMethod.CARD,
            idempotency_key="orphan-refund",
            payload_hash="a" * 64,
        )
    assert not CashLedgerEntry.objects.filter(idempotency_key="orphan-refund").exists()

    with pytest.raises(DatabaseError), transaction.atomic():
        ledger = CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=CashLedgerEntryKind.REFUND,
            amount_minor=payment.ledger_entry.amount_minor,
            payment_method=PaymentMethod.CARD,
            idempotency_key="wrong-refund-snapshot",
            payload_hash="b" * 64,
        )
        Refund.objects.bulk_create(
            [
                Refund(
                    ledger_entry=ledger,
                    original_payment=payment,
                    reason="Причина",
                    employee_name_snapshot="Неправдивий працівник",
                    employee_email_snapshot=actor.email,
                )
            ]
        )
    assert not CashLedgerEntry.objects.filter(idempotency_key="wrong-refund-snapshot").exists()

    with pytest.raises(DatabaseError), transaction.atomic():
        CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=CashLedgerEntryKind.WITHDRAWAL,
            amount_minor=1,
            payment_method="",
            idempotency_key="negative-withdrawal",
            payload_hash="c" * 64,
        )

    with (
        pytest.raises(DatabaseError),
        transaction.atomic(),
        connections["default"].cursor() as cursor,
    ):
        cursor.execute(
            "UPDATE billing_receivable SET status = 'REFUNDED' WHERE id = %s",
            [receivable.pk],
        )
    receivable.refresh_from_db()
    assert receivable.status == ReceivableStatus.PAID


@pytest.mark.django_db(transaction=True)
def test_exact_replay_survives_closed_shift_and_corrupt_untyped_key_is_conflict() -> None:
    actor = create_user(email="closed-replay@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    movement = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=100,
        key="closed-replay-key",
    )
    assert movement.status_code == 201
    shift.status = "CLOSED"
    shift.closed_at = timezone.now()
    shift.expected_cash_at_close_minor = 100
    shift.actual_cash_at_close_minor = 100
    shift.discrepancy_minor = 0
    shift.closed_by = actor
    shift.closed_by_name_snapshot = actor.display_name
    shift.closed_by_email_snapshot = actor.email
    shift.closed_by_role_snapshot = actor.role
    shift.close_idempotency_key = "closed-replay-close"
    shift.close_payload_hash = "c" * 64
    shift.save()

    replay = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=100,
        key="closed-replay-key",
    )
    assert replay.status_code == 200
    assert replay.json()["operation"] == movement.json()["operation"]

    other = create_user(email="corrupt-key@example.test")
    other_client = authenticated_client(other)
    opened = other_client.post("/api/v1/cash-shifts", format="json")
    assert opened.status_code == 201, opened.json()
    other_shift = CashShift.objects.get(pk=opened.json()["id"])
    with transaction.atomic():
        CashLedgerEntry.objects.create(
            cash_shift=other_shift,
            created_by=other,
            kind=CashLedgerEntryKind.DEPOSIT,
            amount_minor=1,
            payment_method="",
            idempotency_key="corrupt-key",
            payload_hash=_payload_hash(
                {
                    "type": "DEPOSIT",
                    "amount_minor": 1,
                    "reason": "Службова потреба",
                    "comment": "",
                }
            ),
        )
        conflict = post_movement(
            other_client,
            movement_type=CashLedgerEntryKind.DEPOSIT,
            amount_minor=1,
            key="corrupt-key",
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "idempotency_key_conflict"
        transaction.set_rollback(True)


@pytest.mark.django_db(transaction=True)
def test_refund_and_adjustment_actor_snapshots_survive_user_rename() -> None:
    actor = create_user(email="snapshot-actor@example.test")
    CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    receivable = completed_receivable(index=11)
    paid = post_full_payment(client, receivable, key="snapshot-payment")
    refunded = post_refund(
        client,
        paid.json()["operation"]["payment"]["id"],
        key="snapshot-refund",
    )
    movement = post_movement(
        client,
        movement_type=CashLedgerEntryKind.DEPOSIT,
        amount_minor=50,
        key="snapshot-deposit",
    )
    assert refunded.status_code == movement.status_code == 201
    original_name = actor.display_name
    actor.first_name = "Змінена"
    actor.last_name = "Особа"
    actor.email = "renamed-snapshot@example.test"
    actor.save()

    listing = authenticated_client(actor).get("/api/v1/finance/operations").json()["operations"]
    refund_row = next(row for row in listing if row["type"] == "REFUND")
    deposit_row = next(row for row in listing if row["type"] == "DEPOSIT")
    assert refund_row["refund"]["actor"]["name"] == original_name
    assert deposit_row["cash_adjustment"]["actor"]["name"] == original_name


@pytest.mark.django_db(transaction=True)
def test_concurrent_cash_refund_and_withdrawal_share_one_physical_cash_guard() -> None:
    actor = create_user(email="mixed-race@example.test")
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable(amount_minor=100, index=12)
    paid = post_full_payment(
        authenticated_client(actor),
        receivable,
        key="mixed-race-payment",
        payment_method=PaymentMethod.CASH,
    )
    payment_id = paid.json()["operation"]["payment"]["id"]
    barrier = Barrier(2)

    def refund_worker() -> tuple[int, str]:
        close_old_connections()
        worker = User.objects.get(pk=actor.pk)
        barrier.wait()
        response = post_refund(
            authenticated_client(worker),
            payment_id,
            key="mixed-race-refund",
        )
        connections.close_all()
        return response.status_code, response.json().get("code", "ok")

    def withdrawal_worker() -> tuple[int, str]:
        close_old_connections()
        worker = User.objects.get(pk=actor.pk)
        barrier.wait()
        response = post_movement(
            authenticated_client(worker),
            movement_type=CashLedgerEntryKind.WITHDRAWAL,
            amount_minor=75,
            key="mixed-race-withdrawal",
        )
        connections.close_all()
        return response.status_code, response.json().get("code", "ok")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(refund_worker), pool.submit(withdrawal_worker)]
        outcomes = [future.result() for future in results]

    assert sorted(code for code, _ in outcomes) == [201, 409]
    assert {value for _, value in outcomes} == {"ok", "insufficient_cash"}


@pytest.mark.django_db(transaction=True)
def test_tp703_openapi_freezes_strict_mutations_and_tagged_union() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    components = schema["components"]["schemas"]
    refund_operation = paths["/api/v1/payments/{payment_id}/refunds"]["post"]
    movement_operation = paths["/api/v1/cash-movements"]["post"]

    assert refund_operation["operationId"] == "refund_create"
    assert movement_operation["operationId"] == "cash_movement_create"
    for operation in (refund_operation, movement_operation):
        header = next(
            parameter
            for parameter in operation["parameters"]
            if parameter["name"] == "Idempotency-Key"
        )
        assert header["required"] is True
        assert header["schema"] == {
            "type": "string",
            "minLength": 1,
            "maxLength": 128,
        }
    assert components["RefundCreateRequest"]["additionalProperties"] is False
    assert set(components["RefundCreateRequest"]["properties"]) == {"reason"}
    assert components["RefundCreateRequest"]["required"] == ["reason"]
    assert components["CashMovementCreateRequest"]["additionalProperties"] is False
    assert set(components["CashMovementCreateRequest"]["properties"]) == {
        "type",
        "amount_minor",
        "reason",
        "comment",
    }
    assert "patient_id" not in components["CashMovementCreateRequest"]["properties"]
    assert "payment_method" not in components["CashMovementCreateRequest"]["properties"]
    assert components["CashMovementCreateRequest"]["properties"]["amount_minor"] == {
        "type": "integer",
        "maximum": 9_007_199_254_740_991,
        "minimum": 1,
        "format": "int64",
    }
    union = components["FinanceOperation"]
    assert union["discriminator"]["propertyName"] == "type"
    assert set(union["discriminator"]["mapping"]) == {
        "PAYMENT",
        "REFUND",
        "DEPOSIT",
        "WITHDRAWAL",
    }
    assert {item["$ref"] for item in union["oneOf"]} == {
        "#/components/schemas/FinancePaymentOperation",
        "#/components/schemas/FinanceRefundOperation",
        "#/components/schemas/FinanceCashAdjustmentOperation",
    }
    assert "refund" in components["FinancePaymentOperation"]["required"]
    assert components["FinancePaymentOperation"]["properties"]["refund"]["nullable"] is True
    assert "original_payment" in components["FinanceRefundOperation"]["required"]
    assert "cash_adjustment" in components["FinanceCashAdjustmentOperation"]["required"]
