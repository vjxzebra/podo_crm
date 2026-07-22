from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connections
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.billing.models import CashLedgerEntry, Payment, Receivable, ReceivableStatus
from apps.inventory.models import (
    InventoryOperation,
    InventoryOperationKind,
    MaterialLot,
    StockMovement,
)
from apps.scheduling.models import Appointment
from apps.visits.models import (
    Visit,
    VisitFinishResult,
    VisitRecommendation,
    VisitStatus,
)
from tests.scheduling.test_create_appointment import (
    KYIV,
    appointment_payload,
    authenticated_client,
    create_user,
)
from tests.visits.test_visit_draft_lines import material_with_lot
from tests.visits.test_visit_start_and_draft import arrived_appointment, start


def _finish_payload(
    *,
    version: int,
    recommendation: str = "Обробляти кремом двічі на день.",
    follow_up: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "version": version,
        "recommendations": recommendation,
        "payment_handoff_requested": True,
        "follow_up": follow_up,
    }


def _follow_up_payload(appointment: Appointment) -> dict[str, object]:
    return {
        "starts_at": datetime(2026, 8, 3, 11, 0, tzinfo=KYIV).isoformat(),
        "service_id": str(appointment.service_id),
        "specialist_id": appointment.specialist_id,
        "room_id": str(appointment.room_id),
    }


def _finish(
    client: APIClient,
    visit_id: str,
    payload: dict[str, object],
    *,
    key: str = "finish-key-1",
):
    return client.post(
        f"/api/v1/visits/{visit_id}/finish",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def _visit_with_materials(
    *,
    admin: User,
    quantities: tuple[str, ...] = ("1.000", "2.000"),
) -> tuple[Appointment, Visit, list[MaterialLot]]:
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    lots: list[MaterialLot] = []
    lines: list[dict[str, str]] = []
    for index, quantity in enumerate(quantities, start=1):
        _, lot = material_with_lot(
            sku=f"FIN-{index:03d}",
            quantity="5.000",
            lot_number=f"FIN-LOT-{index:03d}",
        )
        lots.append(lot)
        lines.append({"lot_id": str(lot.pk), "quantity": quantity})
    saved = authenticated_client(admin).put(
        f"/api/v1/visits/{visit_id}",
        {"version": 1, "material_lines": lines},
        format="json",
    )
    assert saved.status_code == 200, saved.json()
    return appointment, Visit.objects.get(pk=visit_id), lots


@pytest.mark.django_db
def test_finish_posts_stock_receivable_recommendation_follow_up_and_audit_atomically() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment, visit, lots = _visit_with_materials(admin=admin)
    payload = _finish_payload(
        version=visit.version,
        follow_up=_follow_up_payload(appointment),
    )

    response = _finish(authenticated_client(admin), str(visit.pk), payload)

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["replayed"] is False
    assert body["visit"]["status"] == VisitStatus.COMPLETED
    assert body["visit"]["total_minor"] == appointment.service.price_minor
    assert body["visit"]["payment_handoff_requested"] is True
    assert body["receivable"]["amount_minor"] == appointment.service.price_minor
    assert body["receivable"]["status"] == "OPEN"
    assert len(body["movement_ids"]) == 2
    assert body["follow_up_appointment_id"] is not None

    visit.refresh_from_db()
    appointment.refresh_from_db()
    for lot in lots:
        lot.refresh_from_db()
    assert visit.status == VisitStatus.COMPLETED
    assert visit.total_minor == appointment.service.price_minor
    assert visit.completed_at is not None
    assert appointment.status_id == "COMPLETED"
    assert [lot.current_quantity for lot in lots] == [Decimal("4.000"), Decimal("3.000")]
    operation = InventoryOperation.objects.get(kind=InventoryOperationKind.VISIT_USAGE)
    assert operation.source_visit_id == visit.pk
    assert StockMovement.objects.filter(operation=operation).count() == 2
    assert Receivable.objects.get(visit=visit).amount_minor == visit.total_minor
    recommendation = VisitRecommendation.objects.get(visit=visit)
    assert recommendation.text == "Обробляти кремом двічі на день."
    assert recommendation.author == admin
    follow_up = Appointment.objects.get(pk=body["follow_up_appointment_id"])
    assert follow_up.patient_id == visit.patient_id
    assert follow_up.status_id == "NEW"
    assert follow_up.has_no_complaints is True
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_COMPLETED).count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.STOCK_MOVEMENT_POSTED).count() == 1
    assert VisitFinishResult.objects.filter(visit=visit).count() == 1


