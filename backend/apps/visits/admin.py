from django.contrib import admin
from django.http import HttpRequest

from apps.visits.models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "public_number",
        "appointment",
        "patient",
        "specialist",
        "status",
        "version",
        "started_at",
    )
    list_filter = ("status", "specialist")
    search_fields = (
        "public_number",
        "appointment__public_number",
        "patient__public_number",
        "patient__first_name",
        "patient__last_name",
    )
    readonly_fields = tuple(field.name for field in Visit._meta.fields)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Visit | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Visit | None = None) -> bool:
        return False
