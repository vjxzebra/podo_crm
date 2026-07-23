from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.inventory.models import Material, MaterialLot, Supplier

PASSWORD = "correct horse battery staple"  # noqa: S105
MIGRATION_OLD = [("inventory", "0006_global_search_indexes")]
MIGRATION_NEW = [("inventory", "0007_supplier_directory")]


def create_user(*, email: str, role: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_material() -> Material:
    return Material.objects.create(
        sku="SUP-TEST",
        name="Матеріал постачальника",
        category="Тест",
        unit="шт.",
        minimum_quantity=Decimal("1"),
    )


@pytest.mark.django_db
def test_admin_creates_filters_updates_and_audits_supplier() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)

    created = client.post(
        "/api/v1/inventory/suppliers",
        {
            "name": "  Podology Market  ",
            "contact_name": "  Олена Коваль  ",
            "phone": "  +380 67 123 45 67  ",
            "email": "  SALES@EXAMPLE.TEST  ",
            "address": "  Київ, вул. Тестова, 1  ",
            "note": "  Доставка щовівторка  ",
        },
        format="json",
    )
    supplier_id = created.json()["id"]
    listed = client.get("/api/v1/inventory/suppliers", {"search": "sales@"})
    deactivated = client.patch(
        f"/api/v1/inventory/suppliers/{supplier_id}",
        {"is_active": False, "version": created.json()["version"]},
        format="json",
    )
    inactive = client.get("/api/v1/inventory/suppliers", {"status": "inactive"})

    assert created.status_code == 201
    assert created.json()["name"] == "Podology Market"
    assert created.json()["contact_name"] == "Олена Коваль"
    assert created.json()["email"] == "sales@example.test"
    assert created.json()["lots_count"] == 0
    assert [item["id"] for item in listed.json()["suppliers"]] == [supplier_id]
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert [item["id"] for item in inactive.json()["suppliers"]] == [supplier_id]
    assert list(AuditEvent.objects.order_by("occurred_at").values_list("action", flat=True)) == [
        AuditAction.SUPPLIER_CREATED,
        AuditAction.SUPPLIER_DEACTIVATED,
    ]


@pytest.mark.django_db
def test_supplier_duplicate_stale_validation_and_no_delete() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    supplier = Supplier.objects.create(name="Медтехніка")
    client = authenticated_client(admin)

    duplicate = client.post(
        "/api/v1/inventory/suppliers",
        {"name": "медТЕХНІКА"},
        format="json",
    )
    updated = client.patch(
        f"/api/v1/inventory/suppliers/{supplier.pk}",
        {"contact_name": "Ірина", "version": supplier.version},
        format="json",
    )
    stale = client.patch(
        f"/api/v1/inventory/suppliers/{supplier.pk}",
        {"phone": "+380", "version": supplier.version},
        format="json",
    )
    invalid_email = client.patch(
        f"/api/v1/inventory/suppliers/{supplier.pk}",
        {"email": "not-an-email", "version": updated.json()["version"]},
        format="json",
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "supplier_name_already_exists"
    assert updated.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"
    assert invalid_email.status_code == 422
    assert client.delete(f"/api/v1/inventory/suppliers/{supplier.pk}").status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.RECEPTION, UserRole.PODOLOGIST])
def test_supplier_directory_is_admin_only(role: str) -> None:
    user = create_user(email=f"{role}@example.test", role=role)
    supplier = Supplier.objects.create(name="Закритий довідник")
    client = authenticated_client(user)

    assert client.get("/api/v1/inventory/suppliers").status_code == 403
    assert client.get(f"/api/v1/inventory/suppliers/{supplier.pk}").status_code == 403
    assert client.post("/api/v1/inventory/suppliers", {}, format="json").status_code == 403
    assert (
        client.patch(f"/api/v1/inventory/suppliers/{supplier.pk}", {}, format="json").status_code
        == 403
    )


@pytest.mark.django_db
def test_supplier_directory_requires_authentication_and_audit_failure_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anonymous = APIClient()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)

    assert anonymous.get("/api/v1/inventory/suppliers").status_code == 401

    def fail_audit(**kwargs: object) -> None:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.inventory.services.record_audit_event", fail_audit)
    response = authenticated_client(admin).post(
        "/api/v1/inventory/suppliers",
        {"name": "Має відкотитися"},
        format="json",
    )
    assert response.status_code == 500
    assert not Supplier.objects.filter(name="Має відкотитися").exists()


