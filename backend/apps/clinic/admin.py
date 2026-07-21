from django.contrib import admin

from apps.clinic.models import (
    AppointmentStatusConfig,
    ClinicBreak,
    ClinicProfile,
    ClinicWorkday,
    Room,
    Service,
)


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


@admin.register(AppointmentStatusConfig)
class AppointmentStatusConfigAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "label",
        "color",
        "manual_admin",
        "manual_reception",
        "manual_podologist",
        "version",
    )
    readonly_fields = ("code",)

    def has_delete_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False


class ClinicBreakInline(admin.TabularInline):
    model = ClinicBreak
    extra = 0


@admin.register(ClinicWorkday)
class ClinicWorkdayAdmin(admin.ModelAdmin):
    list_display = ("weekday", "is_working", "start_time", "end_time", "version")
    inlines = (ClinicBreakInline,)
