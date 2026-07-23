from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator

from apps.accounts.models import UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import Service
from apps.inventory.models import (
    InventoryOperation,
    Material,
    MaterialLot,
    StockMovement,
)
from apps.visits.models import Visit, VisitMaterialLine, VisitServiceLine
from tests.scheduling.test_create_appointment import authenticated_client, create_user
from tests.visits.test_visit_start_and_draft import arrived_appointment, start


def extra_service(*, code: str = "EXTRA", active: bool = True) -> Service:
    return Service.objects.create(
        code=code,
        name="Додаткова обробка",
        duration_minutes=20,
        price_minor=45_00,
        color="#0F766E",
        is_active=active,
    )


def material_with_lot(
    *,
    sku: str = "MAT-001",
    active: bool = True,
    quantity: str = "5.000",
    expires_in_days: int | None = 60,
    lot_number: str = "LOT-001",
) -> tuple[Material, MaterialLot]:
    material = Material.objects.create(
        sku=sku,
        name=f"Матеріал {sku}",
        category="Перев’язка",
        unit="шт",
        minimum_quantity=Decimal("1.000"),
        is_active=active,
    )
    expires_on = (
        None if expires_in_days is None else timezone.localdate() + timedelta(days=expires_in_days)
    )
    lot = MaterialLot.objects.create(
        material=material,
        lot_number=lot_number,
        received_on=timezone.localdate() - timedelta(days=5),
        expires_on=expires_on,
        initial_quantity=Decimal(quantity),
        current_quantity=Decimal(quantity),
        purchase_price_minor=1234,
        supplier_name="Private supplier",
    )
    return material, lot


@pytest.mark.django_db
def test_start_seeds_primary_service_snapshot_and_total() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)

    response = start(authenticated_client(admin), appointment)

    assert response.status_code == 201
    assert response.json()["service_lines"] == [
        {
            "id": str(VisitServiceLine.objects.get().pk),
            "service_id": str(appointment.service_id),
            "service_code": appointment.service.code,
            "service_name": appointment.service_name_snapshot,
            "duration_minutes": appointment.duration_minutes,
            "price_minor": appointment.service.price_minor,
            "quantity": 1,
            "is_primary": True,
            "line_total_minor": appointment.service.price_minor,
        }
    ]
    assert response.json()["material_lines"] == []
    assert response.json()["services_total_minor"] == appointment.service.price_minor


@pytest.mark.django_db
def test_service_draft_replaces_lines_deduplicates_in_ui_contract_and_keeps_snapshots() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    added = extra_service()
    client = authenticated_client(admin)

    saved = client.put(
        f"/api/v1/visits/{visit_id}",
        {
            "version": 1,
            "service_lines": [
                {"service_id": str(appointment.service_id), "quantity": 2},
                {"service_id": str(added.pk), "quantity": 3},
            ],
        },
        format="json",
    )
    added.name = "Нова назва каталогу"
    added.price_minor = 99_00
    added.save(update_fields=("name", "price_minor", "updated_at"))
    reloaded = client.get(f"/api/v1/visits/{visit_id}")

    assert saved.status_code == 200
    assert saved.json()["version"] == 2
    assert [line["quantity"] for line in saved.json()["service_lines"]] == [2, 3]
    assert saved.json()["services_total_minor"] == (appointment.service.price_minor * 2 + 45_00 * 3)
    added_line = next(
        line for line in reloaded.json()["service_lines"] if line["service_id"] == str(added.pk)
    )
    assert added_line["service_name"] == "Додаткова обробка"
    assert added_line["price_minor"] == 45_00
    assert VisitServiceLine.objects.filter(visit_id=visit_id).count() == 2