@pytest.mark.django_db
def test_receipt_uses_active_supplier_identity_and_preserves_name_snapshot() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    material = create_material()
    supplier = Supplier.objects.create(name="Podology Market")
    client = authenticated_client(admin)
    line = {
        "material_id": str(material.pk),
        "lot_number": "SUP-LOT-1",
        "quantity": "5",
        "purchase_price_minor": 250,
        "supplier_id": str(supplier.pk),
    }

    posted = client.post(
        "/api/v1/inventory/receipts",
        {"received_on": timezone.localdate().isoformat(), "comment": "", "lines": [line]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="supplier-receipt-1",
    )
    lot = MaterialLot.objects.get(material=material)
    supplier.name = "Нова назва"
    supplier.save(update_fields=("name",))

    assert posted.status_code == 201
    assert lot.supplier_id == supplier.pk
    assert lot.supplier_name == "Podology Market"
    assert posted.json()["movements"][0]["supplier_id"] == str(supplier.pk)
    assert posted.json()["movements"][0]["supplier_name"] == "Podology Market"


@pytest.mark.django_db
def test_receipt_rejects_inactive_missing_mixed_and_mismatched_supplier() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    material = create_material()
    active = Supplier.objects.create(name="Активний")
    inactive = Supplier.objects.create(name="Неактивний", is_active=False)
    lot = MaterialLot.objects.create(
        material=material,
        lot_number="EXISTING",
        received_on=timezone.localdate(),
        expires_on=None,
        initial_quantity=Decimal("2"),
        current_quantity=Decimal("2"),
        purchase_price_minor=100,
        supplier=active,
        supplier_name=active.name,
    )
    client = authenticated_client(admin)

    def post(key: str, payload: dict[str, object]):
        return client.post(
            "/api/v1/inventory/receipts",
            {"received_on": timezone.localdate().isoformat(), "comment": "", "lines": [payload]},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    base: dict[str, object] = {
        "material_id": str(material.pk),
        "lot_number": "NEW",
        "quantity": "1",
    }
    inactive_response = post("supplier-inactive", {**base, "supplier_id": str(inactive.pk)})
    missing_response = post(
        "supplier-missing",
        {**base, "supplier_id": "00000000-0000-0000-0000-000000000001"},
    )
    mixed_response = post(
        "supplier-mixed",
        {**base, "supplier_id": str(active.pk), "supplier_name": "Legacy"},
    )
    mismatch_response = post(
        "supplier-mismatch",
        {
            **base,
            "lot_number": lot.lot_number,
            "purchase_price_minor": lot.purchase_price_minor,
            "supplier_id": str(inactive.pk),
            "allow_existing_lot": True,
        },
    )

    assert inactive_response.status_code == 409
    assert inactive_response.json()["code"] == "supplier_inactive"
    assert missing_response.status_code == 422
    assert missing_response.json()["code"] == "supplier_not_found"
    assert mixed_response.status_code == 422
    assert "lines.0.non_field_errors" in mixed_response.json()["fields"]
    assert mismatch_response.status_code == 409
    assert mismatch_response.json()["code"] == "supplier_inactive"
    lot.refresh_from_db()
    assert lot.current_quantity == Decimal("2")


@pytest.mark.django_db(transaction=True)
def test_migration_links_case_insensitive_legacy_supplier_snapshots() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_OLD)
    try:
        old_apps = executor.loader.project_state(MIGRATION_OLD).apps
        OldMaterial = old_apps.get_model("inventory", "Material")
        OldMaterialLot = old_apps.get_model("inventory", "MaterialLot")
        first_material = OldMaterial.objects.create(
            sku="LEGACY-1",
            name="Legacy one",
            category="Legacy",
            unit="шт.",
            minimum_quantity=0,
        )
        second_material = OldMaterial.objects.create(
            sku="LEGACY-2",
            name="Legacy two",
            category="Legacy",
            unit="шт.",
            minimum_quantity=0,
        )
        first = OldMaterialLot.objects.create(
            material=first_material,
            lot_number="OLD-1",
            received_on=timezone.localdate(),
            initial_quantity=1,
            current_quantity=1,
            supplier_name="Медтехніка",
        )
        second = OldMaterialLot.objects.create(
            material=second_material,
            lot_number="OLD-2",
            received_on=timezone.localdate(),
            initial_quantity=1,
            current_quantity=1,
            supplier_name="медтехніка",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_NEW)
        new_apps = executor.loader.project_state(MIGRATION_NEW).apps
        NewSupplier = new_apps.get_model("inventory", "Supplier")
        NewMaterialLot = new_apps.get_model("inventory", "MaterialLot")
        migrated_first = NewMaterialLot.objects.get(pk=first.pk)
        migrated_second = NewMaterialLot.objects.get(pk=second.pk)

        assert NewSupplier.objects.count() == 1
        assert migrated_first.supplier_id == migrated_second.supplier_id
        assert migrated_first.supplier_name == "Медтехніка"
        assert migrated_second.supplier_name == "медтехніка"
    finally:
        MigrationExecutor(connection).migrate(MIGRATION_NEW)
