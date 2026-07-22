from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
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
    CashShiftStatus,
    PaymentMethod,
    ReceivableStatus,
)
from tests.billing.test_payments_api import completed_receivable
from tests.billing.test_payments_api import post_payment as post_full_payment


def create_user(
    email: str,
    *,
    role: str = UserRole.RECEPTION,
    first_name: str = "Марина",
    last_name: str = "Коваль",
) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def post_movement(
    client: APIClient,
    *,
    amount_minor: int,
    key: str,
):
    return client.post(
        "/api/v1/cash-movements",
        {
            "type": CashLedgerEntryKind.DEPOSIT,
            "amount_minor": amount_minor,
            "reason": "Поповнення каси",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def post_close(
    client: APIClient,
    shift: CashShift,
    *,
    actual_cash_minor: int,
    expected_operations_count: int,
    key: str = "close-key",
    comment: str = "",
    confirmed: object = True,
    **extra: object,
):
    return client.post(
        f"/api/v1/cash-shifts/{shift.pk}/close",
        {
            "actual_cash_minor": actual_cash_minor,
            "expected_operations_count": expected_operations_count,
            "cash_count_confirmed": confirmed,
            "comment": comment,
            **extra,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_REQUEST_ID="tp704-close",
    )


@pytest.mark.django_db(transaction=True)
def test_close_preview_balanced_close_exact_replay_and_immutable_snapshots() -> None:
    actor = create_user("owner@example.test", first_name="Олена")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    assert post_movement(client, amount_minor=12_500, key="deposit-one").status_code == 201
    completed_receivable(amount_minor=45_000, index=704)

    preview = client.get(f"/api/v1/cash-shifts/{shift.pk}/close-preview")

    assert preview.status_code == 200
    assert preview.json()["shift"]["totals"]["operations_count"] == 1
    assert preview.json()["shift"]["totals"]["expected_cash_minor"] == 12_500
    assert preview.json()["unpaid"] == {"count": 1, "total_minor": 45_000}

    first = post_close(
        client,
        shift,
        actual_cash_minor=12_500,
        expected_operations_count=1,
        key="balanced-close",
        comment="  ",
    )
    replay = post_close(
        client,
        shift,
        actual_cash_minor=12_500,
        expected_operations_count=1,
        key="balanced-close",
    )

    assert first.status_code == 201, first.json()
    assert replay.status_code == 200, replay.json()
    assert first.json()["replayed"] is False
    assert replay.json()["replayed"] is True
    assert replay.json()["shift"] == first.json()["shift"]
    closed = first.json()["shift"]
    assert closed["status"] == CashShiftStatus.CLOSED
    assert closed["closed_at"] is not None
    assert closed["reconciliation"] == {
        "expected_cash_minor": 12_500,
        "actual_cash_minor": 12_500,
        "discrepancy_minor": 0,
        "comment": "",
        "closed_by": {
            "id": actor.pk,
            "name": "Олена Коваль",
            "email": "owner@example.test",
            "role": UserRole.RECEPTION,
        },
    }
    assert client.get("/api/v1/cash-shifts/current").json() == {"shift": None}
    assert AuditEvent.objects.filter(action=AuditAction.CASH_SHIFT_CLOSED).count() == 1
    event = AuditEvent.objects.get(action=AuditAction.CASH_SHIFT_CLOSED)
    assert event.correlation_id == "tp704-close"
    assert event.before["status"] == CashShiftStatus.OPEN
    assert event.after["status"] == CashShiftStatus.CLOSED

    mismatch = post_close(
        client,
        shift,
        actual_cash_minor=12_499,
        expected_operations_count=1,
        key="balanced-close",
        comment="Нестача",
    )
    another_key = post_close(
        client,
        shift,
        actual_cash_minor=12_500,
        expected_operations_count=1,
        key="another-close",
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert another_key.status_code == 409
    assert another_key.json()["code"] == "cash_shift_already_closed"

    actor.first_name = "Перейменована"
    actor.email = "renamed@example.test"
    actor.save(update_fields=("first_name", "email"))
    detail = client.get(f"/api/v1/cash-shifts/{shift.pk}")
    assert detail.status_code == 200
    assert detail.json()["employee"]["name"] == "Олена Коваль"
    assert detail.json()["employee"]["email"] == "owner@example.test"
    assert detail.json()["entries"][0]["actor_name"] == "Олена Коваль"
    assert detail.json()["entries"][0]["actor_email"] == "owner@example.test"
    assert detail.json()["reconciliation"]["closed_by"]["name"] == "Олена Коваль"


@pytest.mark.django_db(transaction=True)
def test_stale_revision_strict_confirmation_and_discrepancy_comment_validation() -> None:
    actor = create_user("stale@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    assert client.get(f"/api/v1/cash-shifts/{shift.pk}/close-preview").status_code == 200
    assert post_movement(client, amount_minor=2_000, key="late-deposit").status_code == 201

    stale = post_close(
        client,
        shift,
        actual_cash_minor=0,
        expected_operations_count=0,
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "cash_shift_changed"
    shift.refresh_from_db()
    assert shift.status == CashShiftStatus.OPEN
    assert shift.closed_at is None

    no_comment = post_close(
        client,
        shift,
        actual_cash_minor=0,
        expected_operations_count=1,
        comment="   ",
    )
    assert no_comment.status_code == 422
    assert no_comment.json()["code"] == "validation_error"
    assert "comment" in no_comment.json()["fields"]

    for invalid_confirmation in (False, 1, "true", None):
        invalid = post_close(
            client,
            shift,
            actual_cash_minor=0,
            expected_operations_count=1,
            confirmed=invalid_confirmation,
        )
        assert invalid.status_code == 422
        assert "cash_count_confirmed" in invalid.json()["fields"]

    unknown = post_close(
        client,
        shift,
        actual_cash_minor=0,
        expected_operations_count=1,
        expected_cash_minor=2_000,
    )
    assert unknown.status_code == 422
    assert unknown.json()["fields"] == {"expected_cash_minor": ["Невідоме поле."]}

    shortage = post_close(
        client,
        shift,
        actual_cash_minor=0,
        expected_operations_count=1,
        comment="  Перераховано повторно  ",
    )
    assert shortage.status_code == 201, shortage.json()
    assert shortage.json()["shift"]["reconciliation"]["discrepancy_minor"] == -2_000
    assert shortage.json()["shift"]["reconciliation"]["comment"] == "Перераховано повторно"


@pytest.mark.django_db(transaction=True)
def test_owner_admin_foreign_reception_and_podologist_scope_is_non_disclosing() -> None:
    owner = create_user("owner-scope@example.test")
    foreign = create_user("foreign@example.test")
    admin = create_user("admin@example.test", role=UserRole.ADMIN)
    podologist = create_user("podologist@example.test", role=UserRole.PODOLOGIST)
    shift = CashShift.objects.create(employee=owner)

    owner_client = authenticated_client(owner)
    foreign_client = authenticated_client(foreign)
    admin_client = authenticated_client(admin)
    podologist_client = authenticated_client(podologist)

    assert owner_client.get(f"/api/v1/cash-shifts/{shift.pk}").status_code == 200
    assert foreign_client.get(f"/api/v1/cash-shifts/{shift.pk}").status_code == 404
    assert foreign_client.get(f"/api/v1/cash-shifts/{shift.pk}/close-preview").status_code == 404
    assert (
        post_close(
            foreign_client,
            shift,
            actual_cash_minor=0,
            expected_operations_count=0,
        ).status_code
        == 404
    )
    assert foreign_client.get("/api/v1/cash-shifts").json()["shifts"] == []
    forbidden_filter = foreign_client.get(
        "/api/v1/cash-shifts",
        {"employee_id": owner.pk},
    )
    assert forbidden_filter.status_code == 403

    assert podologist_client.get("/api/v1/cash-shifts").status_code == 403
    assert podologist_client.get(f"/api/v1/cash-shifts/{uuid4()}").status_code == 403
    assert admin_client.get(f"/api/v1/cash-shifts/{shift.pk}/close-preview").status_code == 200
    admin_close = post_close(
        admin_client,
        shift,
        actual_cash_minor=0,
        expected_operations_count=0,
        key="admin-close",
    )
    assert admin_close.status_code == 201
    assert admin_close.json()["shift"]["reconciliation"]["closed_by"]["id"] == admin.pk
    assert owner_client.get(f"/api/v1/cash-shifts/{shift.pk}").status_code == 200
    assert admin_client.get(f"/api/v1/cash-shifts/{uuid4()}").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_history_cursor_filters_snapshot_search_and_complete_detail_entries() -> None:
    admin = create_user("history-admin@example.test", role=UserRole.ADMIN)
    shifts: list[CashShift] = []
    for index in range(41):
        employee = create_user(
            f"history-{index:02d}@example.test",
            first_name=f"Працівник{index:02d}",
        )
        shifts.append(CashShift.objects.create(employee=employee))

    client = authenticated_client(admin)
    first = client.get("/api/v1/cash-shifts")
    assert first.status_code == 200
    assert len(first.json()["shifts"]) == 40
    assert first.json()["next_cursor"]
    second = client.get(
        "/api/v1/cash-shifts",
        {"cursor": first.json()["next_cursor"]},
    )
    assert second.status_code == 200
    assert len(second.json()["shifts"]) == 1
    assert second.json()["next_cursor"] is None
    first_ids = {item["id"] for item in first.json()["shifts"]}
    second_ids = {item["id"] for item in second.json()["shifts"]}
    assert not first_ids & second_ids
    assert first_ids | second_ids == {str(shift.pk) for shift in shifts}

    target = shifts[7]
    target.employee.first_name = "Нове ім’я"
    target.employee.email = "new-history@example.test"
    target.employee.save(update_fields=("first_name", "email"))
    by_employee = client.get("/api/v1/cash-shifts", {"employee_id": target.employee_id})
    by_search = client.get("/api/v1/cash-shifts", {"search": "Працівник07"})
    today = timezone.localdate()
    by_date = client.get(
        "/api/v1/cash-shifts",
        {"date_from": today.isoformat(), "date_to": today.isoformat()},
    )
    tomorrow = client.get(
        "/api/v1/cash-shifts",
        {"date_from": (today + timedelta(days=1)).isoformat()},
    )
    assert [item["id"] for item in by_employee.json()["shifts"]] == [str(target.pk)]
    assert [item["id"] for item in by_search.json()["shifts"]] == [str(target.pk)]
    assert by_search.json()["shifts"][0]["employee"]["email"] == "history-07@example.test"
    assert len(by_date.json()["shifts"]) == 40
    assert tomorrow.json()["shifts"] == []

    detail_actor = create_user("detail-owner@example.test")
    detail_shift = CashShift.objects.create(employee=detail_actor)
    with transaction.atomic():
        for index in range(45):
            entry = CashLedgerEntry.objects.create(
                cash_shift=detail_shift,
                created_by=detail_actor,
                kind=CashLedgerEntryKind.DEPOSIT,
                amount_minor=index + 1,
                payment_method="",
                idempotency_key=f"complete-{index}",
                payload_hash=f"{index:064x}",
            )
            CashAdjustment.objects.create(
                ledger_entry=entry,
                reason="Повнота detail",
                employee_name_snapshot=detail_actor.display_name,
                employee_email_snapshot=detail_actor.email,
            )
    detail = authenticated_client(detail_actor).get(f"/api/v1/cash-shifts/{detail_shift.pk}")
    assert detail.status_code == 200
    assert len(detail.json()["entries"]) == 45
    assert detail.json()["totals"]["operations_count"] == 45
    assert detail.json()["totals"]["expected_cash_minor"] == sum(range(1, 46))


@pytest.mark.django_db(transaction=True)
def test_history_status_validation_cursor_and_europe_kyiv_date_boundary() -> None:
    admin = create_user("boundary-admin@example.test", role=UserRole.ADMIN)
    first_actor = create_user("boundary-first@example.test")
    second_actor = create_user("boundary-second@example.test")

    def raw_open(actor: User, opened_at: str) -> CashShift:
        shift_id = uuid4()
        with connection.cursor() as cursor:
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
                    %s, %s, %s, %s, %s, %s, 'OPEN', %s,
                    NULL, NULL, NULL, NULL, '', NULL, '', '', '', '', ''
                )
                """,
                [
                    shift_id,
                    f"CSH-{shift_id.hex[:12].upper()}",
                    actor.pk,
                    actor.display_name,
                    actor.email,
                    actor.role,
                    opened_at,
                ],
            )
        return CashShift.objects.get(pk=shift_id)

    local_july_22 = raw_open(first_actor, "2026-07-21T21:30:00+00:00")
    local_july_23 = raw_open(second_actor, "2026-07-22T21:30:00+00:00")
    close_cash = post_close(
        authenticated_client(first_actor),
        local_july_22,
        actual_cash_minor=0,
        expected_operations_count=0,
        key="boundary-close",
    )
    assert close_cash.status_code == 201

    client = authenticated_client(admin)
    july_22 = client.get(
        "/api/v1/cash-shifts",
        {"date_from": "2026-07-22", "date_to": "2026-07-22"},
    )
    assert july_22.status_code == 200
    assert [item["id"] for item in july_22.json()["shifts"]] == [str(local_july_22.pk)]
    assert client.get("/api/v1/cash-shifts", {"status": CashShiftStatus.CLOSED}).json()["shifts"][
        0
    ]["id"] == str(local_july_22.pk)
    assert client.get("/api/v1/cash-shifts", {"status": CashShiftStatus.OPEN}).json()["shifts"][0][
        "id"
    ] == str(local_july_23.pk)

    reverse = client.get(
        "/api/v1/cash-shifts",
        {"date_from": "2026-07-23", "date_to": "2026-07-22"},
    )
    bad_cursor = client.get("/api/v1/cash-shifts", {"cursor": "not-a-cursor"})
    assert reverse.status_code == 422
    assert "date_to" in reverse.json()["fields"]
    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["code"] == "validation_error"
    assert "cursor" in bad_cursor.json()["fields"]


@pytest.mark.django_db(transaction=True)
def test_database_close_formula_trimmed_comment_snapshots_and_closed_insert_guards() -> None:
    actor = create_user("database-close@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    assert post_movement(client, amount_minor=500, key="db-deposit").status_code == 201

    close_sql = """
        UPDATE billing_cashshift
           SET status = 'CLOSED',
               closed_at = NOW(),
               expected_cash_at_close_minor = %s,
               actual_cash_at_close_minor = %s,
               discrepancy_minor = %s,
               close_comment = %s,
               closed_by_id = %s,
               closed_by_name_snapshot = %s,
               closed_by_email_snapshot = %s,
               closed_by_role_snapshot = %s,
               close_idempotency_key = %s,
               close_payload_hash = %s
         WHERE id = %s
    """
    common = [
        actor.pk,
        actor.display_name,
        actor.email,
        actor.role,
        "raw-close",
        "a" * 64,
        shift.pk,
    ]
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(close_sql, [499, 499, 0, "", *common])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(close_sql, [500, 499, 0, "Нестача", *common])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(close_sql, [500, 499, -1, "   ", *common])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_cashshift SET employee_name_snapshot = %s WHERE id = %s",
            ["Підміна", shift.pk],
        )

    closed = post_close(
        client,
        shift,
        actual_cash_minor=499,
        expected_operations_count=1,
        comment="Нестача після перерахунку",
    )
    assert closed.status_code == 201
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO billing_cashledgerentry (
                id, public_number, cash_shift_id, created_by_id,
                actor_name_snapshot, actor_email_snapshot, actor_role_snapshot,
                kind, amount_minor, payment_method, idempotency_key, payload_hash, posted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'DEPOSIT', 1, '', %s, %s, NOW())
            """,
            [
                uuid4(),
                f"TXN-{uuid4().hex[:12].upper()}",
                shift.pk,
                actor.pk,
                actor.display_name,
                actor.email,
                actor.role,
                "after-close",
                "b" * 64,
            ],
        )


@pytest.mark.django_db(transaction=True)
def test_excess_close_requires_comment_and_persists_positive_discrepancy() -> None:
    actor = create_user("excess@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)

    missing_comment = post_close(
        client,
        shift,
        actual_cash_minor=250,
        expected_operations_count=0,
    )
    assert missing_comment.status_code == 422
    excess = post_close(
        client,
        shift,
        actual_cash_minor=250,
        expected_operations_count=0,
        comment="Надлишок підтверджено",
        key="excess-close",
    )
    assert excess.status_code == 201
    reconciliation = excess.json()["shift"]["reconciliation"]
    assert reconciliation["expected_cash_minor"] == 0
    assert reconciliation["actual_cash_minor"] == 250
    assert reconciliation["discrepancy_minor"] == 250


@pytest.mark.django_db(transaction=True)
def test_close_rolls_back_with_audit_failure_and_concurrent_exact_submit_replays() -> None:
    rollback_actor = create_user("audit-rollback@example.test")
    rollback_shift = CashShift.objects.create(employee=rollback_actor)
    with patch(
        "apps.billing.services.record_audit_event",
        side_effect=RuntimeError("audit unavailable"),
    ):
        failed = post_close(
            authenticated_client(rollback_actor),
            rollback_shift,
            actual_cash_minor=0,
            expected_operations_count=0,
            key="rollback-close",
        )
    assert failed.status_code == 500
    rollback_shift.refresh_from_db()
    assert rollback_shift.status == CashShiftStatus.OPEN
    assert rollback_shift.closed_at is None
    assert rollback_shift.close_idempotency_key == ""
    assert not AuditEvent.objects.filter(action=AuditAction.CASH_SHIFT_CLOSED).exists()

    actor = create_user("concurrent-close@example.test")
    shift = CashShift.objects.create(employee=actor)
    barrier = Barrier(2)

    def submit(_: int) -> tuple[int, bool]:
        close_old_connections()
        request_actor = User.objects.get(pk=actor.pk)
        request_shift = CashShift.objects.get(pk=shift.pk)
        barrier.wait(timeout=5)
        try:
            response = post_close(
                authenticated_client(request_actor),
                request_shift,
                actual_cash_minor=0,
                expected_operations_count=0,
                key="concurrent-exact",
            )
            return response.status_code, bool(response.json().get("replayed"))
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, range(2)))
    assert sorted(results) == [(200, True), (201, False)]
    assert AuditEvent.objects.filter(action=AuditAction.CASH_SHIFT_CLOSED).count() == 1


@pytest.mark.django_db(transaction=True)
def test_payment_refund_and_cash_replays_remain_exact_after_shift_close() -> None:
    actor = create_user("post-close-replay@example.test")
    shift = CashShift.objects.create(employee=actor)
    client = authenticated_client(actor)
    receivable = completed_receivable(amount_minor=8_000, index=740)

    payment = post_full_payment(
        client,
        receivable,
        key="replay-payment",
        payment_method=PaymentMethod.CARD,
    )
    assert payment.status_code == 201
    payment_id = payment.json()["operation"]["payment"]["id"]
    refund = client.post(
        f"/api/v1/payments/{payment_id}/refunds",
        {"reason": "Повтор після close"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="replay-refund",
    )
    movement = post_movement(client, amount_minor=900, key="replay-movement")
    assert refund.status_code == 201
    assert movement.status_code == 201
    closed = post_close(
        client,
        shift,
        actual_cash_minor=900,
        expected_operations_count=3,
        key="replay-family-close",
    )
    assert closed.status_code == 201, closed.json()

    payment_replay = post_full_payment(
        client,
        receivable,
        key="replay-payment",
        payment_method=PaymentMethod.CARD,
    )
    refund_replay = client.post(
        f"/api/v1/payments/{payment_id}/refunds",
        {"reason": "Повтор після close"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="replay-refund",
    )
    movement_replay = post_movement(client, amount_minor=900, key="replay-movement")
    assert payment_replay.status_code == 200
    assert payment_replay.json()["replayed"] is True
    assert refund_replay.status_code == 200
    assert refund_replay.json()["replayed"] is True
    assert movement_replay.status_code == 200
    assert movement_replay.json()["replayed"] is True
    assert CashLedgerEntry.objects.filter(cash_shift=shift).count() == 3
    new_movement = post_movement(client, amount_minor=1, key="new-after-close")
    assert new_movement.status_code == 409
    assert new_movement.json()["code"] == "cash_shift_required"


@pytest.mark.django_db(transaction=True)
def test_close_serializes_against_payment_refund_and_cash_movement_races() -> None:
    def run_race(
        *,
        actor: User,
        shift: CashShift,
        mutation_submit: Callable[[APIClient], Any],
    ) -> tuple[tuple[int, str], tuple[int, str]]:
        barrier = Barrier(2)

        def submit_close() -> tuple[int, str]:
            close_old_connections()
            request_actor = User.objects.get(pk=actor.pk)
            request_shift = CashShift.objects.get(pk=shift.pk)
            barrier.wait(timeout=5)
            try:
                response = post_close(
                    authenticated_client(request_actor),
                    request_shift,
                    actual_cash_minor=0,
                    expected_operations_count=0,
                    key=f"race-close-{shift.pk}",
                )
                return response.status_code, response.json().get("code", "closed")
            finally:
                connections["default"].close()

        def submit_mutation() -> tuple[int, str]:
            close_old_connections()
            request_actor = User.objects.get(pk=actor.pk)
            barrier.wait(timeout=5)
            try:
                response = mutation_submit(authenticated_client(request_actor))
                return response.status_code, response.json().get("code", "posted")
            finally:
                connections["default"].close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            close_future = executor.submit(submit_close)
            mutation_future = executor.submit(submit_mutation)
            close_result = close_future.result(timeout=15)
            mutation_result = mutation_future.result(timeout=15)

        shift.refresh_from_db()
        entry_count = CashLedgerEntry.objects.filter(cash_shift=shift).count()
        if close_result == (201, "closed"):
            assert mutation_result == (409, "cash_shift_required")
            assert shift.status == CashShiftStatus.CLOSED
            assert entry_count == 0
            assert (
                AuditEvent.objects.filter(
                    action=AuditAction.CASH_SHIFT_CLOSED,
                    object_id=str(shift.pk),
                ).count()
                == 1
            )
        else:
            assert close_result == (409, "cash_shift_changed")
            assert mutation_result == (201, "posted")
            assert shift.status == CashShiftStatus.OPEN
            assert entry_count == 1
            assert not AuditEvent.objects.filter(
                action=AuditAction.CASH_SHIFT_CLOSED,
                object_id=str(shift.pk),
            ).exists()
        return close_result, mutation_result

    cash_actor = create_user("race-cash@example.test")
    cash_shift = CashShift.objects.create(employee=cash_actor)
    run_race(
        actor=cash_actor,
        shift=cash_shift,
        mutation_submit=lambda client: post_movement(
            client,
            amount_minor=100,
            key="race-cash-movement",
        ),
    )

    payment_actor = create_user("race-payment@example.test")
    payment_shift = CashShift.objects.create(employee=payment_actor)
    payment_receivable = completed_receivable(amount_minor=3_500, index=741)
    run_race(
        actor=payment_actor,
        shift=payment_shift,
        mutation_submit=lambda client: post_full_payment(
            client,
            payment_receivable,
            key="race-payment",
            payment_method=PaymentMethod.CARD,
        ),
    )

    original_actor = create_user("race-refund-original@example.test")
    CashShift.objects.create(employee=original_actor)
    original_client = authenticated_client(original_actor)
    refund_receivable = completed_receivable(amount_minor=4_500, index=742)
    original_payment = post_full_payment(
        original_client,
        refund_receivable,
        key="race-refund-original-payment",
        payment_method=PaymentMethod.CARD,
    )
    assert original_payment.status_code == 201
    original_payment_id = original_payment.json()["operation"]["payment"]["id"]
    refund_actor = create_user("race-refund@example.test")
    refund_shift = CashShift.objects.create(employee=refund_actor)
    run_race(
        actor=refund_actor,
        shift=refund_shift,
        mutation_submit=lambda client: client.post(
            f"/api/v1/payments/{original_payment_id}/refunds",
            {"reason": "Race refund"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="race-refund",
        ),
    )
    refund_receivable.refresh_from_db()
    if CashLedgerEntry.objects.filter(cash_shift=refund_shift).exists():
        assert refund_receivable.status == ReceivableStatus.REFUNDED
    else:
        assert refund_receivable.status == ReceivableStatus.PAID


@pytest.mark.django_db
def test_openapi_freezes_close_preview_history_detail_and_strict_close_schema() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    components = schema["components"]["schemas"]

    assert paths["/api/v1/cash-shifts"]["get"]["operationId"] == "cash_shift_list"
    assert paths["/api/v1/cash-shifts/{shift_id}"]["get"]["operationId"] == ("cash_shift_retrieve")
    assert (
        paths["/api/v1/cash-shifts/{shift_id}/close-preview"]["get"]["operationId"]
        == "cash_shift_close_preview"
    )
    close_operation = paths["/api/v1/cash-shifts/{shift_id}/close"]["post"]
    assert close_operation["operationId"] == "cash_shift_close"
    close_request_ref = close_operation["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    close_request = components[close_request_ref.rsplit("/", 1)[-1]]
    assert set(close_request["properties"]) == {
        "actual_cash_minor",
        "expected_operations_count",
        "cash_count_confirmed",
        "comment",
    }
    assert set(close_request["required"]) == {
        "actual_cash_minor",
        "expected_operations_count",
        "cash_count_confirmed",
    }
    assert close_request["additionalProperties"] is False
    confirmed_schema = close_request["properties"]["cash_count_confirmed"]
    if "$ref" in confirmed_schema:
        confirmed_schema = components[confirmed_schema["$ref"].rsplit("/", 1)[-1]]
    assert confirmed_schema["enum"] == [True]
    assert close_operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CashShiftCloseResponse"
    }
    assert close_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CashShiftCloseResponse"
    }
    assert set(components["CashShiftSummary"]["properties"]) == {
        "id",
        "public_number",
        "status",
        "employee",
        "opened_at",
        "closed_at",
        "totals",
        "reconciliation",
    }
