from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.inventory.models import (
    ImmutableInventoryRecordError,
    InventoryOperation,
    InventoryOperationKind,
    Material,
    MaterialLot,
    StockMovement,
    Stocktake,
    StocktakeLine,
    StocktakeStatus,
)

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str = UserRole.ADMIN) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="Олена",
        last_name="Коваль",
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_lot(
    *,
    sku: str,
    number: str,
    quantity: str,
    price_minor: int | None = 250,
) -> MaterialLot:
    material = Material.objects.create(
        sku=sku,
        name=f"Матеріал {sku}",
        category="Витратні матеріали",
        unit="шт.",
        minimum_quantity=Decimal("2"),
    )
    return MaterialLot.objects.create(
        material=material,
        lot_number=number,
        received_on=timezone.localdate(),
        expires_on=timezone.localdate() + timedelta(days=90),
        initial_quantity=max(Decimal(quantity), Decimal("1")),
        current_quantity=Decimal(quantity),
        purchase_price_minor=price_minor,
        supplier_name="ТОВ Постачальник",
    )


def create_stocktake(
    client: APIClient,
    *,
    key: str,
    lines: list[dict[str, str]],
    comment: str = "",
):
    return client.post(
        "/api/v1/inventory/stocktakes",
        {"comment": comment, "lines": lines},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def post_stocktake(client: APIClient, *, stocktake_id: str, key: str):
    return client.post(
        f"/api/v1/inventory/stocktakes/{stocktake_id}/post",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


@pytest.mark.django_db
def test_stocktake_preview_and_draft_capture_authoritative_snapshots() -> None:
    admin = create_user(email="admin@example.test")
    priced = create_lot(sku="CAP-101", number="A-01", quantity="5", price_minor=300)
    unpriced = create_lot(sku="CAP-102", number="B-01", quantity="2", price_minor=None)
    client = authenticated_client(admin)

    preview = client.get("/api/v1/inventory/stocktakes/preview")
    response = create_stocktake(
        client,
        key="stocktake-draft-001",
        comment=" Щомісячний підрахунок ",
        lines=[
            {"lot_id": str(priced.pk), "actual_quantity": "7"},
            {"lot_id": str(unpriced.pk), "actual_quantity": "1"},
        ],
    )

    assert preview.status_code == 200
    assert [item["system_quantity"] for item in preview.json()["lots"]] == [
        "5.000",
        "2.000",
    ]
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["comment"] == "Щомісячний підрахунок"
    assert body["line_count"] == 2
    assert body["surplus_line_count"] == 1
    assert body["shortage_line_count"] == 1
    assert body["adjustment_value_minor"] == 600
    assert body["unpriced_adjustment_count"] == 1
    assert [line["difference_kind"] for line in body["lines"]] == ["SURPLUS", "SHORTAGE"]
    assert MaterialLot.objects.get(pk=priced.pk).current_quantity == Decimal("5")
    event = AuditEvent.objects.get(action=AuditAction.STOCKTAKE_CREATED)
    assert event.object_id == body["id"]
    assert len(event.after["lines"]) == 2


@pytest.mark.django_db
def test_stocktake_creation_is_idempotent_and_rejects_changed_payload() -> None:
    client = authenticated_client(create_user(email="admin@example.test"))
    lot = create_lot(sku="CAP-103", number="A-02", quantity="5")
    original = [{"lot_id": str(lot.pk), "actual_quantity": "4"}]

    first = create_stocktake(client, key="stocktake-retry", lines=original)
    replay = create_stocktake(client, key="stocktake-retry", lines=original)
    mismatch = create_stocktake(
        client,
        key="stocktake-retry",
        lines=[{"lot_id": str(lot.pk), "actual_quantity": "3"}],
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["replayed"] is True
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert Stocktake.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.STOCKTAKE_CREATED).count() == 1


@pytest.mark.django_db
def test_post_reconciles_surplus_shortage_and_exact_cached_balances() -> None:
    admin = create_user(email="admin@example.test")
    surplus = create_lot(sku="CAP-104", number="SURPLUS", quantity="5")
    shortage = create_lot(sku="CAP-105", number="SHORTAGE", quantity="8")
    match = create_lot(sku="CAP-106", number="MATCH", quantity="3")
    client = authenticated_client(admin)
    draft = create_stocktake(
        client,
        key="stocktake-balance",
        comment="Контрольний підрахунок",
        lines=[
            {"lot_id": str(surplus.pk), "actual_quantity": "7.5"},
            {"lot_id": str(shortage.pk), "actual_quantity": "2"},
            {"lot_id": str(match.pk), "actual_quantity": "3"},
        ],
    )

    response = post_stocktake(
        client,
        stocktake_id=draft.json()["id"],
        key="stocktake-balance-post",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "POSTED"
    operation = InventoryOperation.objects.get(pk=response.json()["operation_id"])
    assert operation.kind == InventoryOperationKind.STOCKTAKE_ADJUSTMENT
    movements = list(operation.movements.order_by("quantity_delta"))
    assert [(item.quantity_delta, item.balance_after) for item in movements] == [
        (Decimal("-6.000"), Decimal("2.000")),
        (Decimal("2.500"), Decimal("7.500")),
    ]
    surplus.refresh_from_db()
    shortage.refresh_from_db()
    match.refresh_from_db()
    assert surplus.current_quantity == Decimal("7.5")
    assert shortage.current_quantity == Decimal("2")
    assert match.current_quantity == Decimal("3")
    assert operation.movements.count() == 2
    event = AuditEvent.objects.get(action=AuditAction.STOCKTAKE_POSTED)
    assert event.before["status"] == "DRAFT"
    assert event.after["status"] == "POSTED"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("system_quantity", "actual_quantity", "expected_delta"),
    [("0", "2.125", "2.125"), ("10.5", "0", "-10.500"), ("4", "4", None)],
)
def test_each_posted_delta_reconciles_to_the_counted_balance(
    system_quantity: str,
    actual_quantity: str,
    expected_delta: str | None,
) -> None:
    client = authenticated_client(create_user(email=f"admin-{system_quantity}@example.test"))
    lot = create_lot(sku=f"CAP-{system_quantity}", number="PROP", quantity=system_quantity)
    draft = create_stocktake(
        client,
        key=f"stocktake-{system_quantity}",
        lines=[{"lot_id": str(lot.pk), "actual_quantity": actual_quantity}],
    )

    posted = post_stocktake(
        client,
        stocktake_id=draft.json()["id"],
        key=f"stocktake-post-{system_quantity}",
    )

    lot.refresh_from_db()
    assert lot.current_quantity == Decimal(actual_quantity)
    movement = StockMovement.objects.filter(operation_id=posted.json()["operation_id"]).first()
    if expected_delta is None:
        assert movement is None
    else:
        assert movement is not None
        assert movement.quantity_delta == Decimal(expected_delta)
        assert movement.balance_after == Decimal(actual_quantity)


@pytest.mark.django_db
def test_post_rejects_stale_snapshot_without_partial_mutation() -> None:
    client = authenticated_client(create_user(email="admin@example.test"))
    first = create_lot(sku="CAP-107", number="FIRST", quantity="5")
    second = create_lot(sku="CAP-108", number="SECOND", quantity="4")
    draft = create_stocktake(
        client,
        key="stocktake-stale",
        lines=[
            {"lot_id": str(first.pk), "actual_quantity": "3"},
            {"lot_id": str(second.pk), "actual_quantity": "2"},
        ],
    )
    second.current_quantity = Decimal("3")
    second.save(update_fields=("current_quantity",))

    response = post_stocktake(
        client,
        stocktake_id=draft.json()["id"],
        key="stocktake-stale-post",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "stocktake_balance_changed"
    first.refresh_from_db()
    assert first.current_quantity == Decimal("5")
    assert Stocktake.objects.get().status == StocktakeStatus.DRAFT
    assert InventoryOperation.objects.count() == 0
    assert StockMovement.objects.count() == 0
    assert not AuditEvent.objects.filter(action=AuditAction.STOCKTAKE_POSTED).exists()


@pytest.mark.django_db
def test_post_rolls_back_all_adjustments_when_a_movement_write_fails() -> None:
    client = authenticated_client(create_user(email="admin@example.test"))
    first = create_lot(sku="CAP-109", number="FIRST", quantity="5")
    second = create_lot(sku="CAP-110", number="SECOND", quantity="4")
    draft = create_stocktake(
        client,
        key="stocktake-rollback",
        lines=[
            {"lot_id": str(first.pk), "actual_quantity": "3"},
            {"lot_id": str(second.pk), "actual_quantity": "2"},
        ],
    )
    original_create = StockMovement.objects.create
    calls = 0

    def fail_second_movement(**kwargs: object) -> StockMovement:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated movement failure")
        return original_create(**kwargs)

    with patch(
        "apps.inventory.services.StockMovement.objects.create",
        side_effect=fail_second_movement,
    ):
        response = post_stocktake(
            client,
            stocktake_id=draft.json()["id"],
            key="stocktake-rollback-post",
        )

    assert response.status_code == 500
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.current_quantity == Decimal("5")
    assert second.current_quantity == Decimal("4")
    assert Stocktake.objects.get().status == StocktakeStatus.DRAFT
    assert InventoryOperation.objects.count() == 0
    assert StockMovement.objects.count() == 0


@pytest.mark.django_db
def test_post_is_idempotent_and_corrections_require_a_new_stocktake() -> None:
    client = authenticated_client(create_user(email="admin@example.test"))
    lot = create_lot(sku="CAP-111", number="CORRECTION", quantity="5")
    first_draft = create_stocktake(
        client,
        key="stocktake-first",
        lines=[{"lot_id": str(lot.pk), "actual_quantity": "4"}],
    )
    first = post_stocktake(
        client,
        stocktake_id=first_draft.json()["id"],
        key="stocktake-first-post",
    )
    replay = post_stocktake(
        client,
        stocktake_id=first_draft.json()["id"],
        key="stocktake-first-post",
    )
    conflict = post_stocktake(
        client,
        stocktake_id=first_draft.json()["id"],
        key="stocktake-changed-key",
    )
    correction_draft = create_stocktake(
        client,
        key="stocktake-correction",
        lines=[{"lot_id": str(lot.pk), "actual_quantity": "6"}],
    )
    correction = post_stocktake(
        client,
        stocktake_id=correction_draft.json()["id"],
        key="stocktake-correction-post",
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "stocktake_already_posted"
    assert correction.status_code == 200
    lot.refresh_from_db()
    assert lot.current_quantity == Decimal("6")
    assert Stocktake.objects.filter(status=StocktakeStatus.POSTED).count() == 2
    assert InventoryOperation.objects.count() == 2


@pytest.mark.django_db
def test_movement_journal_filters_and_returns_read_only_operation_detail() -> None:
    admin = create_user(email="journal@example.test")
    other_admin = create_user(email="other@example.test")
    first = create_lot(sku="JRN-001", number="JOURNAL-A", quantity="5")
    second = create_lot(sku="JRN-002", number="JOURNAL-B", quantity="4")
    client = authenticated_client(admin)
    draft = create_stocktake(
        client,
        key="journal-stocktake",
        lines=[
            {"lot_id": str(first.pk), "actual_quantity": "3"},
            {"lot_id": str(second.pk), "actual_quantity": "6"},
        ],
    )
    posted = post_stocktake(
        client,
        stocktake_id=draft.json()["id"],
        key="journal-stocktake-post",
    )
    authenticated_client(other_admin).post(
        "/api/v1/inventory/write-offs",
        {"reason": "Окреме списання", "lines": [{"lot_id": str(second.pk), "quantity": "1"}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="journal-other-writeoff",
    )

    response = client.get(
        "/api/v1/inventory/movements",
        {
            "search": "JRN-001",
            "kind": InventoryOperationKind.STOCKTAKE_ADJUSTMENT,
            "material_id": str(first.material_id),
            "actor": "journal@",
            "date_from": timezone.localdate().isoformat(),
            "date_to": timezone.localdate().isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["next_cursor"] is None
    assert len(response.json()["movements"]) == 1
    item = response.json()["movements"][0]
    assert item["operation_id"] == posted.json()["operation_id"]
    assert item["operation_kind"] == InventoryOperationKind.STOCKTAKE_ADJUSTMENT
    assert item["material_sku"] == "JRN-001"
    detail = client.get(f"/api/v1/inventory/operations/{item['operation_id']}")
    assert detail.status_code == 200
    assert detail.json()["movement_count"] == 2
    assert detail.json()["created_by_email"] == "journal@example.test"
    invalid_dates = client.get(
        "/api/v1/inventory/movements",
        {"date_from": "2026-07-22", "date_to": "2026-07-21"},
    )
    assert invalid_dates.status_code == 422


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.RECEPTION, UserRole.PODOLOGIST])
def test_non_admin_cannot_access_stocktake_or_movement_contracts(role: str) -> None:
    client = authenticated_client(create_user(email=f"{role}@example.test", role=role))

    assert client.get("/api/v1/inventory/stocktakes/preview").status_code == 403
    assert (
        client.post(
            "/api/v1/inventory/stocktakes",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="forbidden-stocktake",
        ).status_code
        == 403
    )
    assert client.get("/api/v1/inventory/movements").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_stocktake_snapshots_and_posted_headers_are_append_only_in_model_and_database() -> None:
    client = authenticated_client(create_user(email="admin@example.test"))
    lot = create_lot(sku="CAP-112", number="LOCKED", quantity="5")
    draft = create_stocktake(
        client,
        key="stocktake-immutable",
        lines=[{"lot_id": str(lot.pk), "actual_quantity": "3"}],
    )
    stocktake = Stocktake.objects.get(pk=draft.json()["id"])
    line = stocktake.lines.get()

    line.actual_quantity = Decimal("4")
    with pytest.raises(ImmutableInventoryRecordError):
        line.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        StocktakeLine.objects.filter(pk=line.pk).update(actual_quantity=Decimal("4"))

    post_stocktake(
        client,
        stocktake_id=str(stocktake.pk),
        key="stocktake-immutable-post",
    )
    stocktake.refresh_from_db()
    stocktake.comment = "Змінено"
    with pytest.raises(ImmutableInventoryRecordError):
        stocktake.save()
    with pytest.raises(DatabaseError), transaction.atomic():
        Stocktake.objects.filter(pk=stocktake.pk).update(comment="raw update")
    with pytest.raises(DatabaseError), transaction.atomic():
        Stocktake.objects.filter(pk=stocktake.pk).delete()
