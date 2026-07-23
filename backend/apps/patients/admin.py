from django.contrib import admin

from apps.patients.models import Patient, PatientMedicalProfile


class PatientMedicalProfileInline(admin.StackedInline):
    model = PatientMedicalProfile
    extra = 0


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "public_number",
        "last_name",
        "first_name",
        "phone",
        "primary_podologist",
        "created_at",
    )
    search_fields = ("public_number", "first_name", "last_name", "phone", "normalized_phone")
    list_select_related = ("primary_podologist",)
    readonly_fields = ("public_number", "normalized_phone", "created_at", "updated_at")
    inlines = (PatientMedicalProfileInline,)
