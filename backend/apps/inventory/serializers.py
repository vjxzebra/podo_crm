import re
from decimal import Decimal
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from apps.inventory.models import (
    InventoryOperation,
    InventoryOperationKind,
    Material,
    MaterialLot,
    StockMovement,
    StockStatus,
    Stocktake,
    StocktakeDifferenceKind,
    StocktakeLine,
)

SKU_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._/-]*$")


class MaterialSerializer(serializers.ModelSerializer):
    total_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    available_quantity = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    nearest_expiry = serializers.DateField(allow_null=True, read_only=True)
    stock_status = serializers.ChoiceField(choices=StockStatus.choices, read_only=True)
    lots_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Material
        fields = (
            "id",
            "sku",
            "name",
            "category",
            "unit",
            "minimum_quantity",
            "is_active",
            "total_quantity",
            "available_quantity",
            "nearest_expiry",
            "stock_status",
            "lots_count",
            "version",
            "created_at",
            "updated_at",
        )


class MaterialListSerializer(serializers.Serializer):
    materials = MaterialSerializer(many=True)


class MaterialFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    category = serializers.CharField(required=False, allow_blank=True, max_length=100)
    stock_status = serializers.ChoiceField(
        required=False,
        choices=["all", *StockStatus.values],
        default="all",
    )
    status = serializers.ChoiceField(
        required=False,
        choices=["all", "active", "inactive"],
        default="all",
    )


class MaterialWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=48, allow_blank=False, required=False)
    name = serializers.CharField(max_length=180, allow_blank=False, required=False)
    category = serializers.CharField(max_length=100, allow_blank=False, required=False)
    unit = serializers.CharField(max_length=24, allow_blank=False, required=False)
    minimum_quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
        required=False,
    )
    is_active = serializers.BooleanField(required=False)

    def validate_sku(self, value: str) -> str:
        normalized = value.strip().upper()
        if not SKU_PATTERN.fullmatch(normalized):
            raise serializers.ValidationError(
                "Артикул може містити латинські літери, цифри, крапку, "
                "дефіс, скісну риску й підкреслення."
            )
        return normalized

    def validate_name(self, value: str) -> str:
        return value.strip()

    def validate_category(self, value: str) -> str:
        return value.strip()

    def validate_unit(self, value: str) -> str:
        return value.strip()


class MaterialCreateSerializer(MaterialWriteSerializer):
    sku = serializers.CharField(max_length=48, allow_blank=False)
    name = serializers.CharField(max_length=180, allow_blank=False)
    category = serializers.CharField(max_length=100, allow_blank=False)
    unit = serializers.CharField(max_length=24, allow_blank=False)
    minimum_quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
    )
    is_active = serializers.BooleanField(default=True)


class MaterialUpdateSerializer(MaterialWriteSerializer):
    version = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if len(attrs) == 1:
            raise serializers.ValidationError("Укажіть хоча б одну зміну.")
        return attrs


class MaterialLotSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)
    is_usable = serializers.BooleanField(read_only=True)
    status = serializers.CharField(read_only=True)
    fefo_rank = serializers.SerializerMethodField()

    class Meta:
        model = MaterialLot
        fields = (
            "id",
            "lot_number",
            "received_on",
            "expires_on",
            "initial_quantity",
            "current_quantity",
            "purchase_price_minor",
            "supplier_name",
            "is_expired",
            "is_usable",
            "status",
            "fefo_rank",
            "created_at",
        )

    def get_fefo_rank(self, lot: MaterialLot) -> int | None:
        ranks = self.context.get("fefo_ranks", {})
        return ranks.get(lot.pk) if lot.is_usable else None


class MaterialLotListSerializer(serializers.Serializer):
    lots = MaterialLotSerializer(many=True)


class ReceiptLineSerializer(serializers.Serializer):
    material_id = serializers.UUIDField()
    lot_number = serializers.CharField(max_length=80, allow_blank=False)
    expires_on = serializers.DateField(required=False, allow_null=True, default=None)
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )
    purchase_price_minor = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        min_value=0,
    )
    supplier_name = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=180,
    )
    allow_existing_lot = serializers.BooleanField(default=False)

    def validate_lot_number(self, value: str) -> str:
        return value.strip().upper()

    def validate_supplier_name(self, value: str) -> str:
        return value.strip()


class ReceiptCreateSerializer(serializers.Serializer):
    received_on = serializers.DateField(default=timezone.localdate)
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
    )
    lines = serializers.ListField(
        child=ReceiptLineSerializer(),
        allow_empty=False,
        max_length=50,
    )

    def validate_received_on(self, value: Any) -> Any:
        if value > timezone.localdate():
            raise serializers.ValidationError("Дата надходження не може бути в майбутньому.")
        return value

    def validate_comment(self, value: str) -> str:
        return value.strip()

    def validate_lines(self, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        identities = [(line["material_id"], line["lot_number"]) for line in lines]
        if len(identities) != len(set(identities)):
            raise serializers.ValidationError(
                "Одна партія матеріалу може бути вказана в надходженні лише один раз."
            )
        return lines


class ManualWriteoffLineSerializer(serializers.Serializer):
    lot_id = serializers.UUIDField()
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )


class ManualWriteoffCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, allow_blank=False)
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
    )
    lines = serializers.ListField(
        child=ManualWriteoffLineSerializer(),
        allow_empty=False,
        max_length=50,
    )

    def validate_reason(self, value: str) -> str:
        return value.strip()

    def validate_comment(self, value: str) -> str:
        return value.strip()

    def validate_lines(self, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lot_ids = [line["lot_id"] for line in lines]
        if len(lot_ids) != len(set(lot_ids)):
            raise serializers.ValidationError(
                "Одна партія може бути вказана у списанні лише один раз."
            )
        return lines


class StockMovementSerializer(serializers.ModelSerializer):
    material_id = serializers.UUIDField(source="lot.material_id", read_only=True)
    material_name = serializers.CharField(source="lot.material.name", read_only=True)
    material_unit = serializers.CharField(source="lot.material.unit", read_only=True)
    lot_number = serializers.CharField(source="lot.lot_number", read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "material_id",
            "material_name",
            "material_unit",
            "lot_id",
            "lot_number",
            "quantity_delta",
            "balance_after",
            "created_at",
        )


class InventoryOperationSerializer(serializers.ModelSerializer):
    movements = StockMovementSerializer(many=True, read_only=True)
    replayed = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    movement_count = serializers.SerializerMethodField()

    class Meta:
        model = InventoryOperation
        fields = (
            "id",
            "public_number",
            "kind",
            "status",
            "created_by_id",
            "created_by_name",
            "created_by_email",
            "reason",
            "comment",
            "posted_at",
            "movements",
            "movement_count",
            "replayed",
        )

    def get_replayed(self, operation: InventoryOperation) -> bool:
        return bool(self.context.get("replayed", False))

    def get_created_by_name(self, operation: InventoryOperation) -> str:
        return operation.created_by.get_full_name() or operation.created_by.email

    def get_movement_count(self, operation: InventoryOperation) -> int:
        return len(operation.movements.all())


class StocktakePreviewLotSerializer(serializers.ModelSerializer):
    material_id = serializers.UUIDField(source="material.id", read_only=True)
    material_sku = serializers.CharField(source="material.sku", read_only=True)
    material_name = serializers.CharField(source="material.name", read_only=True)
    material_unit = serializers.CharField(source="material.unit", read_only=True)
    system_quantity = serializers.DecimalField(
        source="current_quantity",
        max_digits=12,
        decimal_places=3,
        read_only=True,
    )
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = MaterialLot
        fields = (
            "id",
            "material_id",
            "material_sku",
            "material_name",
            "material_unit",
            "lot_number",
            "system_quantity",
            "purchase_price_minor",
            "expires_on",
            "is_expired",
        )


class StocktakePreviewSerializer(serializers.Serializer):
    lots = StocktakePreviewLotSerializer(many=True)


class StocktakeCreateLineSerializer(serializers.Serializer):
    lot_id = serializers.UUIDField()
    actual_quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal("0"),
    )


class StocktakeCreateSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
    )
    lines = serializers.ListField(
        child=StocktakeCreateLineSerializer(),
        allow_empty=False,
        max_length=200,
    )

    def validate_comment(self, value: str) -> str:
        return value.strip()

    def validate_lines(self, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lot_ids = [line["lot_id"] for line in lines]
        if len(lot_ids) != len(set(lot_ids)):
            raise serializers.ValidationError(
                "Одна партія може бути вказана в інвентаризації лише один раз."
            )
        return lines


class StocktakeLineSerializer(serializers.ModelSerializer):
    difference = serializers.DecimalField(max_digits=13, decimal_places=3, read_only=True)
    difference_kind = serializers.ChoiceField(
        choices=StocktakeDifferenceKind.choices,
        read_only=True,
    )
    adjustment_value_minor = serializers.IntegerField(allow_null=True, read_only=True)

    class Meta:
        model = StocktakeLine
        fields = (
            "id",
            "lot_id",
            "material_sku",
            "material_name",
            "material_unit",
            "lot_number",
            "system_quantity",
            "actual_quantity",
            "difference",
            "difference_kind",
            "purchase_price_minor",
            "adjustment_value_minor",
        )


class StocktakeSerializer(serializers.ModelSerializer):
    lines = StocktakeLineSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    posted_by_name = serializers.SerializerMethodField()
    line_count = serializers.SerializerMethodField()
    adjusted_line_count = serializers.SerializerMethodField()
    surplus_line_count = serializers.SerializerMethodField()
    shortage_line_count = serializers.SerializerMethodField()
    adjustment_value_minor = serializers.SerializerMethodField()
    unpriced_adjustment_count = serializers.SerializerMethodField()
    replayed = serializers.SerializerMethodField()

    class Meta:
        model = Stocktake
        fields = (
            "id",
            "public_number",
            "status",
            "created_by_id",
            "created_by_name",
            "posted_by_id",
            "posted_by_name",
            "comment",
            "operation_id",
            "created_at",
            "posted_at",
            "line_count",
            "adjusted_line_count",
            "surplus_line_count",
            "shortage_line_count",
            "adjustment_value_minor",
            "unpriced_adjustment_count",
            "lines",
            "replayed",
        )

    def _lines(self, stocktake: Stocktake) -> list[StocktakeLine]:
        return list(stocktake.lines.all())

    def get_created_by_name(self, stocktake: Stocktake) -> str:
        return stocktake.created_by.get_full_name() or stocktake.created_by.email

    def get_posted_by_name(self, stocktake: Stocktake) -> str | None:
        if stocktake.posted_by is None:
            return None
        return stocktake.posted_by.get_full_name() or stocktake.posted_by.email

    def get_line_count(self, stocktake: Stocktake) -> int:
        return len(self._lines(stocktake))

    def get_adjusted_line_count(self, stocktake: Stocktake) -> int:
        return sum(line.difference != 0 for line in self._lines(stocktake))

    def get_surplus_line_count(self, stocktake: Stocktake) -> int:
        return sum(line.difference > 0 for line in self._lines(stocktake))

    def get_shortage_line_count(self, stocktake: Stocktake) -> int:
        return sum(line.difference < 0 for line in self._lines(stocktake))

    def get_adjustment_value_minor(self, stocktake: Stocktake) -> int:
        return sum(
            line.adjustment_value_minor or 0
            for line in self._lines(stocktake)
            if line.adjustment_value_minor is not None
        )

    def get_unpriced_adjustment_count(self, stocktake: Stocktake) -> int:
        return sum(
            line.difference != 0 and line.adjustment_value_minor is None
            for line in self._lines(stocktake)
        )

    def get_replayed(self, stocktake: Stocktake) -> bool:
        return bool(self.context.get("replayed", False))


class MovementFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    kind = serializers.ChoiceField(
        required=False,
        choices=["all", *InventoryOperationKind.values],
        default="all",
    )
    material_id = serializers.UUIDField(required=False)
    actor = serializers.CharField(required=False, allow_blank=True, max_length=255)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    cursor = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if (
            attrs.get("date_from")
            and attrs.get("date_to")
            and (attrs["date_from"] > attrs["date_to"])
        ):
            raise serializers.ValidationError("Початкова дата не може бути пізніше кінцевої.")
        return attrs


class MovementJournalItemSerializer(serializers.ModelSerializer):
    operation_id = serializers.UUIDField(source="operation.id", read_only=True)
    operation_public_number = serializers.CharField(
        source="operation.public_number", read_only=True
    )
    operation_kind = serializers.ChoiceField(
        source="operation.kind",
        choices=InventoryOperationKind.choices,
        read_only=True,
    )
    operation_reason = serializers.CharField(source="operation.reason", read_only=True)
    operation_comment = serializers.CharField(source="operation.comment", read_only=True)
    posted_at = serializers.DateTimeField(source="operation.posted_at", read_only=True)
    actor_id = serializers.IntegerField(source="operation.created_by_id", read_only=True)
    actor_name = serializers.SerializerMethodField()
    actor_email = serializers.EmailField(source="operation.created_by.email", read_only=True)
    material_id = serializers.UUIDField(source="lot.material_id", read_only=True)
    material_sku = serializers.CharField(source="lot.material.sku", read_only=True)
    material_name = serializers.CharField(source="lot.material.name", read_only=True)
    material_unit = serializers.CharField(source="lot.material.unit", read_only=True)
    lot_number = serializers.CharField(source="lot.lot_number", read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "operation_id",
            "operation_public_number",
            "operation_kind",
            "operation_reason",
            "operation_comment",
            "posted_at",
            "actor_id",
            "actor_name",
            "actor_email",
            "material_id",
            "material_sku",
            "material_name",
            "material_unit",
            "lot_id",
            "lot_number",
            "quantity_delta",
            "balance_after",
            "created_at",
        )

    def get_actor_name(self, movement: StockMovement) -> str:
        actor = movement.operation.created_by
        return actor.get_full_name() or actor.email


class MovementJournalResponseSerializer(serializers.Serializer):
    movements = MovementJournalItemSerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)
