from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction, AuditSection
from apps.billing.models import (
    CashLedgerEntry,
    CashLedgerEntryKind,
    CashShift,
    ImmutablePaymentError,
    ImmutableReceivableError,
    Payment,
    PaymentMethod,
    Receivable,
    ReceivableStatus,
)
from apps.clinic.models import AppointmentStatusConfig, Room, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.visits.models import Visit, VisitServiceLine, VisitStatus


def create_user(*, email: str, role: str, first_name: str = "Марина") -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=role,
        first_name=first_name,
        last_name="Бойко",
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def completed_receivable(
    *,
    amount_minor: int = 145_000,
    index: int = 1,
    patient_first_name: str = "Марія",
    patient_last_name: str = "Бондар",
    service_name: str = "Медичний педикюр",
) -> Receivable:
    suffix = f"{index}-{uuid4().hex[:8]}"
    specialist = create_user(
        email=f"specialist-{suffix}@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Олена",
    )
    patient = Patient.objects.create(
        first_name=patient_first_name,
        last_name=patient_last_name,
        phone=f"06712{index:05d}"[-10:],
        primary_podologist=specialist,
    )
    service = Service.objects.create(
        code=f"PAY-{suffix}"[:32],
        name=service_name,
        duration_minutes=45,
        price_minor=amount_minor,
        color="#0F766E",
    )
    room = Room.objects.create(name=f"Кабінет {suffix}"[:100])
    completed, _ = AppointmentStatusConfig.objects.update_or_create(
        code="COMPLETED",
        defaults={
            "label": "Завершено",
            "color": "#15803D",
            "manual_admin": False,
            "manual_reception": False,
            "manual_podologist": False,
        },
    )
    starts_at = timezone.now() - timedelta(hours=index + 1)
    appointment = Appointment.objects.create(
        patient=patient,
        specialist=specialist,
        service=service,
        room=room,
        time_range=(starts_at, starts_at + timedelta(minutes=45)),
        duration_minutes=45,
        service_name_snapshot=service.name,
        service_color_snapshot=service.color,
        room_label_snapshot=room.name,
        status=completed,
        complaints="",
        has_no_complaints=True,
    )
    visit = Visit.objects.create(
        appointment=appointment,
        patient=patient,
        specialist=specialist,
        status=VisitStatus.COMPLETED,
        complaints="",
        has_no_complaints=True,
        total_minor=amount_minor,
        payment_handoff_requested=True,
        version=2,
        started_by=specialist,
        completed_at=starts_at + timedelta(minutes=45),
    )
    VisitServiceLine.objects.create(
        visit=visit,
        service=service,
        service_code=service.code,
        service_name=service.name,
        duration_minutes=service.duration_minutes,
        price_minor=service.price_minor,
        quantity=1,
        is_primary=True,
    )
    return Receivable.objects.create(
        visit=visit,
        amount_minor=amount_minor,
        status=(ReceivableStatus.PAID if amount_minor == 0 else ReceivableStatus.OPEN),
    )


