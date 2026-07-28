from django.contrib import admin

from apps.booking_requests.models import (
    BookingRequest,
    BookingRequestApiCredential,
    BookingRequestSubmission,
)


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "public_number",
        "source",
        "status",
        "client_name",
        "service",
        "created_at",
        "processed_at",
    )
    list_filter = ("source", "status")
    search_fields = (
        "public_number",
        "client_name",
        "phone",
        "service",
        "contact_handle",
    )
    readonly_fields = (
        "id",
        "public_number",
        "source",
        "client_name",
        "phone",
        "phone_normalized",
        "service",
        "contact_handle",
        "message",
        "preferred_at",
        "external_reference",
        "created_at",
        "updated_at",
    )


@admin.register(BookingRequestApiCredential)
class BookingRequestApiCredentialAdmin(admin.ModelAdmin):
    list_display = ("is_configured", "token_hint", "rotated_at", "version")
    exclude = ("token_digest",)
    readonly_fields = (
        "id",
        "token_hint",
        "rotated_by",
        "rotated_by_display_name",
        "rotated_at",
        "version",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object | None = None) -> bool:
        return False


@admin.register(BookingRequestSubmission)
class BookingRequestSubmissionAdmin(admin.ModelAdmin):
    list_display = ("booking_request", "idempotency_key", "created_at")
    search_fields = ("booking_request__public_number", "idempotency_key")
    readonly_fields = (
        "id",
        "credential",
        "idempotency_key",
        "payload_hash",
        "booking_request",
        "created_at",
    )

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object | None = None) -> bool:
        return False
