from django.contrib import admin
from django.http import HttpRequest

from apps.inventory.models import (
    InventoryOperation,
    Material,
    MaterialLot,
    StockMovement,
    Stocktake,
    StocktakeLine,
)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "unit", "minimum_quantity", "is_active")
    list_filter = ("is_active", "category")
    search_fields = ("sku", "name")


@admin.register(MaterialLot)
class MaterialLotAdmin(admin.ModelAdmin):
    list_display = (
        "lot_number",
        "material",
        "received_on",
        "expires_on",
        "current_quantity",
        "supplier_name",
    )
    search_fields = ("lot_number", "material__sku", "material__name", "supplier_name")
    readonly_fields = tuple(field.name for field in MaterialLot._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: MaterialLot | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: MaterialLot | None = None) -> bool:
        return False


@admin.register(InventoryOperation)
class InventoryOperationAdmin(admin.ModelAdmin):
    list_display = ("public_number", "kind", "status", "created_by", "posted_at")
    list_filter = ("kind", "status")
    search_fields = ("public_number", "idempotency_key", "created_by__email")
    readonly_fields = tuple(field.name for field in InventoryOperation._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: InventoryOperation | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: InventoryOperation | None = None
    ) -> bool:
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("operation", "lot", "quantity_delta", "balance_after", "created_at")
    search_fields = ("operation__public_number", "lot__lot_number", "lot__material__sku")
    readonly_fields = tuple(field.name for field in StockMovement._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: StockMovement | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: StockMovement | None = None) -> bool:
        return False


@admin.register(Stocktake)
class StocktakeAdmin(admin.ModelAdmin):
    list_display = (
        "public_number",
        "status",
        "created_by",
        "created_at",
        "posted_by",
        "posted_at",
    )
    list_filter = ("status",)
    search_fields = ("public_number", "created_by__email", "posted_by__email")
    readonly_fields = tuple(field.name for field in Stocktake._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Stocktake | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Stocktake | None = None) -> bool:
        return False


@admin.register(StocktakeLine)
class StocktakeLineAdmin(admin.ModelAdmin):
    list_display = (
        "stocktake",
        "material_sku",
        "lot_number",
        "system_quantity",
        "actual_quantity",
    )
    search_fields = ("stocktake__public_number", "material_sku", "material_name", "lot_number")
    readonly_fields = tuple(field.name for field in StocktakeLine._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: StocktakeLine | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: StocktakeLine | None = None) -> bool:
        return False
