from django.contrib import admin
from django.http import HttpRequest

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "kind", "created_at", "read_at")
    list_filter = ("kind", "tone", "is_important", "read_at")
    search_fields = ("title", "message", "event_key", "recipient__email")
    readonly_fields = (
        "id",
        "recipient",
        "event_key",
        "kind",
        "title",
        "message",
        "tone",
        "is_important",
        "deep_link",
        "occurred_at",
        "created_at",
        "read_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Notification | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Notification | None = None) -> bool:
        return False
