from collections.abc import Mapping
from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from apps.accounts.models import UserRole
from apps.billing.models import (
    CashLedgerEntryKind,
    CashShiftStatus,
    PaymentMethod,
    ReceivableStatus,
)

CASH_MOVEMENT_TYPES = (
    CashLedgerEntryKind.DEPOSIT,
    CashLedgerEntryKind.WITHDRAWAL,
)
POSTED_FINANCE_STATUSES = ("POSTED",)


class CashLedgerEntrySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    kind = serializers.ChoiceField(choices=CashLedgerEntryKind.choices)
    amount_minor = serializers.IntegerField(min_value=1)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        allow_null=True,
    )
    actor_id = serializers.IntegerField(min_value=1)
    actor_name = serializers.CharField()
    actor_email = serializers.EmailField()
    posted_at = serializers.DateTimeField()


class CashShiftEmployeeSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(min_value=1)
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=UserRole.choices)


class CashShiftReconciliationSerializer(serializers.Serializer[Any]):
    expected_cash_minor = serializers.IntegerField(min_value=0)
    actual_cash_minor = serializers.IntegerField(min_value=0)
    discrepancy_minor = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True)
    closed_by = CashShiftEmployeeSerializer()


class CashShiftTotalsSerializer(serializers.Serializer[Any]):
    operations_count = serializers.IntegerField(min_value=0)
    payment_count = serializers.IntegerField(min_value=0)
    refund_count = serializers.IntegerField(min_value=0)
    payments_total_minor = serializers.IntegerField(min_value=0)
    refunds_total_minor = serializers.IntegerField(min_value=0)
    revenue_minor = serializers.IntegerField()
    cash_payments_minor = serializers.IntegerField(min_value=0)
    cash_refunds_minor = serializers.IntegerField(min_value=0)
    card_payments_minor = serializers.IntegerField(min_value=0)
    card_refunds_minor = serializers.IntegerField(min_value=0)
    transfer_payments_minor = serializers.IntegerField(min_value=0)
    transfer_refunds_minor = serializers.IntegerField(min_value=0)
    deposits_minor = serializers.IntegerField(min_value=0)
    withdrawals_minor = serializers.IntegerField(min_value=0)
    expected_cash_minor = serializers.IntegerField()


class CashShiftProjectionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    status = serializers.ChoiceField(choices=CashShiftStatus.choices)
    employee = CashShiftEmployeeSerializer()
    opened_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    totals = CashShiftTotalsSerializer()
    reconciliation = CashShiftReconciliationSerializer(allow_null=True)
    entries = CashLedgerEntrySerializer(many=True)


class CashShiftSummarySerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    status = serializers.ChoiceField(choices=CashShiftStatus.choices)
    employee = CashShiftEmployeeSerializer()
    opened_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    totals = CashShiftTotalsSerializer()
    reconciliation = CashShiftReconciliationSerializer(allow_null=True)


class CashShiftCurrentResponseSerializer(serializers.Serializer[Any]):
    shift = CashShiftProjectionSerializer(allow_null=True)


class StrictInputSerializer(serializers.Serializer[Any]):
    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, Mapping):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError({field: ["Невідоме поле."] for field in unknown})
        return super().to_internal_value(data)


@extend_schema_field({"type": "boolean", "enum": [True]})
class LiteralTrueField(serializers.Field):
    default_error_messages = {"invalid": "Підтвердіть перерахунок готівки."}

    def to_internal_value(self, data: Any) -> bool:
        if data is not True:
            self.fail("invalid")
        return True

    def to_representation(self, value: Any) -> bool:
        return bool(value)


class CashShiftCloseSerializer(StrictInputSerializer):
    actual_cash_minor = serializers.IntegerField(
        min_value=0,
        max_value=9_007_199_254_740_991,
    )
    expected_operations_count = serializers.IntegerField(
        min_value=0,
        max_value=2_147_483_647,
    )
    cash_count_confirmed = LiteralTrueField()
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
        trim_whitespace=True,
    )


class CashShiftFilterSerializer(serializers.Serializer[Any]):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        trim_whitespace=True,
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(required=False, choices=CashShiftStatus.choices)
    employee_id = serializers.IntegerField(required=False, min_value=1)
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=2000)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if (
            attrs.get("date_from") is not None
            and attrs.get("date_to") is not None
            and attrs["date_from"] > attrs["date_to"]
        ):
            raise serializers.ValidationError(
                {"date_to": ["Кінцева дата не може бути раніше початкової."]}
            )
        return attrs