@pytest.mark.django_db
def test_finish_auto_settles_zero_total_without_payment_or_cash_ledger_entry() -> None:
    admin = create_user(email="zero-admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    appointment.service.price_minor = 0
    appointment.service.save(update_fields=("price_minor", "updated_at"))
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    visit = Visit.objects.get(pk=visit_id)

    response = _finish(
        authenticated_client(admin),
        str(visit.pk),
        _finish_payload(version=visit.version),
        key="zero-total-finish",
    )

    assert response.status_code == 201, response.json()
    assert response.json()["receivable"]["amount_minor"] == 0
    assert response.json()["receivable"]["status"] == ReceivableStatus.PAID
    receivable = Receivable.objects.get(visit=visit)
    assert receivable.status == ReceivableStatus.PAID
    assert not Payment.objects.exists()
    assert not CashLedgerEntry.objects.exists()


@pytest.mark.django_db
def test_finish_replays_same_result_for_same_or_new_key_and_rejects_key_payload_mismatch() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    client = authenticated_client(admin)
    payload = _finish_payload(version=1, follow_up=None)

    first = _finish(client, visit_id, payload, key="stable-key")
    same_key = _finish(client, visit_id, payload, key="stable-key")
    new_key = _finish(client, visit_id, payload, key="network-retry-new-key")
    mismatch = _finish(
        client,
        visit_id,
        {**payload, "recommendations": "Інший текст"},
        key="stable-key",
    )

    assert first.status_code == 201
    assert same_key.status_code == 200
    assert new_key.status_code == 200
    assert same_key.json()["replayed"] is True
    assert new_key.json()["receivable"]["id"] == first.json()["receivable"]["id"]
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert Receivable.objects.count() == 1
    assert VisitFinishResult.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_COMPLETED).count() == 1


@pytest.mark.django_db
def test_finish_requires_key_and_enforces_role_and_object_scope() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    payload = _finish_payload(version=1)
    url = f"/api/v1/visits/{visit_id}/finish"

    missing_key = authenticated_client(admin).post(url, payload, format="json")
    reception_response = _finish(authenticated_client(reception), visit_id, payload)
    foreign_response = _finish(authenticated_client(foreign), visit_id, payload)

    assert missing_key.status_code == 422
    assert missing_key.json()["code"] == "idempotency_key_required"
    assert reception_response.status_code == 403
    assert foreign_response.status_code == 404
    assert Visit.objects.get(pk=visit_id).status == VisitStatus.DRAFT
    assert not Receivable.objects.exists()


