from django.contrib import admin
from django.http import HttpRequest

from apps.notifications.models import Notification, NotificationTelegramDelivery


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


@admin.register(NotificationTelegramDelivery)
class NotificationTelegramDeliveryAdmin(admin.ModelAdmin):
    list_display = ("notification", "subscription", "status", "attempt_count", "updated_at")
    list_filter = ("status",)
    search_fields = ("notification__title", "subscription__user__email")
    readonly_fields = (
        "id",
        "notification",
        "subscription",
        "chat_id",
        "message_id",
        "status",
        "attempt_count",
        "next_attempt_at",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: NotificationTelegramDelivery | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: NotificationTelegramDelivery | None = None,
    ) -> bool:
        return False