class CashShiftHistoryExportFilterSerializer(serializers.Serializer[Any]):
    search = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        trim_whitespace=True,
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(required=False, choices=CashShiftStatus.choices)
    employee_id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise serializers.ValidationError(
                {"date_to": ["Кінцева дата не може бути раніше початкової."]}
            )
        if date_from is not None and date_to is not None and (date_to - date_from).days > 365:
            raise serializers.ValidationError(
                {"date_to": ["Період експорту не може перевищувати 366 днів."]}
            )
        return attrs


class CashShiftListResponseSerializer(serializers.Serializer[Any]):
    shifts = CashShiftSummarySerializer(many=True)
    next_cursor = serializers.CharField(allow_null=True)


class CashShiftUnpaidSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField(min_value=0)
    total_minor = serializers.IntegerField(min_value=0)


class CashShiftClosePreviewResponseSerializer(serializers.Serializer[Any]):
    shift = CashShiftProjectionSerializer()
    unpaid = CashShiftUnpaidSerializer()


class CashShiftCloseResponseSerializer(serializers.Serializer[Any]):
    shift = CashShiftProjectionSerializer()
    replayed = serializers.BooleanField()


class PaymentCreateSerializer(StrictInputSerializer):
    visit_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
        trim_whitespace=True,
    )


class RefundCreateSerializer(StrictInputSerializer):
    reason = serializers.CharField(
        min_length=1,
        max_length=500,
        trim_whitespace=True,
    )


class CashMovementCreateSerializer(StrictInputSerializer):
    type = serializers.ChoiceField(choices=CASH_MOVEMENT_TYPES)
    amount_minor = serializers.IntegerField(
        min_value=1,
        max_value=9_007_199_254_740_991,
    )
    reason = serializers.CharField(
        min_length=1,
        max_length=500,
        trim_whitespace=True,
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=2000,
        trim_whitespace=True,
    )


class FinanceOperationFilterSerializer(serializers.Serializer[Any]):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    type = serializers.ChoiceField(
        required=False,
        choices=CashLedgerEntryKind.values,
    )
    status = serializers.ChoiceField(
        required=False,
        choices=(*ReceivableStatus.values, "POSTED"),
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    payment_method = serializers.ChoiceField(
        required=False,
        choices=PaymentMethod.values,
    )
    patient_id = serializers.UUIDField(required=False)
    amount_minor = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=9_007_199_254_740_991,
    )
    refundable_only = serializers.BooleanField(required=False, default=False)
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=2000)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if (
            attrs.get("date_from") is not None
            and attrs.get("date_to") is not None
            and attrs["date_from"] > attrs["date_to"]
        ):
            raise serializers.ValidationError(
                {"date_to": ["Кінцева дата не може бути раніше початкової."]}
            )
        if attrs.get("refundable_only"):
            errors = {}
            if attrs.get("type") not in (None, CashLedgerEntryKind.PAYMENT):
                errors["type"] = ["Для refundable_only доступний лише тип PAYMENT."]
            if attrs.get("status") not in (None, ReceivableStatus.PAID):
                errors["status"] = ["Для refundable_only доступний лише статус PAID."]
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class FinanceOperationExportFilterSerializer(serializers.Serializer[Any]):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    type = serializers.ChoiceField(
        required=False,
        choices=CashLedgerEntryKind.values,
    )
    status = serializers.ChoiceField(
        required=False,
        choices=(*ReceivableStatus.values, "POSTED"),
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    payment_method = serializers.ChoiceField(
        required=False,
        choices=PaymentMethod.values,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from is not None and date_to is not None:
            if date_from > date_to:
                raise serializers.ValidationError(
                    {"date_to": ["Кінцева дата не може бути раніше початкової."]}
                )
            if (date_to - date_from).days + 1 > 366:
                raise serializers.ValidationError(
                    {"date_to": ["Період export не може перевищувати 366 днів."]}
                )
        return attrs


class FinancePatientSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    display_name = serializers.CharField()
    phone = serializers.CharField()


class FinanceSpecialistSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(min_value=1)
    name = serializers.CharField()


class FinanceServiceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    unit_price_minor = serializers.IntegerField(min_value=0)
    line_total_minor = serializers.IntegerField(min_value=0)


class FinanceVisitSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()
    completed_at = serializers.DateTimeField()
    payment_handoff_requested = serializers.BooleanField()
    total_minor = serializers.IntegerField(min_value=0)
    specialist = FinanceSpecialistSerializer()
    services = FinanceServiceSerializer(many=True)


class FinancePaymentActorSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField(min_value=1)
    name = serializers.CharField()


class FinancePaymentShiftSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    public_number = serializers.CharField()


class FinancePaymentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    ledger_entry_id = serializers.UUIDField()
    public_number = serializers.CharField()
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    comment = serializers.CharField(allow_blank=True)
    posted_at = serializers.DateTimeField()
    actor = FinancePaymentActorSerializer()
    cash_shift = FinancePaymentShiftSerializer()


class FinanceRefundSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    ledger_entry_id = serializers.UUIDField()
    public_number = serializers.CharField()
    reason = serializers.CharField()
    posted_at = serializers.DateTimeField()
    actor = FinancePaymentActorSerializer()
    cash_shift = FinancePaymentShiftSerializer()


class FinanceCashAdjustmentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    ledger_entry_id = serializers.UUIDField()
    public_number = serializers.CharField()
    reason = serializers.CharField()
    comment = serializers.CharField(allow_blank=True)
    posted_at = serializers.DateTimeField()
    actor = FinancePaymentActorSerializer()
    cash_shift = FinancePaymentShiftSerializer()


class FinancePaymentOperationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=(CashLedgerEntryKind.PAYMENT,))
    status = serializers.ChoiceField(choices=ReceivableStatus.choices)
    occurred_at = serializers.DateTimeField()
    amount_minor = serializers.IntegerField(min_value=0)
    patient = FinancePatientSerializer()
    visit = FinanceVisitSerializer()
    payment = FinancePaymentSerializer(allow_null=True)
    refund = FinanceRefundSerializer(allow_null=True)


class FinanceRefundOperationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=(CashLedgerEntryKind.REFUND,))
    status = serializers.ChoiceField(choices=POSTED_FINANCE_STATUSES)
    occurred_at = serializers.DateTimeField()
    amount_minor = serializers.IntegerField(min_value=1)
    patient = FinancePatientSerializer()
    visit = FinanceVisitSerializer()
    original_payment = FinancePaymentSerializer()
    refund = FinanceRefundSerializer()


class FinanceCashAdjustmentOperationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=CASH_MOVEMENT_TYPES)
    status = serializers.ChoiceField(choices=POSTED_FINANCE_STATUSES)
    occurred_at = serializers.DateTimeField()
    amount_minor = serializers.IntegerField(min_value=1)
    cash_adjustment = FinanceCashAdjustmentSerializer()


FINANCE_OPERATION_SERIALIZER = PolymorphicProxySerializer(
    component_name="FinanceOperation",
    serializers={
        "PAYMENT": FinancePaymentOperationSerializer,
        "REFUND": FinanceRefundOperationSerializer,
        "DEPOSIT": FinanceCashAdjustmentOperationSerializer,
        "WITHDRAWAL": FinanceCashAdjustmentOperationSerializer,
    },
    resource_type_field_name="type",
)


@extend_schema_field(FINANCE_OPERATION_SERIALIZER)
class FinanceOperationField(serializers.Field):
    def to_representation(self, value: Any) -> dict[str, Any]:
        operation_type = value.get("type") if isinstance(value, Mapping) else None
        if operation_type == CashLedgerEntryKind.PAYMENT:
            return dict(FinancePaymentOperationSerializer(value).data)
        if operation_type == CashLedgerEntryKind.REFUND:
            return dict(FinanceRefundOperationSerializer(value).data)
        if operation_type in (
            CashLedgerEntryKind.DEPOSIT,
            CashLedgerEntryKind.WITHDRAWAL,
        ):
            return dict(FinanceCashAdjustmentOperationSerializer(value).data)
        raise serializers.ValidationError("Невідомий тип фінансової операції.")


class FinanceOperationListResponseSerializer(serializers.Serializer[Any]):
    operations = serializers.ListField(child=FinanceOperationField())
    next_cursor = serializers.CharField(allow_null=True)


class PaymentCreateResponseSerializer(serializers.Serializer[Any]):
    operation = FinancePaymentOperationSerializer()
    replayed = serializers.BooleanField()


class RefundCreateResponseSerializer(serializers.Serializer[Any]):
    operation = FinanceRefundOperationSerializer()
    replayed = serializers.BooleanField()


class CashMovementCreateResponseSerializer(serializers.Serializer[Any]):
    operation = FinanceCashAdjustmentOperationSerializer()
    replayed = serializers.BooleanField()
