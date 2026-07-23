import uuid
from collections.abc import Collection
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models.functions import Lower, Upper
from django.utils import timezone
from django.utils.functional import cached_property


class MaterialUnitImmutableError(RuntimeError):
    pass


class MaterialLotIdentityImmutableError(RuntimeError):
    pass


class ImmutableInventoryRecordError(RuntimeError):
    pass


def inventory_operation_public_number(operation_id: uuid.UUID) -> str:
    return f"INV-{operation_id.hex[:12].upper()}"


def stocktake_public_number(stocktake_id: uuid.UUID) -> str:
    return f"STK-{stocktake_id.hex[:12].upper()}"


class StockStatus(models.TextChoices):
    OUT_OF_STOCK = "out_of_stock", "Немає в наявності"
    LOW = "low", "Низький залишок"
    EXPIRED = "expired", "Є прострочена партія"
    EXPIRING = "expiring", "Закінчується термін"
    HEALTHY = "healthy", "В наявності"


class LotStatus(models.TextChoices):
    EMPTY = "empty", "Вичерпана"
    EXPIRED = "expired", "Прострочена"
    EXPIRING = "expiring", "Закінчується термін"
    USABLE = "usable", "Доступна"


class InventoryOperationKind(models.TextChoices):
    RECEIPT = "RECEIPT", "Надходження"
    VISIT_USAGE = "VISIT_USAGE", "Використання у прийомі"
    MANUAL_WRITEOFF = "MANUAL_WRITEOFF", "Ручне списання"
    STOCKTAKE_ADJUSTMENT = "STOCKTAKE_ADJUSTMENT", "Коригування інвентаризації"


class InventoryOperationStatus(models.TextChoices):
    POSTED = "POSTED", "Проведено"


class StocktakeStatus(models.TextChoices):
    DRAFT = "DRAFT", "Чернетка"
    POSTED = "POSTED", "Проведено"


class StocktakeDifferenceKind(models.TextChoices):
    MATCH = "MATCH", "Без різниці"
    SURPLUS = "SURPLUS", "Надлишок"
    SHORTAGE = "SHORTAGE", "Нестача"


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    contact_name = models.CharField(max_length=180, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_active", "name", "id")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="inventory_supplier_name_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.name


class Material(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=48)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=100)
    unit = models.CharField(max_length=24)
    minimum_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_active", "name", "sku", "id")
        indexes = [
            GinIndex(
                OpClass(Upper("sku"), name="gin_trgm_ops"),
                OpClass(Upper("name"), name="gin_trgm_ops"),
                name="inventory_global_search_gin",
            )
        ]
        constraints = [
            models.UniqueConstraint(Lower("sku"), name="inventory_material_sku_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(minimum_quantity__gte=0),
                name="inventory_material_minimum_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sku} · {self.name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            not self._state.adding
            and getattr(self, "_original_unit", self.unit) != self.unit
            and self.lots.exists()
        ):
            raise MaterialUnitImmutableError(
                "Material unit cannot change after the first lot or stock movement."
            )
        super().save(*args, **kwargs)
        self._original_unit = self.unit

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[Any],
    ) -> "Material":
        instance = super().from_db(db, field_names, values)
        instance._original_unit = instance.unit
        return instance

    @cached_property
    def inventory_projection(self) -> dict[str, Any]:
        today = timezone.localdate()
        expiring_until = today + timedelta(days=60)
        lots = list(self.lots.all())
        positive_lots = [item for item in lots if item.current_quantity > 0]
        usable_lots = [
            item for item in positive_lots if item.expires_on is None or item.expires_on >= today
        ]
        total = sum((item.current_quantity for item in positive_lots), Decimal("0"))
        available = sum((item.current_quantity for item in usable_lots), Decimal("0"))
        usable_expiries = [item.expires_on for item in usable_lots if item.expires_on is not None]
        nearest_expiry = min(usable_expiries, default=None)
        has_expired = any(
            item.expires_on is not None and item.expires_on < today for item in positive_lots
        )
        if available <= 0:
            stock_status = StockStatus.OUT_OF_STOCK
        elif available < self.minimum_quantity:
            stock_status = StockStatus.LOW
        elif has_expired:
            stock_status = StockStatus.EXPIRED
        elif nearest_expiry is not None and nearest_expiry <= expiring_until:
            stock_status = StockStatus.EXPIRING
        else:
            stock_status = StockStatus.HEALTHY
        return {
            "total_quantity": total,
            "available_quantity": available,
            "nearest_expiry": nearest_expiry,
            "stock_status": stock_status,
            "lots_count": len(lots),
        }

    @property
    def total_quantity(self) -> Decimal:
        return self.inventory_projection["total_quantity"]

    @property
    def available_quantity(self) -> Decimal:
        return self.inventory_projection["available_quantity"]

    @property
    def nearest_expiry(self) -> Any:
        return self.inventory_projection["nearest_expiry"]

    @property
    def stock_status(self) -> str:
        return str(self.inventory_projection["stock_status"])

    @property
    def lots_count(self) -> int:
        return self.inventory_projection["lots_count"]


