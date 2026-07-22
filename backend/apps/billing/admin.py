from django.contrib import admin
from django.http import HttpRequest

from apps.billing.models import (
    CashAdjustment,
    CashLedgerEntry,
    CashShift,
    Payment,
    Receivable,
    Refund,
)


@admin.register(Receivable)
class ReceivableAdmin(admin.ModelAdmin):
    list_display = ("id", "visit", "amount_minor", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("id", "visit", "amount_minor", "status", "created_at", "updated_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Receivable | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Receivable | None = None) -> bool:
        return False


@admin.register(CashShift)
class CashShiftAdmin(admin.ModelAdmin):
    list_display = ("public_number", "employee", "status", "opened_at", "closed_at")
    list_filter = ("status",)
    search_fields = ("public_number", "employee__email")
    readonly_fields = (
        "id",
        "public_number",
        "employee",
        "employee_name_snapshot",
        "employee_email_snapshot",
        "employee_role_snapshot",
        "status",
        "opened_at",
        "closed_at",
        "expected_cash_at_close_minor",
        "actual_cash_at_close_minor",
        "discrepancy_minor",
        "close_comment",
        "closed_by",
        "closed_by_name_snapshot",
        "closed_by_email_snapshot",
        "closed_by_role_snapshot",
        "close_idempotency_key",
        "close_payload_hash",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: CashShift | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: CashShift | None = None) -> bool:
        return False


@admin.register(CashLedgerEntry)
class CashLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "public_number",
        "cash_shift",
        "kind",
        "amount_minor",
        "payment_method",
        "created_by",
        "posted_at",
    )
    list_filter = ("kind", "payment_method")
    search_fields = ("public_number", "cash_shift__public_number", "created_by__email")
    readonly_fields = (
        "id",
        "public_number",
        "cash_shift",
        "created_by",
        "actor_name_snapshot",
        "actor_email_snapshot",
        "actor_role_snapshot",
        "kind",
        "amount_minor",
        "payment_method",
        "idempotency_key",
        "payload_hash",
        "posted_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: CashLedgerEntry | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: CashLedgerEntry | None = None
    ) -> bool:
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "ledger_entry", "receivable", "comment")
    search_fields = (
        "ledger_entry__public_number",
        "visit_public_number_snapshot",
        "patient_public_number_snapshot",
        "patient_name_snapshot",
    )
    readonly_fields = (
        "id",
        "ledger_entry",
        "receivable",
        "comment",
        "patient_id_snapshot",
        "patient_public_number_snapshot",
        "patient_name_snapshot",
        "patient_phone_snapshot",
        "visit_public_number_snapshot",
        "visit_completed_at_snapshot",
        "visit_payment_handoff_requested_snapshot",
        "visit_total_minor_snapshot",
        "specialist_id_snapshot",
        "specialist_name_snapshot",
        "employee_name_snapshot",
        "employee_email_snapshot",
        "services_snapshot",
        "services_search_snapshot",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Payment | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Payment | None = None) -> bool:
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id", "ledger_entry", "original_payment", "reason")
    search_fields = (
        "ledger_entry__public_number",
        "original_payment__ledger_entry__public_number",
        "original_payment__patient_public_number_snapshot",
        "original_payment__patient_name_snapshot",
        "reason",
    )
    readonly_fields = (
        "id",
        "ledger_entry",
        "original_payment",
        "reason",
        "employee_name_snapshot",
        "employee_email_snapshot",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Refund | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Refund | None = None) -> bool:
        return False


@admin.register(CashAdjustment)
class CashAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("id", "ledger_entry", "reason", "comment")
    search_fields = (
        "ledger_entry__public_number",
        "reason",
        "comment",
    )
    readonly_fields = (
        "id",
        "ledger_entry",
        "reason",
        "comment",
        "employee_name_snapshot",
        "employee_email_snapshot",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: CashAdjustment | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: CashAdjustment | None = None
    ) -> bool:
        return False
