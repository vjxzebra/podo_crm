import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.inventory.models import (
    InventoryOperation,
    InventoryOperationKind,
    Material,
    MaterialLot,
    StockMovement,
    Stocktake,
    StocktakeLine,
    StocktakeStatus,
)
from config.api.exceptions import ApiProblem


def material_snapshot(material: Material) -> dict[str, Any]:
    return {
        "sku": material.sku,
        "name": material.name,
        "category": material.category,
        "unit": material.unit,
        "minimum_quantity": str(material.minimum_quantity),
        "is_active": material.is_active,
        "version": material.version,
    }


def _check_version(*, actual: int, expected: int) -> None:
    if actual != expected:
        raise ApiProblem(
            code="stale_version",
            message="Матеріал уже змінено в іншій сесії. Оновіть дані та повторіть дію.",
            status_code=409,
        )


@transaction.atomic
def create_material(*, actor: User, correlation_id: str, data: dict[str, Any]) -> Material:
    material = Material.objects.create(**data)
    record_audit_event(
        actor=actor,
        action=AuditAction.MATERIAL_CREATED,
        object_type="material",
        object_id=material.pk,
        object_label=f"{material.sku} · {material.name}",
        correlation_id=correlation_id,
        before={},
        after=material_snapshot(material),
        description="Створено картку складського матеріалу.",
    )
    return material


@transaction.atomic
def update_material(
    *, actor: User, material_id: uuid.UUID, correlation_id: str, changes: dict[str, Any]
) -> Material:
    material = Material.objects.select_for_update().get(pk=material_id)
    expected_version = changes.pop("version")
    _check_version(actual=material.version, expected=expected_version)
    if "unit" in changes and changes["unit"] != material.unit and material.lots.exists():
        raise ApiProblem(
            code="material_unit_immutable",
            message="Одиницю виміру не можна змінити після появи першої партії.",
            status_code=409,
            fields={"unit": ["Створіть новий матеріал з іншою одиницею виміру."]},
        )
    before = material_snapshot(material)
    was_active = material.is_active
    for field in ("sku", "name", "category", "unit", "minimum_quantity", "is_active"):
        if field in changes:
            setattr(material, field, changes[field])
    material.version += 1
    material.save()
    if was_active and not material.is_active:
        action = AuditAction.MATERIAL_DEACTIVATED
        description = "Деактивовано матеріал без видалення партій та історії."
    elif not was_active and material.is_active:
        action = AuditAction.MATERIAL_REACTIVATED
        description = "Активовано складський матеріал."
    else:
        action = AuditAction.MATERIAL_UPDATED
        description = "Оновлено картку складського матеріалу."
    record_audit_event(
        actor=actor,
        action=action,
        object_type="material",
        object_id=material.pk,
        object_label=f"{material.sku} · {material.name}",
        correlation_id=correlation_id,
        before=before,
        after=material_snapshot(material),
        description=description,
    )
    return material


def _json_default(value: object) -> str:
    if isinstance(value, (date, Decimal, uuid.UUID)):
        return str(value)
    raise TypeError(f"Unsupported idempotency payload value: {type(value)!r}")


def _payload_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _existing_operation(
    *,
    actor: User,
    kind: str,
    idempotency_key: str,
    payload_hash: str,
) -> InventoryOperation | None:
    operation = (
        InventoryOperation.objects.prefetch_related("movements__lot__material")
        .filter(
            created_by=actor,
            kind=kind,
            idempotency_key=idempotency_key,
        )
        .first()
    )
    if operation is not None and operation.payload_hash != payload_hash:
        raise ApiProblem(
            code="idempotency_payload_mismatch",
            message="Цей ключ повтору вже використано для іншого складського запиту.",
            status_code=409,
            fields={"idempotency_key": ["Створіть новий ключ для зміненого запиту."]},
        )
    return operation


