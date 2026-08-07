from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.inventory.models import (
    Material,
    MaterialLot,
    MaterialLotIdentityImmutableError,
    MaterialUnitImmutableError,
)

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_material(
    *,
    sku: str = "KAP-001",
    name: str = "Каполін, 1 см",
    category: str = "Перев’язувальні",
    unit: str = "шт.",
    minimum_quantity: Decimal = Decimal("20"),
    is_active: bool = True,
) -> Material:
    return Material.objects.create(
        sku=sku,
        name=name,
        category=category,
        unit=unit,
        minimum_quantity=minimum_quantity,
        is_active=is_active,
    )


def create_lot(
    *,
    material: Material,
    number: str,
    current: Decimal,
    expires_delta: int | None,
    received_delta: int = -10,
) -> MaterialLot:
    today = timezone.localdate()
    return MaterialLot.objects.create(
        material=material,
        lot_number=number,
        received_on=today + timedelta(days=received_delta),
        expires_on=None if expires_delta is None else today + timedelta(days=expires_delta),
        initial_quantity=max(current, Decimal("1")),
        current_quantity=current,
        purchase_price_minor=320,
        supplier_name="ТОВ Медтехніка",
    )


@pytest.mark.django_db
def test_admin_searches_filters_and_receives_stock_projections():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    low = create_material()
    create_lot(material=low, number="n-042 / 01", current=Decimal("12"), expires_delta=90)
    healthy = create_material(
        sku="GLO-006",
        name="Рукавички нітрилові",
        category="Захист",
        unit="пар",
        minimum_quantity=Decimal("5"),
    )
    create_lot(material=healthy, number="G-114", current=Decimal("40"), expires_delta=365)
    create_material(sku="OLD-1", name="Архівний засіб", is_active=False)
    client = authenticated_client(admin)

    listed = client.get("/api/v1/inventory/materials")
    search = client.get("/api/v1/inventory/materials", {"search": "kap-001"})
    category = client.get("/api/v1/inventory/materials", {"category": "захист"})
    low_only = client.get("/api/v1/inventory/materials", {"stock_status": "low"})
    inactive = client.get("/api/v1/inventory/materials", {"status": "inactive"})

    assert listed.status_code == 200
    assert len(listed.json()["materials"]) == 3
    assert [item["id"] for item in search.json()["materials"]] == [str(low.pk)]
    assert [item["id"] for item in category.json()["materials"]] == [str(healthy.pk)]
    assert [item["id"] for item in low_only.json()["materials"]] == [str(low.pk)]
    assert [item["sku"] for item in inactive.json()["materials"]] == ["OLD-1"]
    projection = search.json()["materials"][0]
    assert projection["total_quantity"] == "12.000"
    assert projection["available_quantity"] == "12.000"
    assert projection["stock_status"] == "low"
    assert projection["lots_count"] == 1


@pytest.mark.django_db
def test_lot_projection_orders_usable_lots_by_fefo_and_excludes_expired_stock():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    material = create_material(minimum_quantity=Decimal("1"))
    late = create_lot(material=material, number="LATE", current=Decimal("7"), expires_delta=45)
    first = create_lot(material=material, number="FIRST", current=Decimal("3"), expires_delta=10)
    expired = create_lot(
        material=material, number="EXPIRED", current=Decimal("5"), expires_delta=-1
    )
    no_expiry = create_lot(
        material=material, number="NO-EXPIRY", current=Decimal("2"), expires_delta=None
    )
    empty = create_lot(material=material, number="EMPTY", current=Decimal("0"), expires_delta=5)
    client = authenticated_client(admin)

    detail = client.get(f"/api/v1/inventory/materials/{material.pk}")
    response = client.get(f"/api/v1/inventory/materials/{material.pk}/lots")

    assert detail.status_code == 200
    assert detail.json()["total_quantity"] == "17.000"
    assert detail.json()["available_quantity"] == "12.000"
    assert detail.json()["nearest_expiry"] == first.expires_on.isoformat()
    assert detail.json()["stock_status"] == "expired"
    assert response.status_code == 200
    lots = response.json()["lots"]
    assert [item["id"] for item in lots[:3]] == [str(first.pk), str(late.pk), str(no_expiry.pk)]
    assert [item["fefo_rank"] for item in lots[:3]] == [1, 2, 3]
    expired_payload = next(item for item in lots if item["id"] == str(expired.pk))
    empty_payload = next(item for item in lots if item["id"] == str(empty.pk))
    assert expired_payload["status"] == "expired"
    assert expired_payload["is_usable"] is False
    assert empty_payload["status"] == "empty"
    assert empty_payload["fefo_rank"] is None