@pytest.mark.django_db
def test_finish_insufficient_stock_rolls_back_all_completion_side_effects() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment, visit, lots = _visit_with_materials(admin=admin, quantities=("4.000",))
    lot = lots[0]
    lot.current_quantity = Decimal("3.000")
    lot.save(update_fields=("current_quantity",))

    response = _finish(
        authenticated_client(admin),
        str(visit.pk),
        _finish_payload(version=visit.version),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_stock"
    visit.refresh_from_db()
    appointment.refresh_from_db()
    lot.refresh_from_db()
    assert visit.status == VisitStatus.DRAFT
    assert appointment.status_id == "IN_PROGRESS"
    assert lot.current_quantity == Decimal("3.000")
    assert not InventoryOperation.objects.exists()
    assert not StockMovement.objects.exists()
    assert not Receivable.objects.exists()
    assert not VisitRecommendation.objects.exists()
    assert not VisitFinishResult.objects.exists()


@pytest.mark.django_db
def test_finish_fault_after_first_lot_update_leaves_no_partial_rows_or_balances() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment, visit, lots = _visit_with_materials(admin=admin)

    with patch(
        "apps.visits.finish_services.StockMovement.objects.create",
        side_effect=RuntimeError("fault after first lot update"),
    ):
        response = _finish(
            authenticated_client(admin),
            str(visit.pk),
            _finish_payload(version=visit.version),
        )

    assert response.status_code == 500
    visit.refresh_from_db()
    appointment.refresh_from_db()
    for lot in lots:
        lot.refresh_from_db()
    assert visit.status == VisitStatus.DRAFT
    assert appointment.status_id == "IN_PROGRESS"
    assert [lot.current_quantity for lot in lots] == [Decimal("5.000"), Decimal("5.000")]
    assert not InventoryOperation.objects.exists()
    assert not StockMovement.objects.exists()
    assert not Receivable.objects.exists()
    assert not VisitFinishResult.objects.exists()


@pytest.mark.django_db
def test_follow_up_slot_conflict_rolls_back_stock_receivable_and_completion() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment, visit, lots = _visit_with_materials(admin=admin, quantities=("1.000",))
    blocking = authenticated_client(admin).post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=appointment.specialist,
            service=appointment.service,
            room=appointment.room,
            patient=appointment.patient,
            starts_at=datetime(2026, 8, 3, 11, 0, tzinfo=KYIV),
        ),
        format="json",
    )
    assert blocking.status_code == 201, blocking.json()

    response = _finish(
        authenticated_client(admin),
        str(visit.pk),
        _finish_payload(
            version=visit.version,
            follow_up=_follow_up_payload(appointment),
        ),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "appointment_slot_conflict"
    visit.refresh_from_db()
    lots[0].refresh_from_db()
    assert visit.status == VisitStatus.DRAFT
    assert lots[0].current_quantity == Decimal("5.000")
    assert not Receivable.objects.exists()
    assert not InventoryOperation.objects.exists()
    assert not VisitFinishResult.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_double_finish_creates_one_completion_result() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    payload = _finish_payload(version=1)
    barrier = Barrier(2)

    def post_finish(_: int) -> tuple[int, str]:
        close_old_connections()
        actor = User.objects.get(pk=admin.pk)
        barrier.wait(timeout=5)
        try:
            response = _finish(
                authenticated_client(actor),
                visit_id,
                payload,
                key="concurrent-finish",
            )
            return response.status_code, response.json()["receivable"]["id"]
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(post_finish, range(2)))

    assert sorted(code for code, _ in results) == [200, 201]
    assert len({receivable_id for _, receivable_id in results}) == 1
    assert Receivable.objects.count() == 1
    assert VisitFinishResult.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_COMPLETED).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_finish_and_writeoff_never_make_lot_negative_or_partial() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    _, visit, lots = _visit_with_materials(admin=admin, quantities=("4.000",))
    lot = lots[0]
    finish_payload = _finish_payload(version=visit.version)
    writeoff_payload = {
        "reason": "Конкурентне ручне списання",
        "comment": "Перевірка блокування партії",
        "lines": [{"lot_id": str(lot.pk), "quantity": "3.000"}],
    }
    barrier = Barrier(2)

    def submit(kind: str) -> int:
        close_old_connections()
        actor = User.objects.get(pk=admin.pk)
        client = authenticated_client(actor)
        barrier.wait(timeout=5)
        try:
            if kind == "finish":
                return _finish(
                    client,
                    str(visit.pk),
                    finish_payload,
                    key="stock-race-finish",
                ).status_code
            return client.post(
                "/api/v1/inventory/write-offs",
                writeoff_payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="stock-race-writeoff",
            ).status_code
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, ("finish", "writeoff")))

    lot.refresh_from_db()
    assert sorted(results) == [201, 409]
    assert lot.current_quantity in {Decimal("1.000"), Decimal("2.000")}
    assert lot.current_quantity >= 0
    assert InventoryOperation.objects.count() == 1
    assert Receivable.objects.count() in {0, 1}
    if Receivable.objects.exists():
        assert InventoryOperation.objects.get().kind == InventoryOperationKind.VISIT_USAGE
        assert Visit.objects.get(pk=visit.pk).status == VisitStatus.COMPLETED
    else:
        assert InventoryOperation.objects.get().kind == InventoryOperationKind.MANUAL_WRITEOFF
        assert Visit.objects.get(pk=visit.pk).status == VisitStatus.DRAFT


@pytest.mark.django_db(transaction=True)
def test_concurrent_finish_and_slot_create_commit_exactly_one_follow_up() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    follow_up = _follow_up_payload(appointment)
    finish_payload = _finish_payload(version=1, follow_up=follow_up)
    blocking_payload = appointment_payload(
        specialist=appointment.specialist,
        service=appointment.service,
        room=appointment.room,
        patient=appointment.patient,
        starts_at=datetime(2026, 8, 3, 11, 0, tzinfo=KYIV),
    )
    barrier = Barrier(2)

    def submit(kind: str) -> int:
        close_old_connections()
        actor = User.objects.get(pk=admin.pk)
        client = authenticated_client(actor)
        barrier.wait(timeout=5)
        try:
            if kind == "finish":
                return _finish(
                    client,
                    visit_id,
                    finish_payload,
                    key="slot-race-finish",
                ).status_code
            return client.post(
                "/api/v1/appointments",
                blocking_payload,
                format="json",
            ).status_code
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, ("finish", "appointment")))

    visit = Visit.objects.get(pk=visit_id)
    assert sorted(results) == [201, 409]
    assert Appointment.objects.count() == 2
    assert (visit.status == VisitStatus.COMPLETED) is Receivable.objects.exists()
    assert VisitFinishResult.objects.count() == Receivable.objects.count()


@pytest.mark.django_db
def test_openapi_exposes_atomic_finish_contract_and_idempotency_header() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    operation = schema["paths"]["/api/v1/visits/{visit_id}/finish"]["post"]
    request_schema = schema["components"]["schemas"]["VisitFinishRequest"]
    response_schema = schema["components"]["schemas"]["VisitFinishResponse"]

    header = next(item for item in operation["parameters"] if item["name"] == "Idempotency-Key")
    assert header["required"] is True
    assert set(request_schema["required"]) == {"payment_handoff_requested", "version"}
    assert request_schema["properties"]["follow_up"]["nullable"] is True
    assert response_schema["properties"]["receivable"] == {
        "$ref": "#/components/schemas/VisitReceivable"
    }
    assert operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisitFinishResponse"
    }