@pytest.mark.django_db
def test_service_draft_rejects_duplicates_and_new_inactive_service_atomically() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    inactive = extra_service(code="INACTIVE", active=False)
    client = authenticated_client(admin)
    url = f"/api/v1/visits/{visit_id}"

    duplicate = client.put(
        url,
        {
            "version": 1,
            "service_lines": [
                {"service_id": str(appointment.service_id), "quantity": 1},
                {"service_id": str(appointment.service_id), "quantity": 2},
            ],
        },
        format="json",
    )
    unavailable = client.put(
        url,
        {
            "version": 1,
            "service_lines": [{"service_id": str(inactive.pk), "quantity": 1}],
        },
        format="json",
    )

    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == "visit_service_duplicate"
    assert unavailable.status_code == 422
    assert unavailable.json()["code"] == "visit_service_inactive"
    assert Visit.objects.get(pk=visit_id).version == 1
    assert VisitServiceLine.objects.filter(visit_id=visit_id).count() == 1
    assert not AuditEvent.objects.filter(action=AuditAction.VISIT_DRAFT_SAVED).exists()


@pytest.mark.django_db
def test_material_picker_is_visit_scoped_fefo_and_redacts_inventory_costs() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    material, later = material_with_lot(quantity="4.000", expires_in_days=None)
    sooner = MaterialLot.objects.create(
        material=material,
        lot_number="LOT-FEFO",
        received_on=timezone.localdate(),
        expires_on=timezone.localdate() + timedelta(days=10),
        initial_quantity=Decimal("3.000"),
        current_quantity=Decimal("3.000"),
        purchase_price_minor=9999,
        supplier_name="Hidden supplier",
    )
    material_with_lot(sku="EXPIRED", expires_in_days=-1)
    material_with_lot(sku="INACTIVE", active=False)
    url = f"/api/v1/visits/{visit_id}/material-options?search=MAT-001"

    response = authenticated_client(admin).get(url)
    reception_response = authenticated_client(reception).get(url)
    foreign_response = authenticated_client(foreign).get(url)

    assert response.status_code == 200
    assert response.json() == {
        "materials": [
            {
                "id": str(material.pk),
                "sku": "MAT-001",
                "name": "Матеріал MAT-001",
                "unit": "шт",
                "available_quantity": "7.000",
                "lots": [
                    {
                        "id": str(sooner.pk),
                        "lot_number": "LOT-FEFO",
                        "expires_on": sooner.expires_on.isoformat(),
                        "current_quantity": "3.000",
                        "fefo_rank": 1,
                    },
                    {
                        "id": str(later.pk),
                        "lot_number": "LOT-001",
                        "expires_on": None,
                        "current_quantity": "4.000",
                        "fefo_rank": 2,
                    },
                ],
            }
        ]
    }
    assert "purchase_price_minor" not in str(response.json())
    assert "supplier" not in str(response.json()).lower()
    assert reception_response.status_code == 403
    assert foreign_response.status_code == 404


@pytest.mark.django_db
def test_material_draft_uses_snapshot_current_projection_and_has_no_stock_side_effects() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    material, lot = material_with_lot(quantity="3.000")
    client = authenticated_client(admin)

    saved = client.put(
        f"/api/v1/visits/{visit_id}",
        {
            "version": 1,
            "material_lines": [{"lot_id": str(lot.pk), "quantity": "2.000"}],
        },
        format="json",
    )
    material.name = "Перейменований матеріал"
    material.save(update_fields=("name", "updated_at"))
    lot.current_quantity = Decimal("1.000")
    lot.save(update_fields=("current_quantity",))
    reloaded = client.get(f"/api/v1/visits/{visit_id}")

    assert saved.status_code == 200
    assert saved.json()["material_lines"][0]["quantity"] == "2.000"
    assert saved.json()["material_lines"][0]["is_available"] is True
    line = reloaded.json()["material_lines"][0]
    assert line["material_name"] == "Матеріал MAT-001"
    assert line["available_quantity"] == "1.000"
    assert line["is_available"] is False
    assert InventoryOperation.objects.count() == 0
    assert StockMovement.objects.count() == 0
    event = AuditEvent.objects.get(action=AuditAction.VISIT_DRAFT_SAVED)
    assert event.after["material_lines"][0]["quantity"] == "2.000"