def operation_snapshot(operation: InventoryOperation) -> dict[str, Any]:
    return {
        "public_number": operation.public_number,
        "kind": operation.kind,
        "status": operation.status,
        "source_visit_id": operation.source_visit_id,
        "reason": operation.reason,
        "comment": operation.comment,
        "movements": [
            {
                "material_id": movement.lot.material_id,
                "material": movement.lot.material.name,
                "lot_id": movement.lot_id,
                "lot_number": movement.lot.lot_number,
                "quantity_delta": movement.quantity_delta,
                "balance_after": movement.balance_after,
            }
            for movement in operation.movements.all()
        ],
    }


def _lot_detail_conflict(
    *,
    lot: MaterialLot,
    expires_on: date | None,
    purchase_price_minor: int | None,
    supplier_name: str,
) -> bool:
    return (
        lot.expires_on != expires_on
        or (purchase_price_minor is not None and lot.purchase_price_minor != purchase_price_minor)
        or (supplier_name != "" and lot.supplier_name != supplier_name)
    )


@transaction.atomic
def post_receipt(
    *,
    actor: User,
    correlation_id: str,
    idempotency_key: str,
    data: dict[str, Any],
) -> tuple[InventoryOperation, bool]:
    locked_actor = User.objects.select_for_update().get(pk=actor.pk)
    request_hash = _payload_hash(data)
    existing = _existing_operation(
        actor=locked_actor,
        kind=InventoryOperationKind.RECEIPT,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    lines = data["lines"]
    material_ids = sorted({line["material_id"] for line in lines}, key=str)
    locked_materials = list(
        Material.objects.select_for_update().filter(pk__in=material_ids).order_by("pk")
    )
    materials = {item.pk: item for item in locked_materials}
    for index, line in enumerate(lines):
        material = materials.get(line["material_id"])
        if material is None:
            raise ApiProblem(
                code="material_not_found",
                message="Один із матеріалів не знайдено.",
                status_code=422,
                fields={f"lines.{index}.material_id": ["Оберіть матеріал із каталогу."]},
            )
        if not material.is_active:
            raise ApiProblem(
                code="material_inactive",
                message="Надходження можна провести лише для активного матеріалу.",
                status_code=409,
                fields={f"lines.{index}.material_id": ["Активуйте матеріал або оберіть інший."]},
            )

    requested_numbers = {line["lot_number"] for line in lines}
    locked_lots = list(
        MaterialLot.objects.select_for_update()
        .filter(material_id__in=material_ids, lot_number__in=requested_numbers)
        .select_related("material")
        .order_by("pk")
    )
    lots = {(item.material_id, item.lot_number): item for item in locked_lots}
    for index, line in enumerate(lines):
        lot = lots.get((line["material_id"], line["lot_number"]))
        if lot is None:
            continue
        if not line["allow_existing_lot"]:
            raise ApiProblem(
                code="material_lot_already_exists",
                message="Партія з таким номером уже існує для матеріалу.",
                status_code=409,
                fields={
                    f"lines.{index}.lot_number": [
                        "Підтвердьте поповнення існуючої партії або змініть номер."
                    ]
                },
            )
        if _lot_detail_conflict(
            lot=lot,
            expires_on=line["expires_on"],
            purchase_price_minor=line["purchase_price_minor"],
            supplier_name=line["supplier_name"],
        ):
            raise ApiProblem(
                code="material_lot_details_mismatch",
                message="Дані існуючої партії не збігаються з рядком надходження.",
                status_code=409,
                fields={
                    f"lines.{index}.lot_number": [
                        "Строк, ціна й постачальник мають відповідати існуючій партії."
                    ]
                },
            )

    operation = InventoryOperation.objects.create(
        kind=InventoryOperationKind.RECEIPT,
        created_by=locked_actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
        comment=data["comment"],
    )
    for line in lines:
        lot = lots.get((line["material_id"], line["lot_number"]))
        if lot is None:
            lot = MaterialLot.objects.create(
                material=materials[line["material_id"]],
                lot_number=line["lot_number"],
                received_on=data["received_on"],
                expires_on=line["expires_on"],
                initial_quantity=line["quantity"],
                current_quantity=line["quantity"],
                purchase_price_minor=line["purchase_price_minor"],
                supplier_name=line["supplier_name"],
            )
            lots[(line["material_id"], line["lot_number"])] = lot
        else:
            lot.initial_quantity += line["quantity"]
            lot.current_quantity += line["quantity"]
            lot.save(update_fields=("initial_quantity", "current_quantity"))
        StockMovement.objects.create(
            operation=operation,
            lot=lot,
            quantity_delta=line["quantity"],
            balance_after=lot.current_quantity,
        )

    operation = InventoryOperation.objects.prefetch_related("movements__lot__material").get(
        pk=operation.pk
    )
    record_audit_event(
        actor=locked_actor,
        action=AuditAction.INVENTORY_RECEIPT_POSTED,
        object_type="inventory_operation",
        object_id=operation.pk,
        object_label=operation.public_number,
        correlation_id=correlation_id,
        before={},
        after=operation_snapshot(operation),
        description="Проведено надходження матеріалів.",
    )
    return operation, False


@transaction.atomic
def post_manual_writeoff(
    *,
    actor: User,
    correlation_id: str,
    idempotency_key: str,
    data: dict[str, Any],
) -> tuple[InventoryOperation, bool]:
    locked_actor = User.objects.select_for_update().get(pk=actor.pk)
    request_hash = _payload_hash(data)
    existing = _existing_operation(
        actor=locked_actor,
        kind=InventoryOperationKind.MANUAL_WRITEOFF,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    lines = data["lines"]
    lot_ids = sorted({line["lot_id"] for line in lines}, key=str)
    locked_lots = list(
        MaterialLot.objects.select_for_update()
        .filter(pk__in=lot_ids)
        .select_related("material")
        .order_by("pk")
    )
    lots = {item.pk: item for item in locked_lots}
    before_balances: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        lot = lots.get(line["lot_id"])
        if lot is None:
            raise ApiProblem(
                code="material_lot_not_found",
                message="Одну з партій не знайдено.",
                status_code=422,
                fields={f"lines.{index}.lot_id": ["Оберіть актуальну партію."]},
            )
        if line["quantity"] > lot.current_quantity:
            raise ApiProblem(
                code="insufficient_stock",
                message="Кількість списання перевищує поточний залишок партії.",
                status_code=409,
                fields={
                    f"lines.{index}.quantity": [
                        f"Доступно {lot.current_quantity} {lot.material.unit}."
                    ]
                },
            )
        before_balances.append(
            {
                "lot_id": lot.pk,
                "lot_number": lot.lot_number,
                "balance": lot.current_quantity,
            }
        )

    operation = InventoryOperation.objects.create(
        kind=InventoryOperationKind.MANUAL_WRITEOFF,
        created_by=locked_actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
        reason=data["reason"],
        comment=data["comment"],
    )
    for line in lines:
        lot = lots[line["lot_id"]]
        lot.current_quantity -= line["quantity"]
        lot.save(update_fields=("current_quantity",))
        StockMovement.objects.create(
            operation=operation,
            lot=lot,
            quantity_delta=-line["quantity"],
            balance_after=lot.current_quantity,
        )

    operation = InventoryOperation.objects.prefetch_related("movements__lot__material").get(
        pk=operation.pk
    )
    record_audit_event(
        actor=locked_actor,
        action=AuditAction.INVENTORY_MANUAL_WRITEOFF_POSTED,
        object_type="inventory_operation",
        object_id=operation.pk,
        object_label=operation.public_number,
        correlation_id=correlation_id,
        before={"balances": before_balances},
        after=operation_snapshot(operation),
        description="Проведено ручне списання матеріалів.",
        note=operation.comment,
    )
    return operation, False


def stocktake_line_snapshot(line: StocktakeLine) -> dict[str, Any]:
    return {
        "lot_id": line.lot_id,
        "material_sku": line.material_sku,
        "material_name": line.material_name,
        "material_unit": line.material_unit,
        "lot_number": line.lot_number,
        "system_quantity": line.system_quantity,
        "actual_quantity": line.actual_quantity,
        "difference": line.difference,
        "difference_kind": line.difference_kind,
        "adjustment_value_minor": line.adjustment_value_minor,
    }


def stocktake_snapshot(stocktake: Stocktake) -> dict[str, Any]:
    return {
        "public_number": stocktake.public_number,
        "status": stocktake.status,
        "comment": stocktake.comment,
        "operation_id": stocktake.operation_id,
        "lines": [stocktake_line_snapshot(line) for line in stocktake.lines.all()],
    }


def _existing_stocktake(
    *,
    actor: User,
    idempotency_key: str,
    payload_hash: str,
) -> Stocktake | None:
    stocktake = (
        Stocktake.objects.select_related("created_by", "posted_by", "operation")
        .prefetch_related("lines__lot__material", "operation__movements__lot__material")
        .filter(created_by=actor, idempotency_key=idempotency_key)
        .first()
    )
    if stocktake is not None and stocktake.payload_hash != payload_hash:
        raise ApiProblem(
            code="idempotency_payload_mismatch",
            message="Цей ключ повтору вже використано для іншої інвентаризації.",
            status_code=409,
            fields={"idempotency_key": ["Створіть новий ключ для зміненого підрахунку."]},
        )
    return stocktake


@transaction.atomic
def create_stocktake(
    *,
    actor: User,
    correlation_id: str,
    idempotency_key: str,
    data: dict[str, Any],
) -> tuple[Stocktake, bool]:
    locked_actor = User.objects.select_for_update().get(pk=actor.pk)
    request_hash = _payload_hash(data)
    existing = _existing_stocktake(
        actor=locked_actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    lines = data["lines"]
    lot_ids = sorted({line["lot_id"] for line in lines}, key=str)
    locked_lots = list(
        MaterialLot.objects.select_for_update()
        .filter(pk__in=lot_ids)
        .select_related("material")
        .order_by("pk")
    )
    lots = {lot.pk: lot for lot in locked_lots}
    for index, line in enumerate(lines):
        if line["lot_id"] not in lots:
            raise ApiProblem(
                code="material_lot_not_found",
                message="Одну з партій для інвентаризації не знайдено.",
                status_code=422,
                fields={
                    f"lines.{index}.lot_id": ["Оновіть перелік партій і повторіть підрахунок."]
                },
            )

    stocktake = Stocktake.objects.create(
        created_by=locked_actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
        comment=data["comment"],
    )
    for line in lines:
        lot = lots[line["lot_id"]]
        StocktakeLine.objects.create(
            stocktake=stocktake,
            lot=lot,
            material_sku=lot.material.sku,
            material_name=lot.material.name,
            material_unit=lot.material.unit,
            lot_number=lot.lot_number,
            system_quantity=lot.current_quantity,
            actual_quantity=line["actual_quantity"],
            purchase_price_minor=lot.purchase_price_minor,
        )

    stocktake = (
        Stocktake.objects.select_related("created_by", "posted_by", "operation")
        .prefetch_related("lines__lot__material")
        .get(pk=stocktake.pk)
    )
    record_audit_event(
        actor=locked_actor,
        action=AuditAction.STOCKTAKE_CREATED,
        object_type="stocktake",
        object_id=stocktake.pk,
        object_label=stocktake.public_number,
        correlation_id=correlation_id,
        before={},
        after=stocktake_snapshot(stocktake),
        description="Зафіксовано чернетку інвентаризації з обліковими й фактичними залишками.",
        note=stocktake.comment,
    )
    return stocktake, False


@transaction.atomic
def post_stocktake(
    *,
    actor: User,
    stocktake_id: uuid.UUID,
    correlation_id: str,
    idempotency_key: str,
) -> tuple[Stocktake, bool]:
    locked_actor = User.objects.select_for_update().get(pk=actor.pk)
    stocktake = (
        Stocktake.objects.select_for_update(of=("self",))
        .select_related("created_by", "posted_by", "operation")
        .prefetch_related("lines__lot__material", "operation__movements__lot__material")
        .get(pk=stocktake_id)
    )
    if stocktake.status == StocktakeStatus.POSTED:
        if stocktake.post_idempotency_key == idempotency_key:
            return stocktake, True
        raise ApiProblem(
            code="stocktake_already_posted",
            message="Цю інвентаризацію вже проведено; виправлення створюється новою операцією.",
            status_code=409,
        )

    lines = list(stocktake.lines.all())
    lot_ids = sorted((line.lot_id for line in lines), key=str)
    locked_lots = list(
        MaterialLot.objects.select_for_update()
        .filter(pk__in=lot_ids)
        .select_related("material")
        .order_by("pk")
    )
    lots = {lot.pk: lot for lot in locked_lots}
    for index, line in enumerate(lines):
        lot = lots.get(line.lot_id)
        if lot is None or lot.current_quantity != line.system_quantity:
            current = "видалена" if lot is None else str(lot.current_quantity)
            raise ApiProblem(
                code="stocktake_balance_changed",
                message="Залишки змінилися після підрахунку. Створіть нову інвентаризацію.",
                status_code=409,
                fields={
                    f"lines.{index}.system_quantity": [
                        f"Було {line.system_quantity}; зараз {current}."
                    ]
                },
            )

    before = stocktake_snapshot(stocktake)
    operation_hash = _payload_hash({"stocktake_id": stocktake.pk})
    if (
        _existing_operation(
            actor=locked_actor,
            kind=InventoryOperationKind.STOCKTAKE_ADJUSTMENT,
            idempotency_key=idempotency_key,
            payload_hash=operation_hash,
        )
        is not None
    ):
        raise ApiProblem(
            code="stocktake_post_state_invalid",
            message="Операція з цим ключем уже існує без зв'язку з чернеткою.",
            status_code=409,
        )
    operation = InventoryOperation.objects.create(
        kind=InventoryOperationKind.STOCKTAKE_ADJUSTMENT,
        created_by=locked_actor,
        idempotency_key=idempotency_key,
        payload_hash=operation_hash,
        reason=f"Інвентаризація {stocktake.public_number}",
        comment=stocktake.comment,
    )
    for line in lines:
        if line.difference == 0:
            continue
        lot = lots[line.lot_id]
        lot.current_quantity = line.actual_quantity
        lot.save(update_fields=("current_quantity",))
        StockMovement.objects.create(
            operation=operation,
            lot=lot,
            quantity_delta=line.difference,
            balance_after=lot.current_quantity,
        )

    stocktake.status = StocktakeStatus.POSTED
    stocktake.operation = operation
    stocktake.post_idempotency_key = idempotency_key
    stocktake.posted_by = locked_actor
    stocktake.posted_at = timezone.now()
    stocktake.save(
        update_fields=(
            "status",
            "operation",
            "post_idempotency_key",
            "posted_by",
            "posted_at",
        )
    )
    stocktake = (
        Stocktake.objects.select_related("created_by", "posted_by", "operation")
        .prefetch_related("lines__lot__material", "operation__movements__lot__material")
        .get(pk=stocktake.pk)
    )
    record_audit_event(
        actor=locked_actor,
        action=AuditAction.STOCKTAKE_POSTED,
        object_type="stocktake",
        object_id=stocktake.pk,
        object_label=stocktake.public_number,
        correlation_id=correlation_id,
        before=before,
        after=stocktake_snapshot(stocktake),
        description="Проведено інвентаризацію append-only коригуваннями залишків.",
        note=stocktake.comment,
    )
    return stocktake, False
