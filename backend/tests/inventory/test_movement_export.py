import csv
import re
from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.inventory import exports as inventory_exports
from apps.inventory.models import (
    InventoryOperation,
    InventoryOperationKind,
    Material,
    MaterialLot,
    StockMovement,
)

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str = UserRole.ADMIN) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="=Олена",
        last_name="Коваль",
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_movement(*, actor: User, suffix: str) -> StockMovement:
    material = Material.objects.create(
        sku=f"=EXP-{suffix}",
        name=f"+Матеріал {suffix}",
        category="Витратні матеріали",
        unit="шт.",
        minimum_quantity=Decimal("1"),
    )
    lot = MaterialLot.objects.create(
        material=material,
        lot_number=f"-LOT-{suffix}",
        received_on=timezone.localdate(),
        expires_on=timezone.localdate() + timedelta(days=90),
        initial_quantity=Decimal("5"),
        current_quantity=Decimal("3"),
        purchase_price_minor=250,
        supplier_name=f"@Постачальник {suffix}",
    )
    operation = InventoryOperation.objects.create(
        public_number=f"INV-EXP-{suffix}",
        kind=InventoryOperationKind.MANUAL_WRITEOFF,
        created_by=actor,
        idempotency_key=f"movement-export-{suffix}",
        payload_hash="a" * 64,
        reason='=HYPERLINK("https://example.invalid")',
        comment="  @SUM(1+1)",
    )
    return StockMovement.objects.create(
        operation=operation,
        lot=lot,
        quantity_delta=Decimal("-2"),
        balance_after=Decimal("3"),
    )


@pytest.mark.django_db
def test_filtered_movement_export_has_stable_safe_utf8_csv_contract() -> None:
    admin = create_user(email="export@example.test")
    movement = create_movement(actor=admin, suffix="001")
    create_movement(actor=create_user(email="other@example.test"), suffix="002")
    audit_count = AuditEvent.objects.count()

    response = authenticated_client(admin).get(
        "/api/v1/inventory/movements/export",
        {
            "search": movement.operation.public_number,
            "kind": InventoryOperationKind.MANUAL_WRITEOFF,
            "material_id": str(movement.lot.material_id),
            "actor": "export@",
            "date_from": timezone.localdate().isoformat(),
            "date_to": timezone.localdate().isoformat(),
        },
        HTTP_ACCEPT="text/csv",
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Cache-Control"] == "no-store"
    assert response["X-Export-Row-Count"] == "1"
    assert re.fullmatch(
        'attachment; filename="inventory-movements-\\d{8}-\\d{6}\\.csv"',
        response["Content-Disposition"],
    )
    assert response.content.startswith(b"\xef\xbb\xbf")
    reader = csv.DictReader(StringIO(response.content.decode("utf-8-sig"), newline=""))
    rows = list(reader)
    assert reader.fieldnames == list(inventory_exports.MOVEMENT_EXPORT_COLUMNS)
    assert len(rows) == 1
    row = rows[0]
    assert row["posted_at_local"] == timezone.localtime(movement.operation.posted_at).isoformat(
        timespec="seconds"
    )
    assert row["operation_number"] == "INV-EXP-001"
    assert row["operation_kind"] == InventoryOperationKind.MANUAL_WRITEOFF
    assert row["material_sku"] == "'=EXP-001"
    assert row["material_name"] == "'+Матеріал 001"
    assert row["lot_number"] == "'-LOT-001"
    assert row["supplier_name"] == "'@Постачальник 001"
    assert row["quantity_delta"] == "-2.000"
    assert row["balance_after"] == "3.000"
    assert row["actor_name"] == "'=Олена Коваль"
    assert row["reason"].startswith("'=")
    assert row["comment"] == "'  @SUM(1+1)"
    assert AuditEvent.objects.count() == audit_count


def test_spreadsheet_safe_text_removes_nul_without_database_fixture() -> None:
    assert inventory_exports.spreadsheet_safe_text("safe\x00value") == "safevalue"


@pytest.mark.django_db
def test_empty_movement_export_returns_header_only() -> None:
    client = authenticated_client(create_user(email="empty-export@example.test"))

    response = client.get("/api/v1/inventory/movements/export", {"search": "missing-operation"})

    assert response.status_code == 200
    assert response["X-Export-Row-Count"] == "0"
    rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
    assert rows == [list(inventory_exports.MOVEMENT_EXPORT_COLUMNS)]


@pytest.mark.django_db
def test_movement_export_rejects_oversized_result_without_partial_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = create_user(email="large-export@example.test")
    create_movement(actor=admin, suffix="101")
    create_movement(actor=admin, suffix="102")
    monkeypatch.setattr(inventory_exports, "MOVEMENT_EXPORT_ROW_LIMIT", 1)

    response = authenticated_client(admin).get("/api/v1/inventory/movements/export")

    assert response.status_code == 422
    assert response.json()["code"] == "export_too_large"
    assert response["Content-Type"].startswith("application/json")


@pytest.mark.django_db
def test_movement_export_rejects_invalid_range_and_cursor() -> None:
    client = authenticated_client(create_user(email="range-export@example.test"))

    too_wide = client.get(
        "/api/v1/inventory/movements/export",
        {"date_from": "2025-01-01", "date_to": "2026-01-02"},
    )
    inverted = client.get(
        "/api/v1/inventory/movements/export",
        {"date_from": "2026-07-23", "date_to": "2026-07-22"},
    )
    cursor = client.get("/api/v1/inventory/movements/export", {"cursor": "opaque"})

    assert too_wide.status_code == 422
    assert "366" in too_wide.json()["fields"]["date_to"][0]
    assert inverted.status_code == 422
    assert cursor.status_code == 422
    assert cursor.json()["code"] == "export_cursor_not_supported"


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.RECEPTION, UserRole.PODOLOGIST])
def test_non_admin_cannot_export_inventory_movements(role: str) -> None:
    client = authenticated_client(create_user(email=f"{role}-export@example.test", role=role))

    assert client.get("/api/v1/inventory/movements/export").status_code == 403


@pytest.mark.django_db
def test_anonymous_cannot_export_inventory_movements() -> None:
    assert APIClient().get("/api/v1/inventory/movements/export").status_code == 401
