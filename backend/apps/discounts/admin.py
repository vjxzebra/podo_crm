from django.contrib import admin

from apps.discounts.models import (
    Discount,
    LoyaltyPolicy,
    PatientLoyaltyState,
    VisitLoyaltyEvent,
)


class NoDeleteAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(Discount)
class DiscountAdmin(NoDeleteAdmin):
    list_display = ("name", "percent", "is_active", "version", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(LoyaltyPolicy)
class LoyaltyPolicyAdmin(NoDeleteAdmin):
    list_display = ("key", "is_active", "every_n", "discount", "version", "started_at")
    readonly_fields = tuple(field.name for field in LoyaltyPolicy._meta.fields)

    def has_add_permission(self, request):  # type: ignore[no-untyped-def]
        return False

    def has_change_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


@admin.register(PatientLoyaltyState)
class PatientLoyaltyStateAdmin(NoDeleteAdmin):
    list_display = ("patient", "completed_count", "version", "updated_at")
    readonly_fields = ("patient", "completed_count", "version", "updated_at")


@admin.register(VisitLoyaltyEvent)
class VisitLoyaltyEventAdmin(NoDeleteAdmin):
    list_display = ("visit", "patient", "sequence_number", "eligible", "created_at")
    readonly_fields = tuple(field.name for field in VisitLoyaltyEvent._meta.fields)
