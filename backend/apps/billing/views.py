from uuid import UUID

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasCashShiftAccess, HasFinanceAccess, IsAdmin
from apps.billing import exports as billing_exports
from apps.billing.models import CashLedgerEntryKind
from apps.billing.receipts import render_payment_receipt_pdf
from apps.billing.selectors import payment_receipts_visible_to, payment_receivables_visible_to
from apps.billing.serializers import (
    CashMovementCreateResponseSerializer,
    CashMovementCreateSerializer,
    CashShiftClosePreviewResponseSerializer,
    CashShiftCloseResponseSerializer,
    CashShiftCloseSerializer,
    CashShiftCurrentResponseSerializer,
    CashShiftFilterSerializer,
    CashShiftHistoryExportFilterSerializer,
    CashShiftListResponseSerializer,
    CashShiftProjectionSerializer,
    FinanceOperationExportFilterSerializer,
    FinanceOperationFilterSerializer,
    FinanceOperationListResponseSerializer,
    FinancePaymentOperationSerializer,
    PaymentCreateResponseSerializer,
    PaymentCreateSerializer,
    RefundCreateResponseSerializer,
    RefundCreateSerializer,
)
from apps.billing.services import (
    cash_shift_close_preview,
    cash_shift_detail,
    cash_shift_export_snapshot,
    cash_shift_history_export_rows,
    cash_shift_history_page,
    cash_shift_projection,
    close_cash_shift,
    current_cash_shift,
    finance_cash_adjustment_operation_read_model,
    finance_operations_export_rows,
    finance_operations_page,
    finance_payment_operation_read_model,
    finance_refund_operation_read_model,
    open_cash_shift,
    payment_operation_by_receivable_id,
    post_cash_movement,
    post_payment,
    post_refund,
)
from config.api.csv import SafeCsvRenderer
from config.api.exceptions import ApiProblem
from config.api.pdf import SafePdfRenderer
from config.api.serializers import ErrorEnvelopeSerializer
from config.middleware import get_request_id