def post_payment(
    client: APIClient,
    receivable: Receivable,
    *,
    key: str = "payment-key-1",
    payment_method: str = PaymentMethod.CASH,
    comment: str = "Оплачено повністю",
):
    return client.post(
        "/api/v1/payments",
        {
            "visit_id": str(receivable.visit_id),
            "payment_method": payment_method,
            "comment": comment,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_REQUEST_ID="tp702-payment",
    )


def raw_payment(
    *,
    ledger: CashLedgerEntry,
    receivable: Receivable,
    actor: User,
    patient_name_override: str | None = None,
) -> Payment:
    visit = receivable.visit
    patient = visit.patient
    specialist = visit.specialist
    lines = list(visit.service_lines.all())
    return Payment(
        ledger_entry=ledger,
        receivable=receivable,
        patient_id_snapshot=patient.pk,
        patient_public_number_snapshot=patient.public_number,
        patient_name_snapshot=(
            patient.display_name if patient_name_override is None else patient_name_override
        ),
        patient_phone_snapshot=patient.phone,
        visit_public_number_snapshot=visit.public_number,
        visit_completed_at_snapshot=visit.completed_at,
        visit_payment_handoff_requested_snapshot=visit.payment_handoff_requested,
        visit_total_minor_snapshot=visit.total_minor,
        specialist_id_snapshot=specialist.pk,
        specialist_name_snapshot=specialist.display_name,
        employee_name_snapshot=actor.display_name,
        employee_email_snapshot=actor.email,
        services_snapshot=[
            {
                "id": str(line.pk),
                "code": line.service_code,
                "name": line.service_name,
                "quantity": line.quantity,
                "unit_price_minor": line.price_minor,
                "line_total_minor": line.line_total_minor,
            }
            for line in lines
        ],
        services_search_snapshot=" ".join(
            f"{line.service_code} {line.service_name}" for line in lines
        ),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payment_method", "expected_cash"),
    [
        (PaymentMethod.CASH, 145_000),
        (PaymentMethod.CARD, 0),
        (PaymentMethod.TRANSFER, 0),
    ],
)
def test_full_payment_is_server_derived_snapshotted_audited_and_in_own_shift(
    payment_method: str,
    expected_cash: int,
) -> None:
    actor = create_user(email=f"{payment_method.lower()}@example.test", role=UserRole.RECEPTION)
    shift = CashShift.objects.create(employee=actor)
    receivable = completed_receivable()

    response = post_payment(
        authenticated_client(actor),
        receivable,
        payment_method=payment_method,
        comment="  Оплачено повністю  ",
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["replayed"] is False
    operation = body["operation"]
    assert operation["id"] == str(receivable.pk)
    assert operation["type"] == "PAYMENT"
    assert operation["status"] == "PAID"
    assert operation["amount_minor"] == 145_000
    assert set(operation) == {
        "id",
        "type",
        "status",
        "occurred_at",
        "amount_minor",
        "patient",
        "visit",
        "payment",
        "refund",
    }
    assert operation["refund"] is None
    assert operation["patient"]["display_name"] == "Марія Бондар"
    assert operation["visit"]["payment_handoff_requested"] is True
    assert operation["visit"]["total_minor"] == 145_000
    assert operation["visit"]["specialist"]["name"] == "Олена Бойко"
    assert operation["visit"]["services"][0]["name"] == "Медичний педикюр"
    assert operation["visit"]["services"][0]["unit_price_minor"] == 145_000
    assert operation["payment"]["payment_method"] == payment_method
    assert operation["payment"]["comment"] == "Оплачено повністю"
    assert operation["payment"]["cash_shift"]["id"] == str(shift.pk)
    assert operation["payment"]["actor"] == {"id": actor.pk, "name": actor.display_name}
    assert set(operation["payment"]) == {
        "id",
        "ledger_entry_id",
        "public_number",
        "payment_method",
        "comment",
        "posted_at",
        "actor",
        "cash_shift",
    }

    receivable.refresh_from_db()
    payment = Payment.objects.select_related("ledger_entry").get(receivable=receivable)
    assert receivable.status == ReceivableStatus.PAID
    assert payment.ledger_entry.amount_minor == 145_000
    assert payment.ledger_entry.kind == CashLedgerEntryKind.PAYMENT
    assert payment.ledger_entry.payment_method == payment_method
    assert payment.patient_id_snapshot == receivable.visit.patient_id
    assert payment.visit_total_minor_snapshot == 145_000
    assert payment.services_snapshot == operation["visit"]["services"]

    event = AuditEvent.objects.get(action=AuditAction.PAYMENT_POSTED)
    assert event.section == AuditSection.BILLING
    assert event.actor == actor
    assert event.object_id == str(payment.pk)
    assert event.object_label == payment.ledger_entry.public_number
    assert event.correlation_id == "tp702-payment"
    assert event.before["receivable_status"] == "OPEN"
    assert event.after["receivable_status"] == "PAID"

    current = authenticated_client(actor).get("/api/v1/cash-shifts/current").json()["shift"]
    assert current["totals"]["payments_total_minor"] == 145_000
    assert current["totals"]["revenue_minor"] == 145_000
    assert current["totals"]["expected_cash_minor"] == expected_cash


@pytest.mark.django_db
def test_payment_replays_same_key_and_rejects_mismatch_or_new_key_after_settlement() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    client = authenticated_client(actor)

    first = post_payment(client, receivable)
    replay = post_payment(client, receivable)
    mismatch = post_payment(client, receivable, payment_method=PaymentMethod.CARD)
    new_key = post_payment(client, receivable, key="payment-key-2")

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["operation"] == first.json()["operation"]
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert new_key.status_code == 409
    assert new_key.json()["code"] == "receivable_already_paid"
    assert Payment.objects.count() == 1
    assert CashLedgerEntry.objects.filter(kind=CashLedgerEntryKind.PAYMENT).count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.PAYMENT_POSTED).count() == 1


@pytest.mark.django_db
def test_payment_requires_own_open_shift_and_never_uses_another_employee_shift() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    other = create_user(email="other@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=other)
    receivable = completed_receivable()

    response = post_payment(authenticated_client(actor), receivable)

    assert response.status_code == 409
    assert response.json()["code"] == "cash_shift_required"
    assert receivable.status == ReceivableStatus.OPEN
    assert not Payment.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_payment_contract_rejects_unknown_amount_and_requires_valid_idempotency_key() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    client = authenticated_client(actor)
    payload = {
        "visit_id": str(receivable.visit_id),
        "payment_method": "CASH",
        "comment": "",
    }

    unknown = client.post(
        "/api/v1/payments",
        {**payload, "amount_minor": 1},
        format="json",
        HTTP_IDEMPOTENCY_KEY="unknown-field",
    )
    missing = client.post("/api/v1/payments", payload, format="json")
    too_long = client.post(
        "/api/v1/payments",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="x" * 129,
    )

    assert unknown.status_code == 422
    assert unknown.json()["fields"] == {"amount_minor": ["Невідоме поле."]}
    assert missing.status_code == 422
    assert missing.json()["code"] == "idempotency_key_required"
    assert too_long.status_code == 422
    assert too_long.json()["code"] == "idempotency_key_invalid"
    assert not Payment.objects.exists()


@pytest.mark.django_db
def test_payment_endpoints_enforce_finance_role_and_authentication() -> None:
    receivable = completed_receivable()
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    anonymous = APIClient()

    assert authenticated_client(podologist).get("/api/v1/finance/operations").status_code == 403
    assert post_payment(authenticated_client(podologist), receivable).status_code == 403
    assert anonymous.get("/api/v1/finance/operations").status_code == 401
    assert post_payment(anonymous, receivable).status_code == 401
    assert not Payment.objects.exists()


@pytest.mark.django_db
def test_zero_total_receivable_is_paid_without_payment_or_ledger_and_is_listed() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    zero = completed_receivable(amount_minor=0)

    listing = authenticated_client(actor).get("/api/v1/finance/operations")
    attempt = post_payment(authenticated_client(actor), zero)

    assert zero.status == ReceivableStatus.PAID
    assert listing.status_code == 200
    assert listing.json()["operations"][0]["id"] == str(zero.pk)
    assert listing.json()["operations"][0]["status"] == "PAID"
    assert listing.json()["operations"][0]["amount_minor"] == 0
    assert listing.json()["operations"][0]["payment"] is None
    assert attempt.status_code == 409
    assert attempt.json()["code"] == "receivable_already_paid"
    assert not Payment.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_refunded_receivable_returns_dedicated_conflict_without_new_payment() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = replica")
        cursor.execute(
            "UPDATE billing_receivable SET status = 'REFUNDED' WHERE id = %s",
            [receivable.pk],
        )

    response = post_payment(authenticated_client(actor), receivable)

    assert response.status_code == 409
    assert response.json()["code"] == "receivable_already_refunded"
    assert not Payment.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_inconsistent_receivable_cannot_post_a_partial_visit_total() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = replica")
        cursor.execute(
            "UPDATE billing_receivable SET amount_minor = %s WHERE id = %s",
            [100, receivable.pk],
        )

    response = post_payment(authenticated_client(actor), receivable)

    assert response.status_code == 409
    assert response.json()["code"] == "visit_not_payable"
    assert not Payment.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_finance_union_search_filters_snapshots_and_stable_cursor() -> None:
    actor = create_user(email="admin@example.test", role=UserRole.ADMIN)
    CashShift.objects.create(employee=actor)
    open_receivable = completed_receivable(
        index=1,
        patient_first_name="Марія",
        patient_last_name="Зелена",
        service_name="Обробка тріщин",
    )
    paid_receivable = completed_receivable(
        index=2,
        patient_first_name="Ірина",
        patient_last_name="Синя",
        service_name="Медичний педикюр",
    )
    zero_receivable = completed_receivable(
        amount_minor=0,
        index=3,
        patient_first_name="Олена",
        patient_last_name="Біла",
        service_name="Безкоштовна консультація",
    )
    paid_response = post_payment(
        authenticated_client(actor),
        paid_receivable,
        payment_method=PaymentMethod.CARD,
    )
    assert paid_response.status_code == 201, paid_response.json()
    paid_public_number = paid_response.json()["operation"]["payment"]["public_number"]

    client = authenticated_client(actor)
    all_rows = client.get("/api/v1/finance/operations")
    by_full_name = client.get("/api/v1/finance/operations", {"search": "Марія Зелена"})
    by_service = client.get("/api/v1/finance/operations", {"search": "Обробка тріщин"})
    by_number = client.get("/api/v1/finance/operations", {"search": paid_public_number})
    paid_rows = client.get("/api/v1/finance/operations", {"status": "PAID"})
    card_rows = client.get("/api/v1/finance/operations", {"payment_method": "CARD"})
    patient_rows = client.get(
        "/api/v1/finance/operations",
        {"patient_id": str(open_receivable.visit.patient_id)},
    )
    invalid_dates = client.get(
        "/api/v1/finance/operations",
        {"date_from": "2026-07-23", "date_to": "2026-07-22"},
    )
    invalid_all = client.get("/api/v1/finance/operations", {"status": "all"})

    assert all_rows.status_code == 200
    assert len(all_rows.json()["operations"]) == 3
    assert {row["id"] for row in all_rows.json()["operations"]} == {
        str(open_receivable.pk),
        str(paid_receivable.pk),
        str(zero_receivable.pk),
    }
    assert [row["id"] for row in by_full_name.json()["operations"]] == [str(open_receivable.pk)]
    assert [row["id"] for row in by_service.json()["operations"]] == [str(open_receivable.pk)]
    assert [row["id"] for row in by_number.json()["operations"]] == [str(paid_receivable.pk)]
    assert {row["id"] for row in paid_rows.json()["operations"]} == {
        str(paid_receivable.pk),
        str(zero_receivable.pk),
    }
    assert [row["id"] for row in card_rows.json()["operations"]] == [str(paid_receivable.pk)]
    assert [row["id"] for row in patient_rows.json()["operations"]] == [str(open_receivable.pk)]
    assert invalid_dates.status_code == 422
    assert invalid_all.status_code == 422

    with patch("apps.billing.services._FINANCE_PAGE_SIZE", 2):
        first = client.get("/api/v1/finance/operations").json()
        second = client.get(
            "/api/v1/finance/operations",
            {"cursor": first["next_cursor"]},
        ).json()
    assert len(first["operations"]) == 2
    assert len(second["operations"]) == 1
    assert first["next_cursor"]
    assert second["next_cursor"] is None
    assert len({row["id"] for row in [*first["operations"], *second["operations"]]}) == 3


@pytest.mark.django_db
def test_paid_operation_keeps_immutable_patient_staff_visit_and_service_snapshots() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    response = post_payment(authenticated_client(actor), receivable)
    assert response.status_code == 201, response.json()
    original = response.json()["operation"]

    patient = receivable.visit.patient
    specialist = receivable.visit.specialist
    line = receivable.visit.service_lines.get()
    original_patient_id = patient.pk
    patient.first_name = "Змінена"
    patient.phone = "0500000000"
    patient.save()
    specialist.first_name = "Змінений"
    specialist.save()
    actor.first_name = "Інший"
    actor.save()
    line.service_name = "Перейменована послуга"
    line.price_minor = 1
    line.save()
    replacement = Patient.objects.create(
        first_name="Нова",
        last_name="Пацієнтка",
        phone="0630000000",
        primary_podologist=specialist,
    )
    receivable.visit.patient = replacement
    receivable.visit.save(update_fields=("patient", "updated_at"))

    client = authenticated_client(actor)
    current = client.get("/api/v1/finance/operations").json()["operations"][0]
    assert current["patient"] == original["patient"]
    assert current["visit"] == original["visit"]
    assert current["payment"]["actor"] == original["payment"]["actor"]
    assert (
        len(
            client.get("/api/v1/finance/operations", {"search": "Медичний педикюр"}).json()[
                "operations"
            ]
        )
        == 1
    )
    assert (
        client.get("/api/v1/finance/operations", {"search": "Перейменована послуга"}).json()[
            "operations"
        ]
        == []
    )
    assert (
        client.get("/api/v1/finance/operations", {"search": "unit_price_minor"}).json()[
            "operations"
        ]
        == []
    )
    assert (
        len(
            client.get("/api/v1/finance/operations", {"search": "Марія Бондар"}).json()[
                "operations"
            ]
        )
        == 1
    )
    assert (
        client.get("/api/v1/finance/operations", {"search": "Змінена Бондар"}).json()["operations"]
        == []
    )
    assert (
        len(
            client.get(
                "/api/v1/finance/operations", {"patient_id": str(original_patient_id)}
            ).json()["operations"]
        )
        == 1
    )
    assert (
        client.get("/api/v1/finance/operations", {"patient_id": str(replacement.pk)}).json()[
            "operations"
        ]
        == []
    )


@pytest.mark.django_db
def test_payment_rolls_back_ledger_status_and_audit_when_audit_write_fails() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()

    with patch(
        "apps.billing.services.record_audit_event",
        side_effect=RuntimeError("audit down"),
    ):
        response = post_payment(authenticated_client(actor), receivable)

    assert response.status_code == 500
    receivable.refresh_from_db()
    assert receivable.status == ReceivableStatus.OPEN
    assert not Payment.objects.exists()
    assert not CashLedgerEntry.objects.exists()
    assert not AuditEvent.objects.filter(action=AuditAction.PAYMENT_POSTED).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_payment_key_replays_one_atomic_result() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    barrier = Barrier(2)

    def submit(_: int) -> tuple[int, str, str]:
        close_old_connections()
        request_actor = User.objects.get(pk=actor.pk)
        request_receivable = Receivable.objects.get(pk=receivable.pk)
        barrier.wait(timeout=5)
        try:
            response = post_payment(
                authenticated_client(request_actor),
                request_receivable,
                key="concurrent-payment",
            )
            body = response.json()
            return (
                response.status_code,
                body.get("code", "ok"),
                body.get("operation", {}).get("id", ""),
            )
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, range(2)))

    assert sorted(code for code, _, _ in results) == [200, 201]
    assert len({operation_id for _, _, operation_id in results}) == 1
    assert Payment.objects.count() == 1
    assert CashLedgerEntry.objects.filter(kind=CashLedgerEntryKind.PAYMENT).count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.PAYMENT_POSTED).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_different_keys_allow_only_one_payment_per_receivable() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    barrier = Barrier(2)

    def submit(index: int) -> tuple[int, str]:
        close_old_connections()
        request_actor = User.objects.get(pk=actor.pk)
        request_receivable = Receivable.objects.get(pk=receivable.pk)
        barrier.wait(timeout=5)
        try:
            response = post_payment(
                authenticated_client(request_actor),
                request_receivable,
                key=f"concurrent-payment-{index}",
            )
            return response.status_code, response.json().get("code", "ok")
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, range(2)))

    assert sorted(code for code, _ in results) == [201, 409]
    assert {value for _, value in results} == {"ok", "receivable_already_paid"}
    assert Payment.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.PAYMENT_POSTED).count() == 1


