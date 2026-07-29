from django.urls import path

from apps.billing.views import (
    CashMovementCreateView,
    CashShiftClosePreviewView,
    CashShiftCloseView,
    CashShiftDetailView,
    CashShiftExportView,
    CashShiftHistoryExportView,
    CashShiftOpenView,
    CurrentCashShiftView,
    FinanceOperationDetailView,
    FinanceOperationExportView,
    FinanceOperationListView,
    PaymentCreateView,
    PaymentReceiptView,
    RefundCreateView,
)

urlpatterns = [
    path("cash-shifts", CashShiftOpenView.as_view(), name="cash-shift-open"),
    path(
        "cash-shifts/current",
        CurrentCashShiftView.as_view(),
        name="cash-shift-current",
    ),
    path(
        "cash-shifts/export",
        CashShiftHistoryExportView.as_view(),
        name="cash-shift-history-export",
    ),
    path(
        "cash-shifts/<uuid:shift_id>/close-preview",
        CashShiftClosePreviewView.as_view(),
        name="cash-shift-close-preview",
    ),
    path(
        "cash-shifts/<uuid:shift_id>/close",
        CashShiftCloseView.as_view(),
        name="cash-shift-close",
    ),
    path(
        "cash-shifts/<uuid:shift_id>/export",
        CashShiftExportView.as_view(),
        name="cash-shift-export",
    ),
    path(
        "cash-shifts/<uuid:shift_id>",
        CashShiftDetailView.as_view(),
        name="cash-shift-detail",
    ),
    path(
        "finance/operations/export",
        FinanceOperationExportView.as_view(),
        name="finance-operation-export",
    ),
    path(
        "finance/operations",
        FinanceOperationListView.as_view(),
        name="finance-operation-list",
    ),
    path(
        "finance/operations/<str:operation_type>/<uuid:operation_id>",
        FinanceOperationDetailView.as_view(),
        name="finance-operation-detail",
    ),
    path("payments", PaymentCreateView.as_view(), name="payment-create"),
    path(
        "payments/<uuid:payment_id>/receipt",
        PaymentReceiptView.as_view(),
        name="payment-receipt",
    ),
    path(
        "payments/<uuid:payment_id>/refunds",
        RefundCreateView.as_view(),
        name="refund-create",
    ),
    path("cash-movements", CashMovementCreateView.as_view(), name="cash-movement-create"),
]