@pytest.mark.django_db
def test_material_draft_rejects_duplicate_unusable_and_insufficient_lots() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    _, usable = material_with_lot(quantity="2.000")
    _, expired = material_with_lot(sku="EXP", expires_in_days=-1, lot_number="LOT-EXP")
    _, inactive = material_with_lot(sku="OFF", active=False, lot_number="LOT-OFF")
    client = authenticated_client(admin)
    url = f"/api/v1/visits/{visit_id}"

    duplicate = client.put(
        url,
        {
            "version": 1,
            "material_lines": [
                {"lot_id": str(usable.pk), "quantity": "0.500"},
                {"lot_id": str(usable.pk), "quantity": "0.500"},
            ],
        },
        format="json",
    )
    expired_response = client.put(
        url,
        {
            "version": 1,
            "material_lines": [{"lot_id": str(expired.pk), "quantity": "0.500"}],
        },
        format="json",
    )
    inactive_response = client.put(
        url,
        {
            "version": 1,
            "material_lines": [{"lot_id": str(inactive.pk), "quantity": "0.500"}],
        },
        format="json",
    )
    insufficient = client.put(
        url,
        {
            "version": 1,
            "material_lines": [{"lot_id": str(usable.pk), "quantity": "2.001"}],
        },
        format="json",
    )

    assert duplicate.json()["code"] == "visit_material_lot_duplicate"
    assert expired_response.json()["code"] == "visit_material_lot_unusable"
    assert inactive_response.json()["code"] == "visit_material_lot_unusable"
    assert insufficient.json()["code"] == "visit_material_quantity_insufficient"
    assert {
        duplicate.status_code,
        expired_response.status_code,
        inactive_response.status_code,
        insufficient.status_code,
    } == {422}
    assert Visit.objects.get(pk=visit_id).version == 1
    assert VisitMaterialLine.objects.count() == 0
    assert not AuditEvent.objects.filter(action=AuditAction.VISIT_DRAFT_SAVED).exists()


@pytest.mark.django_db
def test_line_draft_rolls_back_all_replacements_when_audit_fails() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    visit_id = start(authenticated_client(admin), appointment).json()["id"]
    added = extra_service()
    _, lot = material_with_lot()

    with patch("apps.visits.services.record_audit_event", side_effect=RuntimeError("audit down")):
        response = authenticated_client(admin).put(
            f"/api/v1/visits/{visit_id}",
            {
                "version": 1,
                "service_lines": [{"service_id": str(added.pk), "quantity": 2}],
                "material_lines": [{"lot_id": str(lot.pk), "quantity": "1.000"}],
            },
            format="json",
        )

    assert response.status_code == 500
    assert Visit.objects.get(pk=visit_id).version == 1
    assert list(
        VisitServiceLine.objects.filter(visit_id=visit_id).values_list("service_id", flat=True)
    ) == [appointment.service_id]
    assert VisitMaterialLine.objects.count() == 0
    assert not AuditEvent.objects.filter(action=AuditAction.VISIT_DRAFT_SAVED).exists()


@pytest.mark.django_db
def test_openapi_exposes_visit_line_draft_and_scoped_material_picker() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    draft_schema = schema["components"]["schemas"]["VisitDraftUpdateRequest"]
    response_schema = schema["components"]["schemas"]["VisitResponse"]
    material_path = schema["paths"]["/api/v1/visits/{visit_id}/material-options"]["get"]

    assert draft_schema["properties"]["service_lines"]["type"] == "array"
    assert draft_schema["properties"]["material_lines"]["type"] == "array"
    assert response_schema["properties"]["services_total_minor"]["type"] == "integer"
    assert material_path["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisitMaterialOptionList"
    }