@pytest.mark.django_db
def test_admin_create_update_deactivate_and_audit_material():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)

    created = client.post(
        "/api/v1/inventory/materials",
        {
            "sku": " ant-014 ",
            "name": "  Octenisept, 250 мл ",
            "category": " Антисептики ",
            "unit": " мл ",
            "minimum_quantity": "1000",
        },
        format="json",
    )
    updated = client.patch(
        f"/api/v1/inventory/materials/{created.json()['id']}",
        {"minimum_quantity": "750", "version": created.json()["version"]},
        format="json",
    )
    deactivated = client.patch(
        f"/api/v1/inventory/materials/{created.json()['id']}",
        {"is_active": False, "version": updated.json()["version"]},
        format="json",
    )

    assert created.status_code == 201
    assert created.json()["sku"] == "ANT-014"
    assert created.json()["name"] == "Octenisept, 250 мл"
    assert updated.status_code == 200
    assert updated.json()["minimum_quantity"] == "750.000"
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert list(AuditEvent.objects.order_by("occurred_at").values_list("action", flat=True)) == [
        AuditAction.MATERIAL_CREATED,
        AuditAction.MATERIAL_UPDATED,
        AuditAction.MATERIAL_DEACTIVATED,
    ]


@pytest.mark.django_db
def test_duplicate_stale_and_unit_immutability_conflicts_preserve_material():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    material = create_material()
    create_lot(material=material, number="LOT-1", current=Decimal("4"), expires_delta=90)
    client = authenticated_client(admin)

    duplicate = client.post(
        "/api/v1/inventory/materials",
        {
            "sku": "kap-001",
            "name": "Дублікат",
            "category": "Інше",
            "unit": "шт.",
            "minimum_quantity": "0",
        },
        format="json",
    )
    unit = client.patch(
        f"/api/v1/inventory/materials/{material.pk}",
        {"unit": "уп.", "version": material.version},
        format="json",
    )
    updated = client.patch(
        f"/api/v1/inventory/materials/{material.pk}",
        {"name": "Каполін оновлений", "version": material.version},
        format="json",
    )
    stale = client.patch(
        f"/api/v1/inventory/materials/{material.pk}",
        {"category": "Втрачена зміна", "version": material.version},
        format="json",
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "material_sku_already_exists"
    assert unit.status_code == 409
    assert unit.json()["code"] == "material_unit_immutable"
    assert updated.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"
    material.refresh_from_db()
    assert material.unit == "шт."
    assert material.category == "Перев’язувальні"


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.RECEPTION, UserRole.PODOLOGIST])
def test_non_admin_cannot_read_or_mutate_inventory(role: str):
    user = create_user(email=f"{role}@example.test", role=role)
    material = create_material()
    client = authenticated_client(user)

    assert client.get("/api/v1/inventory/materials").status_code == 403
    assert client.get(f"/api/v1/inventory/materials/{material.pk}").status_code == 403
    assert client.get(f"/api/v1/inventory/materials/{material.pk}/lots").status_code == 403
    assert client.post("/api/v1/inventory/materials", {}, format="json").status_code == 403
    assert (
        client.patch(f"/api/v1/inventory/materials/{material.pk}", {}, format="json").status_code
        == 403
    )