@pytest.mark.django_db(transaction=True)
def test_payment_receivable_and_ledger_raw_guards_are_enforced() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    other = create_user(email="other@example.test", role=UserRole.RECEPTION)
    shift = CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    paid = post_payment(authenticated_client(actor), receivable)
    assert paid.status_code == 201, paid.json()
    payment = Payment.objects.get()

    payment.comment = "changed"
    with pytest.raises(ImmutablePaymentError):
        payment.save()
    with pytest.raises(ImmutablePaymentError):
        Payment.objects.filter(pk=payment.pk).update(comment="changed")
    with pytest.raises(ImmutablePaymentError):
        payment.delete()
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE billing_payment SET comment = %s WHERE id = %s", ["x", payment.pk])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM billing_payment WHERE id = %s", [payment.pk])

    receivable.refresh_from_db()
    receivable.status = ReceivableStatus.OPEN
    with pytest.raises(ImmutableReceivableError):
        receivable.save()
    with pytest.raises(ImmutableReceivableError):
        Receivable.objects.filter(pk=receivable.pk).update(status=ReceivableStatus.OPEN)
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_receivable SET status = 'OPEN' WHERE id = %s",
            [receivable.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM billing_receivable WHERE id = %s", [receivable.pk])

    other_shift = CashShift.objects.create(employee=other)
    with pytest.raises(DatabaseError), transaction.atomic():
        CashLedgerEntry.objects.create(
            cash_shift=other_shift,
            created_by=actor,
            kind=CashLedgerEntryKind.PAYMENT,
            amount_minor=100,
            payment_method=PaymentMethod.CASH,
            idempotency_key="wrong-owner",
            payload_hash="a" * 64,
        )

    with pytest.raises(DatabaseError), transaction.atomic():
        unpaid = completed_receivable(index=2)
        ledger = CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=CashLedgerEntryKind.PAYMENT,
            amount_minor=unpaid.amount_minor,
            payment_method=PaymentMethod.CASH,
            idempotency_key="raw-snapshot",
            payload_hash="b" * 64,
        )
        Payment.objects.bulk_create(
            [
                raw_payment(
                    ledger=ledger,
                    receivable=unpaid,
                    actor=actor,
                    patient_name_override="Неправдиве ім’я",
                )
            ]
        )
    assert not CashLedgerEntry.objects.filter(idempotency_key="raw-snapshot").exists()

    orphan_receivable = completed_receivable(index=3)
    with pytest.raises(DatabaseError), transaction.atomic():
        CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=CashLedgerEntryKind.PAYMENT,
            amount_minor=orphan_receivable.amount_minor,
            payment_method=PaymentMethod.CASH,
            idempotency_key="orphan-payment-ledger",
            payload_hash="d" * 64,
        )
    assert not CashLedgerEntry.objects.filter(idempotency_key="orphan-payment-ledger").exists()

    unsettled_receivable = completed_receivable(index=4)
    with pytest.raises(DatabaseError), transaction.atomic():
        ledger = CashLedgerEntry.objects.create(
            cash_shift=shift,
            created_by=actor,
            kind=CashLedgerEntryKind.PAYMENT,
            amount_minor=unsettled_receivable.amount_minor,
            payment_method=PaymentMethod.CASH,
            idempotency_key="unsettled-typed-payment",
            payload_hash="e" * 64,
        )
        Payment.objects.bulk_create(
            [
                raw_payment(
                    ledger=ledger,
                    receivable=unsettled_receivable,
                    actor=actor,
                )
            ]
        )
    assert not CashLedgerEntry.objects.filter(idempotency_key="unsettled-typed-payment").exists()
    assert not Payment.objects.filter(receivable=unsettled_receivable).exists()

    closed_actor = create_user(email="closed@example.test", role=UserRole.RECEPTION)
    closed_shift = CashShift.objects.create(employee=closed_actor)
    closed_shift.status = "CLOSED"
    closed_shift.closed_at = timezone.now()
    closed_shift.expected_cash_at_close_minor = 0
    closed_shift.actual_cash_at_close_minor = 0
    closed_shift.discrepancy_minor = 0
    closed_shift.closed_by = closed_actor
    closed_shift.closed_by_name_snapshot = closed_actor.display_name
    closed_shift.closed_by_email_snapshot = closed_actor.email
    closed_shift.closed_by_role_snapshot = closed_actor.role
    closed_shift.close_idempotency_key = "raw-guard-close"
    closed_shift.close_payload_hash = "f" * 64
    closed_shift.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        CashLedgerEntry.objects.create(
            cash_shift=closed_shift,
            created_by=closed_actor,
            kind=CashLedgerEntryKind.PAYMENT,
            amount_minor=100,
            payment_method=PaymentMethod.CASH,
            idempotency_key="closed-shift",
            payload_hash="c" * 64,
        )