class MaterialLot(models.Model):
    _original_material_id: uuid.UUID
    _original_lot_number: str

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="lots")
    lot_number = models.CharField(max_length=80)
    received_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    initial_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    purchase_price_minor = models.PositiveBigIntegerField(null=True, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="lots",
        null=True,
        blank=True,
    )
    supplier_name = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("expires_on", "received_on", "lot_number", "id")
        constraints = [
            models.UniqueConstraint(
                Lower("lot_number"),
                "material",
                name="inventory_material_lot_identity_ci_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(initial_quantity__gt=0),
                name="inventory_lot_initial_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(current_quantity__gte=0),
                name="inventory_lot_current_quantity_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.material.sku} · {self.lot_number}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.lot_number = self.lot_number.strip().upper()
        if not self._state.adding:
            if hasattr(self, "_original_material_id") and hasattr(self, "_original_lot_number"):
                original_material_id = self._original_material_id
                original_lot_number = self._original_lot_number
            else:
                original_material_id, original_lot_number = (
                    type(self)
                    .objects.filter(pk=self.pk)
                    .values_list("material_id", "lot_number")
                    .get()
                )
            if original_material_id != self.material_id or original_lot_number != self.lot_number:
                raise MaterialLotIdentityImmutableError(
                    "A material lot identity cannot be reassigned or renamed."
                )
        super().save(*args, **kwargs)
        self._original_material_id = self.material_id
        self._original_lot_number = self.lot_number

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[Any],
    ) -> "MaterialLot":
        instance = super().from_db(db, field_names, values)
        loaded_values = dict(zip(field_names, values, strict=True))
        if "material_id" in loaded_values:
            instance._original_material_id = loaded_values["material_id"]
        if "lot_number" in loaded_values:
            instance._original_lot_number = loaded_values["lot_number"]
        return instance

    @property
    def is_expired(self) -> bool:
        return self.expires_on is not None and self.expires_on < timezone.localdate()

    @property
    def is_usable(self) -> bool:
        return self.current_quantity > 0 and not self.is_expired

    @property
    def status(self) -> str:
        if self.current_quantity <= 0:
            return LotStatus.EMPTY
        if self.is_expired:
            return LotStatus.EXPIRED
        if self.expires_on is not None and self.expires_on <= timezone.localdate() + timedelta(
            days=60
        ):
            return LotStatus.EXPIRING
        return LotStatus.USABLE


class InventoryOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_number = models.CharField(max_length=24, unique=True, editable=False)
    kind = models.CharField(max_length=32, choices=InventoryOperationKind.choices)
    status = models.CharField(
        max_length=16,
        choices=InventoryOperationStatus.choices,
        default=InventoryOperationStatus.POSTED,
        editable=False,
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="inventory_operations",
    )
    source_visit = models.OneToOneField(
        "visits.Visit",
        on_delete=models.PROTECT,
        related_name="inventory_operation",
        null=True,
        blank=True,
        editable=False,
    )
    idempotency_key = models.CharField(max_length=128)
    payload_hash = models.CharField(max_length=64, editable=False)
    reason = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-posted_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("created_by", "kind", "idempotency_key"),
                name="inventory_operation_actor_kind_idempotency_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(kind=InventoryOperationKind.VISIT_USAGE, source_visit__isnull=False)
                    | (
                        ~models.Q(kind=InventoryOperationKind.VISIT_USAGE)
                        & models.Q(source_visit__isnull=True)
                    )
                ),
                name="inventory_operation_visit_source_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_number} · {self.get_kind_display()}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableInventoryRecordError("Posted inventory operations are immutable.")
        if not self.public_number:
            self.public_number = inventory_operation_public_number(self.id)
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableInventoryRecordError("Posted inventory operations cannot be deleted.")


class StockMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation = models.ForeignKey(
        InventoryOperation,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    lot = models.ForeignKey(
        MaterialLot,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=3)
    balance_after = models.DecimalField(max_digits=12, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0),
                name="inventory_movement_quantity_non_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(balance_after__gte=0),
                name="inventory_movement_balance_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.operation.public_number} · {self.lot} · {self.quantity_delta}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableInventoryRecordError("Posted stock movements are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableInventoryRecordError("Posted stock movements cannot be deleted.")


class Stocktake(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_number = models.CharField(max_length=24, unique=True, editable=False)
    status = models.CharField(
        max_length=16,
        choices=StocktakeStatus.choices,
        default=StocktakeStatus.DRAFT,
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="inventory_stocktakes",
    )
    posted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="posted_inventory_stocktakes",
        null=True,
        blank=True,
        editable=False,
    )
    idempotency_key = models.CharField(max_length=128)
    payload_hash = models.CharField(max_length=64, editable=False)
    post_idempotency_key = models.CharField(max_length=128, blank=True, editable=False)
    comment = models.TextField(blank=True)
    operation = models.OneToOneField(
        InventoryOperation,
        on_delete=models.PROTECT,
        related_name="stocktake",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("created_by", "idempotency_key"),
                name="inventory_stocktake_actor_idempotency_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_number} · {self.get_status_display()}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding and getattr(self, "_original_status", self.status) == (
            StocktakeStatus.POSTED
        ):
            raise ImmutableInventoryRecordError("Posted stocktakes are immutable.")
        if not self.public_number:
            self.public_number = stocktake_public_number(self.id)
        super().save(*args, **kwargs)
        self._original_status = self.status

    def refresh_from_db(self, *args: Any, **kwargs: Any) -> None:
        super().refresh_from_db(*args, **kwargs)
        self._original_status = self.status

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[Any],
    ) -> "Stocktake":
        instance = super().from_db(db, field_names, values)
        instance._original_status = instance.status
        return instance

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if self.status == StocktakeStatus.POSTED:
            raise ImmutableInventoryRecordError("Posted stocktakes cannot be deleted.")
        return super().delete(*args, **kwargs)


class StocktakeLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stocktake = models.ForeignKey(Stocktake, on_delete=models.PROTECT, related_name="lines")
    lot = models.ForeignKey(MaterialLot, on_delete=models.PROTECT, related_name="stocktake_lines")
    material_sku = models.CharField(max_length=48, editable=False)
    material_name = models.CharField(max_length=180, editable=False)
    material_unit = models.CharField(max_length=24, editable=False)
    lot_number = models.CharField(max_length=80, editable=False)
    system_quantity = models.DecimalField(max_digits=12, decimal_places=3, editable=False)
    actual_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    purchase_price_minor = models.PositiveBigIntegerField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("material_name", "material_sku", "lot_number", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("stocktake", "lot"),
                name="inventory_stocktake_lot_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(system_quantity__gte=0),
                name="inventory_stocktake_system_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(actual_quantity__gte=0),
                name="inventory_stocktake_actual_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.stocktake.public_number} · {self.material_sku} · {self.lot_number}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableInventoryRecordError("Stocktake lines are immutable snapshots.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableInventoryRecordError("Stocktake lines cannot be deleted.")

    @property
    def difference(self) -> Decimal:
        return self.actual_quantity - self.system_quantity

    @property
    def difference_kind(self) -> str:
        if self.difference > 0:
            return StocktakeDifferenceKind.SURPLUS
        if self.difference < 0:
            return StocktakeDifferenceKind.SHORTAGE
        return StocktakeDifferenceKind.MATCH

    @property
    def adjustment_value_minor(self) -> int | None:
        if self.purchase_price_minor is None:
            return None
        return int(
            (self.difference * self.purchase_price_minor).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