@pytest.mark.django_db
def test_inventory_endpoints_require_authentication_and_do_not_delete():
    material = create_material()
    anonymous = APIClient()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)

    assert anonymous.get("/api/v1/inventory/materials").status_code == 401
    assert anonymous.get(f"/api/v1/inventory/materials/{material.pk}").status_code == 401
    assert (
        authenticated_client(admin).delete(f"/api/v1/inventory/materials/{material.pk}").status_code
        == 405
    )


@pytest.mark.django_db(transaction=True)
def test_database_and_models_protect_catalog_and_lot_identity():
    material = create_material()
    lot = create_lot(material=material, number="lot-a", current=Decimal("2"), expires_delta=90)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_material(sku="kap-001", name="Дублікат")
    with pytest.raises(IntegrityError), transaction.atomic():
        create_lot(material=material, number="LOT-A", current=Decimal("1"), expires_delta=120)
    with pytest.raises(IntegrityError), transaction.atomic():
        create_lot(material=material, number="NEGATIVE", current=Decimal("-1"), expires_delta=90)

    material.unit = "пак."
    with pytest.raises(MaterialUnitImmutableError):
        material.save()
    lot.lot_number = "RENAMED"
    with pytest.raises(MaterialLotIdentityImmutableError):
        lot.save()


@pytest.mark.django_db
def test_deferred_material_lot_fields_do_not_recurse_and_still_protect_identity():
    material = create_material()
    lot = create_lot(
        material=material,
        number="LOT-DEFERRED",
        current=Decimal("2"),
        expires_delta=90,
    )

    deferred_lot = MaterialLot.objects.only("id").get(pk=lot.pk)
    assert deferred_lot.pk == lot.pk

    deferred_lot.lot_number = "RENAMED"
    with pytest.raises(MaterialLotIdentityImmutableError):
        deferred_lot.save()

    assert MaterialLot.objects.filter(pk=lot.pk).delete()[0] == 1


@pytest.mark.django_db
def test_case_variant_category_reuses_existing_spelling_and_new_one_is_kept():
    admin = create_user(email="category-admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    create_material(sku="KAP-001", name="Каполін, 1 см", category="Перев’язувальні")

    reused = client.post(
        "/api/v1/inventory/materials",
        {
            "sku": "KAP-002",
            "name": "Каполін, 2 см",
            "category": "  перев’язувальні  ",
            "unit": "шт.",
            "minimum_quantity": "5",
        },
        format="json",
    )
    added = client.post(
        "/api/v1/inventory/materials",
        {
            "sku": "ANT-014",
            "name": "Octenisept, 250 мл",
            "category": "Антисептики",
            "unit": "мл",
            "minimum_quantity": "1000",
        },
        format="json",
    )

    # A case-only variant must not become a second category.
    assert reused.status_code == 201, reused.json()
    assert reused.json()["category"] == "Перев’язувальні"
    # A genuinely new name is stored as typed.
    assert added.status_code == 201, added.json()
    assert added.json()["category"] == "Антисептики"
    assert sorted(set(Material.objects.values_list("category", flat=True))) == [
        "Антисептики",
        "Перев’язувальні",
    ]


@pytest.mark.django_db
def test_case_variant_category_is_canonicalised_on_update():
    admin = create_user(email="category-update@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    create_material(sku="KAP-001", name="Каполін, 1 см", category="Перев’язувальні")
    target = create_material(sku="GLV-001", name="Рукавички", category="Захист")

    response = client.patch(
        f"/api/v1/inventory/materials/{target.pk}",
        {"category": "ПЕРЕВ’ЯЗУВАЛЬНІ", "version": target.version},
        format="json",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["category"] == "Перев’язувальні"
    assert sorted(set(Material.objects.values_list("category", flat=True))) == [
        "Перев’язувальні",
    ]