@pytest.mark.django_db
def test_payment_openapi_freezes_union_and_full_payment_contract() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    components = schema["components"]["schemas"]
    list_operation = paths["/api/v1/finance/operations"]["get"]
    create_operation = paths["/api/v1/payments"]["post"]

    assert {
        parameter["name"]
        for parameter in list_operation["parameters"]
        if parameter["in"] == "query"
    } == {
        "search",
        "type",
        "status",
        "date_from",
        "date_to",
        "payment_method",
        "patient_id",
        "amount_minor",
        "refundable_only",
        "cursor",
    }
    query_parameters = {
        parameter["name"]: parameter
        for parameter in list_operation["parameters"]
        if parameter["in"] == "query"
    }
    assert set(query_parameters["type"]["schema"]["enum"]) == {
        "PAYMENT",
        "REFUND",
        "DEPOSIT",
        "WITHDRAWAL",
    }
    assert set(query_parameters["status"]["schema"]["enum"]) == {
        "OPEN",
        "PAID",
        "REFUNDED",
        "POSTED",
    }
    assert set(query_parameters["payment_method"]["schema"]["enum"]) == {
        "CASH",
        "CARD",
        "TRANSFER",
    }
    header = next(
        parameter
        for parameter in create_operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert header["required"] is True
    assert create_operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PaymentCreateRequest"
    }
    assert set(components["PaymentCreateRequest"]["properties"]) == {
        "visit_id",
        "payment_method",
        "comment",
    }
    assert set(components["PaymentCreateRequest"]["required"]) == {
        "visit_id",
        "payment_method",
    }
    assert components["PaymentCreateRequest"]["additionalProperties"] is False
    assert "amount_minor" not in components["PaymentCreateRequest"]["properties"]
    assert set(components["FinancePaymentOperation"]["required"]) == {
        "id",
        "type",
        "status",
        "occurred_at",
        "amount_minor",
        "patient",
        "visit",
        "payment",
        "refund",
    }
    assert set(components["FinanceVisit"]["required"]) == {
        "id",
        "public_number",
        "completed_at",
        "payment_handoff_requested",
        "total_minor",
        "specialist",
        "services",
    }
    assert components["FinancePaymentOperation"]["properties"]["payment"]["nullable"] is True
    assert components["FinancePaymentOperation"]["properties"]["refund"]["nullable"] is True
    assert set(components["FinancePayment"]["properties"]) == {
        "id",
        "ledger_entry_id",
        "public_number",
        "payment_method",
        "comment",
        "posted_at",
        "actor",
        "cash_shift",
    }
