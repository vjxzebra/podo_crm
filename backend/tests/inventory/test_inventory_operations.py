from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.db import DatabaseError, IntegrityError, close_old_connections, connections, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.inventory.models import (
    ImmutableInventoryRecordError,
    InventoryOperation,
    Material,
    MaterialLot,
    StockMovement,
)

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str = UserRole.ADMIN) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_material(*, sku: str, name: str = "Матеріал", unit: str = "шт.") -> Material:
    return Material.objects.create(
        sku=sku,
        name=name,
        category="Витратні матеріали",
        unit=unit,
        minimum_quantity=Decimal("2"),
    )


def create_lot(
    *,
    material: Material,
    number: str,
    quantity: str,
    expires_delta: int = 90,
) -> MaterialLot:
    return MaterialLot.objects.create(
        material=material,
        lot_number=number,
        received_on=timezone.localdate(),
        expires_on=timezone.localdate() + timedelta(days=expires_delta),
        initial_quantity=Decimal(quantity),
        current_quantity=Decimal(quantity),
        purchase_price_minor=250,
        supplier_name="ТОВ Постачальник",
    )


def post_receipt(
    client: APIClient,
    *,
    key: str,
    lines: list[dict[str, object]],
    comment: str = "",
):
    return client.post(
        "/api/v1/inventory/receipts",
        {
            "received_on": timezone.localdate().isoformat(),
            "comment": comment,
            "lines": lines,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


@pytest.mark.django_db
def test_posts_multi_line_receipt_with_movements_projections_and_audit() -> None:
    admin = create_user(email="admin@example.test")
    gauze = create_material(sku="GAU-001", name="Марля", unit="м")
    gloves = create_material(sku="GLO-006", name="Рукавички", unit="пар")
    client = authenticated_client(admin)

    response = post_receipt(
        client,
        key="receipt-multi-001",
        comment="Перша поставка",
        lines=[
            {
                "material_id": str(gauze.pk),
                "lot_number": " gauze-24 ",
                "expires_on": None,
                "quantity": "12.5",
                "purchase_price_minor": 180,
                "supplier_name": " Медтехніка ",
            },
            {
                "material_id": str(gloves.pk),
                "lot_number": "g-114",
                "expires_on": (timezone.localdate() + timedelta(days=365)).isoformat(),
                "quantity": "40",
                "purchase_price_minor": 320,
            },
        ],
    )

    assert response.status_code == 201
    assert response.json()["kind"] == "RECEIPT"
    assert response.json()["status"] == "POSTED"
    assert response.json()["replayed"] is False
    assert len(response.json()["movements"]) == 2
    gauze_lot = MaterialLot.objects.get(material=gauze)
    gloves_lot = MaterialLot.objects.get(material=gloves)
    assert gauze_lot.lot_number == "GAUZE-24"
    assert gauze_lot.current_quantity == Decimal("12.500")
    assert gauze_lot.supplier_name == "Медтехніка"
    assert gloves_lot.current_quantity == Decimal("40.000")
    assert StockMovement.objects.filter(operation_id=response.json()["id"]).count() == 2
    detail = client.get(f"/api/v1/inventory/materials/{gauze.pk}")
    assert detail.json()["available_quantity"] == "12.500"
    event = AuditEvent.objects.get(action=AuditAction.INVENTORY_RECEIPT_POSTED)
    assert event.object_id == response.json()["id"]
    assert len(event.after["movements"]) == 2


@pytest.mark.django_db
def test_receipt_idempotency_replays_original_and_rejects_payload_mismatch() -> None:
    admin = create_user(email="admin@example.test")
    material = create_material(sku="CAP-001")
    client = authenticated_client(admin)
    line = {
        "material_id": str(material.pk),
        "lot_number": "LOT-A",
        "expires_on": None,
        "quantity": "5",
    }

    first = post_receipt(client, key="receipt-retry", lines=[line])
    replay = post_receipt(client, key="receipt-retry", lines=[line])
    mismatch = post_receipt(
        client,
        key="receipt-retry",
        lines=[{**line, "quantity": "6"}],
    )
    missing_key = client.post(
        "/api/v1/inventory/receipts",
        {"lines": [line]},
        format="json",
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["replayed"] is True
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert missing_key.status_code == 422
    assert missing_key.json()["code"] == "idempotency_key_required"
    assert MaterialLot.objects.get().current_quantity == Decimal("5")
    assert InventoryOperation.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.INVENTORY_RECEIPT_POSTED).count() == 1


@pytest.mark.django_db
def test_existing_lot_requires_confirmation_and_matching_details() -> None:
    admin = create_user(email="admin@example.test")
    material = create_material(sku="CAP-002")
    client = authenticated_client(admin)
    expiry = timezone.localdate() + timedelta(days=100)
    line = {
        "material_id": str(material.pk),
        "lot_number": "LOT-B",
        "expires_on": expiry.isoformat(),
        "quantity": "5",
        "purchase_price_minor": 250,
        "supplier_name": "ТОВ Постачальник",
    }
    assert post_receipt(client, key="receipt-original", lines=[line]).status_code == 201

    unconfirmed = post_receipt(client, key="receipt-unconfirmed", lines=[line])
    mismatch = post_receipt(
        client,
        key="receipt-mismatch",
        lines=[{**line, "allow_existing_lot": True, "expires_on": None}],
    )
    confirmed = post_receipt(
        client,
        key="receipt-confirmed",
        lines=[{**line, "allow_existing_lot": True, "quantity": "3"}],
    )

    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["code"] == "material_lot_already_exists"
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "material_lot_details_mismatch"
    assert confirmed.status_code == 201
    lot = MaterialLot.objects.get(material=material)
    assert lot.initial_quantity == Decimal("8")
    assert lot.current_quantity == Decimal("8")
    assert StockMovement.objects.filter(lot=lot).count() == 2


@pytest.mark.django_db
def test_manual_writeoff_locks_lots_updates_balances_and_audits() -> None:
    admin = create_user(email="admin@example.test")
    material = create_material(sku="CAP-003")
    first = create_lot(material=material, number="FIRST", quantity="7", expires_delta=-1)
    second = create_lot(material=material, number="SECOND", quantity="4")
    client = authenticated_client(admin)

    response = client.post(
        "/api/v1/inventory/write-offs",
        {
            "reason": "Утилізація",
            "comment": "Пошкоджене пакування",
            "lines": [
                {"lot_id": str(second.pk), "quantity": "1.5"},
                {"lot_id": str(first.pk), "quantity": "2"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="writeoff-001",
    )

    assert response.status_code == 201
    assert response.json()["kind"] == "MANUAL_WRITEOFF"
    assert response.json()["reason"] == "Утилізація"
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.current_quantity == Decimal("5")
    assert second.current_quantity == Decimal("2.5")
    assert sorted(item["quantity_delta"] for item in response.json()["movements"]) == [
        "-1.500",
        "-2.000",
    ]
    event = AuditEvent.objects.get(action=AuditAction.INVENTORY_MANUAL_WRITEOFF_POSTED)
    assert len(event.before["balances"]) == 2
    assert event.note == "Пошкоджене пакування"


@pytest.mark.django_db
def test_insufficient_writeoff_rolls_back_every_line() -> None:
    admin = create_user(email="admin@example.test")
    material = create_material(sku="CAP-004")
    first = create_lot(material=material, number="FIRST", quantity="5")
    second = create_lot(material=material, number="SECOND", quantity="1")
    client = authenticated_client(admin)

    response = client.post(
        "/api/v1/inventory/write-offs",
        {
            "reason": "Пошкодження",
            "lines": [
                {"lot_id": str(first.pk), "quantity": "2"},
                {"lot_id": str(second.pk), "quantity": "2"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="writeoff-overstock",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_stock"
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.current_quantity == Decimal("5")
    assert second.current_quantity == Decimal("1")
    assert InventoryOperation.objects.count() == 0
    assert StockMovement.objects.count() == 0
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_writeoffs_never_create_negative_stock() -> None:
    admins = [
        create_user(email="admin-one@example.test"),
        create_user(email="admin-two@example.test"),
    ]
    material = create_material(sku="CAP-005")
    lot = create_lot(material=material, number="RACE", quantity="5")
    barrier = Barrier(2)

    def write_off(index: int) -> int:
        close_old_connections()
        actor = User.objects.get(pk=admins[index].pk)
        client = authenticated_client(actor)
        barrier.wait(timeout=5)
        try:
            return client.post(
                "/api/v1/inventory/write-offs",
                {
                    "reason": "Конкурентний тест",
                    "lines": [{"lot_id": str(lot.pk), "quantity": "4"}],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=f"writeoff-race-{index}",
            ).status_code
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write_off, range(2)))

    assert sorted(results) == [201, 409]
    lot.refresh_from_db()
    assert lot.current_quantity == Decimal("1")
    assert InventoryOperation.objects.count() == 1
    assert StockMovement.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.RECEPTION, UserRole.PODOLOGIST])
def test_non_admin_cannot_post_inventory_operations(role: str) -> None:
    client = authenticated_client(create_user(email=f"{role}@example.test", role=role))

    assert (
        client.post(
            "/api/v1/inventory/receipts",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="forbidden-receipt",
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/inventory/write-offs",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="forbidden-writeoff",
        ).status_code
        == 403
    )


@pytest.mark.django_db(transaction=True)
def test_posted_operations_and_movements_are_append_only() -> None:
    admin = create_user(email="admin@example.test")
    material = create_material(sku="CAP-006")
    response = post_receipt(
        authenticated_client(admin),
        key="receipt-immutable",
        lines=[
            {
                "material_id": str(material.pk),
                "lot_number": "LOCKED",
                "quantity": "3",
            }
        ],
    )
    operation = InventoryOperation.objects.get(pk=response.json()["id"])
    movement = operation.movements.get()

    operation.comment = "Змінено"
    with pytest.raises(ImmutableInventoryRecordError):
        operation.save()
    with pytest.raises(ImmutableInventoryRecordError):
        movement.delete()
    with pytest.raises(DatabaseError), transaction.atomic():
        InventoryOperation.objects.filter(pk=operation.pk).update(comment="raw update")
    with pytest.raises(DatabaseError), transaction.atomic():
        StockMovement.objects.filter(pk=movement.pk).delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        StockMovement.objects.create(
            operation=operation,
            lot=movement.lot,
            quantity_delta=Decimal("0"),
            balance_after=movement.balance_after,
        )
