from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import PasswordResetRequest, User


@admin.register(User)
class PodoriaUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "role", "is_active", "must_change_password", "is_staff")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Профіль",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "role",
                    "must_change_password",
                    "temporary_password_expires_at",
                )
            },
        ),
        (
            "Доступ",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Системні дати", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "role", "password1", "password2"),
            },
        ),
    )
    search_fields = ("email", "first_name", "last_name")


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "requested_at", "resolved_at", "resolved_by")
    list_filter = ("resolved_at",)
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = ("user", "requested_at", "resolved_at", "resolved_by")
