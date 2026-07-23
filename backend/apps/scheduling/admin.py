from django.contrib import admin

from apps.scheduling.models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("public_number", "patient", "specialist", "room", "status", "time_range")
    list_filter = ("status", "specialist", "room")
    search_fields = (
        "public_number",
        "patient__first_name",
        "patient__last_name",
        "patient__phone",
    )