def _actor(request: Request) -> User:
    if not isinstance(request.user, User):
        raise ApiProblem(
            code="authentication_required",
            message="Потрібна автентифікація.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return request.user


def _idempotency_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key", "").strip()
    if not value:
        raise ApiProblem(
            code="idempotency_key_required",
            message="Для фінансової mutation потрібен Idempotency-Key.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"idempotency_key": ["Створіть стабільний ключ для цього submit."]},
        )
    if len(value) > 128:
        raise ApiProblem(
            code="idempotency_key_invalid",
            message="Idempotency-Key перевищує дозволену довжину.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"idempotency_key": ["Максимальна довжина — 128 символів."]},
        )
    return value


IDEMPOTENCY_PARAMETER = OpenApiParameter(
    name="Idempotency-Key",
    type={"type": "string", "minLength": 1, "maxLength": 128},
    location=OpenApiParameter.HEADER,
    required=True,
    description="Stable per-submit key. The same normalized payload replays its result.",
)


class CashShiftOpenView(APIView):
    permission_classes = [HasCashShiftAccess]

    @extend_schema(
        operation_id="cash_shift_list",
        summary="List role-scoped cash-shift history with stable keyset paging",
        parameters=[CashShiftFilterSerializer],
        responses={
            status.HTTP_200_OK: CashShiftListResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def get(self, request: Request) -> Response:
        serializer = CashShiftFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        shifts, next_cursor = cash_shift_history_page(
            actor=_actor(request),
            filters=dict(serializer.validated_data),
        )
        return Response(
            CashShiftListResponseSerializer({"shifts": shifts, "next_cursor": next_cursor}).data
        )

    @extend_schema(
        operation_id="cash_shift_open",
        summary="Open one cash shift for the current employee",
        request=None,
        responses={
            status.HTTP_201_CREATED: CashShiftProjectionSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def post(self, request: Request) -> Response:
        actor = _actor(request)
        shift = open_cash_shift(
            actor=actor,
            correlation_id=get_request_id(request),
        )
        return Response(
            CashShiftProjectionSerializer(cash_shift_projection(shift, actor=actor)).data,
            status=status.HTTP_201_CREATED,
        )


class CurrentCashShiftView(APIView):
    permission_classes = [HasCashShiftAccess]

    @extend_schema(
        operation_id="cash_shift_current",
        summary="Return the current employee's open shift and ledger-derived totals",
        responses={
            status.HTTP_200_OK: CashShiftCurrentResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        shift = current_cash_shift(actor=actor)
        payload = {"shift": None if shift is None else cash_shift_projection(shift, actor=actor)}
        return Response(CashShiftCurrentResponseSerializer(payload).data)


class CashShiftDetailView(APIView):
    permission_classes = [HasCashShiftAccess]

    @extend_schema(
        operation_id="cash_shift_retrieve",
        summary="Return one role-scoped cash shift with its complete immutable ledger",
        responses={
            status.HTTP_200_OK: CashShiftProjectionSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def get(self, request: Request, shift_id: UUID) -> Response:
        actor = _actor(request)
        shift = cash_shift_detail(actor=actor, shift_id=shift_id)
        return Response(
            CashShiftProjectionSerializer(cash_shift_projection(shift, actor=actor)).data
        )


class CashShiftHistoryExportView(APIView):
    permission_classes = [HasCashShiftAccess]
    renderer_classes = [JSONRenderer, SafeCsvRenderer]

    @extend_schema(
        operation_id="cash_shift_history_export",
        summary="Export filtered role-scoped cash-shift summaries as safe CSV",
        parameters=[CashShiftHistoryExportFilterSerializer],
        responses={
            (status.HTTP_200_OK, "text/csv"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description=(
                    "UTF-8 BOM CSV with one report summary and at most 5000 cash-shift rows."
                ),
            ),
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def get(self, request: Request) -> HttpResponse:
        if "cursor" in request.query_params:
            raise ApiProblem(
                code="cash_shift_history_export_cursor_not_supported",
                message="Експорт історії завжди починається з повного набору за фільтрами.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={"cursor": ["Приберіть cursor з export-запиту."]},
            )
        serializer = CashShiftHistoryExportFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        rows = cash_shift_history_export_rows(
            actor=_actor(request),
            filters=dict(serializer.validated_data),
            row_limit=billing_exports.CASH_SHIFT_HISTORY_EXPORT_ROW_LIMIT,
        )
        if len(rows) > billing_exports.CASH_SHIFT_HISTORY_EXPORT_ROW_LIMIT:
            raise ApiProblem(
                code="cash_shift_history_export_too_large",
                message="Експорт історії містить забагато касових змін. Звузьте фільтри.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    "filters": [
                        "Максимум "
                        f"{billing_exports.CASH_SHIFT_HISTORY_EXPORT_ROW_LIMIT} змін "
                        "за один файл."
                    ]
                },
            )
        filename = timezone.localtime().strftime("cash-shift-history-%Y%m%d-%H%M%S.csv")
        response = HttpResponse(
            billing_exports.render_cash_shift_history_csv(rows),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        response["X-Export-Shift-Count"] = str(len(rows))
        response["X-Export-Row-Count"] = str(len(rows) + 1)
        return response


class CashShiftExportView(APIView):
    permission_classes = [HasCashShiftAccess]
    renderer_classes = [JSONRenderer, SafeCsvRenderer]

    @extend_schema(
        operation_id="cash_shift_export",
        summary="Export one role-scoped cash shift and its append-only ledger as safe CSV",
        responses={
            (status.HTTP_200_OK, "text/csv"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="UTF-8 BOM CSV with one summary row and at most 5000 ledger rows.",
            ),
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def get(self, request: Request, shift_id: UUID) -> HttpResponse:
        if request.query_params:
            raise ApiProblem(
                code="cash_shift_export_query_not_supported",
                message="Експорт однієї касової зміни не приймає фільтри або cursor.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    name: ["Приберіть query parameter з exact-shift export."]
                    for name in sorted(request.query_params)
                },
            )
        shift, entries = cash_shift_export_snapshot(
            actor=_actor(request),
            shift_id=shift_id,
            entry_limit=billing_exports.CASH_SHIFT_EXPORT_ENTRY_LIMIT,
        )
        if len(entries) > billing_exports.CASH_SHIFT_EXPORT_ENTRY_LIMIT:
            raise ApiProblem(
                code="cash_shift_export_too_large",
                message="У касовій зміні забагато операцій для синхронного CSV export.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    "entries": [
                        "Допустимо не більше "
                        f"{billing_exports.CASH_SHIFT_EXPORT_ENTRY_LIMIT} операцій."
                    ]
                },
            )
        content = billing_exports.render_cash_shift_csv(shift, entries)
        filename = (
            f"cash-shift-{shift.public_number}-"
            f"{timezone.localtime(timezone.now()).strftime('%Y%m%d-%H%M%S')}.csv"
        )
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        response["X-Export-Entry-Count"] = str(len(entries))
        response["X-Export-Row-Count"] = str(len(entries) + 1)
        return response


class CashShiftClosePreviewView(APIView):
    permission_classes = [HasCashShiftAccess]

    @extend_schema(
        operation_id="cash_shift_close_preview",
        summary="Preview authoritative cash reconciliation and unpaid warning",
        responses={
            status.HTTP_200_OK: CashShiftClosePreviewResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def get(self, request: Request, shift_id: UUID) -> Response:
        payload = cash_shift_close_preview(actor=_actor(request), shift_id=shift_id)
        return Response(CashShiftClosePreviewResponseSerializer(payload).data)


class CashShiftCloseView(APIView):
    permission_classes = [HasCashShiftAccess]

    @extend_schema(
        operation_id="cash_shift_close",
        summary="Close one owned cash shift, or any shift as admin, after reconciliation",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=CashShiftCloseSerializer,
        responses={
            status.HTTP_200_OK: CashShiftCloseResponseSerializer,
            status.HTTP_201_CREATED: CashShiftCloseResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["cash"],
    )
    def post(self, request: Request, shift_id: UUID) -> Response:
        serializer = CashShiftCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = _actor(request)
        shift, replayed = close_cash_shift(
            actor=actor,
            shift_id=shift_id,
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
        )
        payload = {
            "shift": cash_shift_projection(shift, actor=actor),
            "replayed": replayed,
        }
        return Response(
            CashShiftCloseResponseSerializer(payload).data,
            status=(status.HTTP_200_OK if replayed else status.HTTP_201_CREATED),
        )


class FinanceOperationListView(APIView):
    permission_classes = [HasFinanceAccess]

    @extend_schema(
        operation_id="finance_operation_list",
        summary="Search and keyset-page receivable lifecycle and posted finance operations",
        parameters=[FinanceOperationFilterSerializer],
        responses={
            status.HTTP_200_OK: FinanceOperationListResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["finance"],
    )
    def get(self, request: Request) -> Response:
        serializer = FinanceOperationFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        operations, next_cursor = finance_operations_page(
            actor=_actor(request),
            filters=dict(serializer.validated_data),
        )
        payload = {
            "operations": operations,
            "next_cursor": next_cursor,
        }
        return Response(FinanceOperationListResponseSerializer(payload).data)


class FinanceOperationExportView(APIView):
    permission_classes = [IsAdmin]
    renderer_classes = [JSONRenderer, SafeCsvRenderer]

    @extend_schema(
        operation_id="finance_operation_export",
        summary="Export filtered admin finance-operation journal as safe CSV",
        parameters=[FinanceOperationExportFilterSerializer],
        responses={
            (status.HTTP_200_OK, "text/csv"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description=(
                    "UTF-8 BOM CSV with one report summary and at most 5000 finance-operation rows."
                ),
            ),
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["finance"],
    )
    def get(self, request: Request) -> HttpResponse:
        supported_query = {
            "search",
            "type",
            "status",
            "payment_method",
            "date_from",
            "date_to",
        }
        unsupported = sorted(set(request.query_params) - supported_query)
        if unsupported:
            raise ApiProblem(
                code="finance_operation_export_query_not_supported",
                message="Експорт фінансових операцій приймає лише фільтри головного журналу.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    name: ["Приберіть unsupported query parameter з export-запиту."]
                    for name in unsupported
                },
            )
        serializer = FinanceOperationExportFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = dict(serializer.validated_data)
        operations = finance_operations_export_rows(
            actor=_actor(request),
            filters=filters,
            row_limit=billing_exports.FINANCE_OPERATION_EXPORT_ROW_LIMIT,
        )
        if len(operations) > billing_exports.FINANCE_OPERATION_EXPORT_ROW_LIMIT:
            raise ApiProblem(
                code="finance_operation_export_too_large",
                message="Експорт містить забагато фінансових операцій. Звузьте фільтри.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    "filters": [
                        "Максимум "
                        f"{billing_exports.FINANCE_OPERATION_EXPORT_ROW_LIMIT} "
                        "операцій за один файл."
                    ]
                },
            )
        filename = timezone.localtime().strftime("finance-operations-%Y%m%d-%H%M%S.csv")
        response = HttpResponse(
            billing_exports.render_finance_operations_csv(operations, filters),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        response["X-Export-Operation-Count"] = str(len(operations))
        response["X-Export-Row-Count"] = str(len(operations) + 1)
        return response


class FinanceOperationDetailView(APIView):
    permission_classes = [HasFinanceAccess]

    @extend_schema(
        operation_id="finance_operation_retrieve",
        summary="Resolve an exact role-scoped finance operation deep link",
        parameters=[
            OpenApiParameter(
                name="operation_type",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                enum=[CashLedgerEntryKind.PAYMENT],
            )
        ],
        responses={
            status.HTTP_200_OK: FinancePaymentOperationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["finance"],
    )
    def get(
        self,
        request: Request,
        operation_type: str,
        operation_id: UUID,
    ) -> Response:
        actor = _actor(request)
        if operation_type != CashLedgerEntryKind.PAYMENT:
            raise Http404
        receivable = get_object_or_404(
            payment_receivables_visible_to(actor),
            pk=operation_id,
        )
        return Response(
            FinancePaymentOperationSerializer(finance_payment_operation_read_model(receivable)).data
        )


class PaymentCreateView(APIView):
    permission_classes = [HasFinanceAccess]

    @extend_schema(
        operation_id="payment_create",
        summary="Post one server-derived full payment into the actor's open shift",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=PaymentCreateSerializer,
        responses={
            status.HTTP_200_OK: PaymentCreateResponseSerializer,
            status.HTTP_201_CREATED: PaymentCreateResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["finance"],
    )
    def post(self, request: Request) -> Response:
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = _actor(request)
        payment, replayed = post_payment(
            actor=actor,
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
        )
        payload = {
            "operation": payment_operation_by_receivable_id(payment.receivable_id),
            "replayed": replayed,
        }
        return Response(
            PaymentCreateResponseSerializer(payload).data,
            status=(status.HTTP_200_OK if replayed else status.HTTP_201_CREATED),
        )


class PaymentReceiptView(APIView):
    permission_classes = [HasFinanceAccess]
    renderer_classes = [JSONRenderer, SafePdfRenderer]

    @extend_schema(
        operation_id="payment_receipt_retrieve",
        summary="Download or print an A4 payment receipt and recommendation form",
        parameters=[
            OpenApiParameter(
                name="disposition",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=["attachment", "inline"],
                default="attachment",
                description="Use inline for the browser print flow.",
            )
        ],
        responses={
            (status.HTTP_200_OK, "application/pdf"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description=(
                    "Black-and-white A4 payment receipt and podologist recommendation form."
                ),
            ),
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["finance"],
    )
    def get(self, request: Request, payment_id: UUID) -> HttpResponse:
        disposition = request.query_params.get("disposition", "attachment")
        if disposition not in {"attachment", "inline"}:
            raise ApiProblem(
                code="invalid_receipt_disposition",
                message="Формат відкриття квитанції не підтримується.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={"disposition": ["Доступні значення: attachment або inline."]},
            )
        payment = get_object_or_404(
            payment_receipts_visible_to(_actor(request)),
            pk=payment_id,
        )
        content = render_payment_receipt_pdf(payment)
        filename = f"payment-receipt-{payment.ledger_entry.public_number}.pdf"
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class RefundCreateView(APIView):
    permission_classes = [HasFinanceAccess]

    @extend_schema(
        operation_id="refund_create",
        summary="Post one server-derived full refund into the actor's open shift",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=RefundCreateSerializer,
        responses={
            status.HTTP_200_OK: RefundCreateResponseSerializer,
            status.HTTP_201_CREATED: RefundCreateResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["finance"],
    )
    def post(self, request: Request, payment_id: UUID) -> Response:
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund, replayed = post_refund(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            payment_id=payment_id,
            data=dict(serializer.validated_data),
        )
        payload = {
            "operation": finance_refund_operation_read_model(refund),
            "replayed": replayed,
        }
        return Response(
            RefundCreateResponseSerializer(payload).data,
            status=(status.HTTP_200_OK if replayed else status.HTTP_201_CREATED),
        )


class CashMovementCreateView(APIView):
    permission_classes = [HasFinanceAccess]

    @extend_schema(
        operation_id="cash_movement_create",
        summary="Post a cash deposit or withdrawal into the actor's open shift",
        parameters=[IDEMPOTENCY_PARAMETER],
        request=CashMovementCreateSerializer,
        responses={
            status.HTTP_200_OK: CashMovementCreateResponseSerializer,
            status.HTTP_201_CREATED: CashMovementCreateResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["finance"],
    )
    def post(self, request: Request) -> Response:
        serializer = CashMovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjustment, replayed = post_cash_movement(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
        )
        payload = {
            "operation": finance_cash_adjustment_operation_read_model(adjustment),
            "replayed": replayed,
        }
        return Response(
            CashMovementCreateResponseSerializer(payload).data,
            status=(status.HTTP_200_OK if replayed else status.HTTP_201_CREATED),
        )
