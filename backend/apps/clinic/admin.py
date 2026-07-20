from django.contrib import admin

from apps.clinic.models import ClinicProfile, Room, Service


@admin.register(ClinicProfile)
class ClinicProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "version", "updated_at")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "version", "updated_at")
    list_filter = ("is_active",)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "duration_minutes",
        "price_minor",
        "color",
        "is_active",
        "version",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "name")
