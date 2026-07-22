from uuid import UUID

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasCashShiftAccess, HasFinanceAccess
from apps.billing.models import CashLedgerEntryKind
from apps.billing.selectors import payment_receivables_visible_to
from apps.billing.serializers import (
    CashMovementCreateResponseSerializer,
    CashMovementCreateSerializer,
    CashShiftClosePreviewResponseSerializer,
    CashShiftCloseResponseSerializer,
    CashShiftCloseSerializer,
    CashShiftCurrentResponseSerializer,
    CashShiftFilterSerializer,
    CashShiftListResponseSerializer,
    CashShiftProjectionSerializer,
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
    cash_shift_history_page,
    cash_shift_projection,
    close_cash_shift,
    current_cash_shift,
    finance_cash_adjustment_operation_read_model,
    finance_operations_page,
    finance_payment_operation_read_model,
    finance_refund_operation_read_model,
    open_cash_shift,
    payment_operation_by_receivable_id,
    post_cash_movement,
    post_payment,
    post_refund,
)
from config.api.exceptions import ApiProblem
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
        shift = open_cash_shift(
            actor=_actor(request),
            correlation_id=get_request_id(request),
        )
        return Response(
            CashShiftProjectionSerializer(cash_shift_projection(shift)).data,
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
        shift = current_cash_shift(actor=_actor(request))
        payload = {"shift": None if shift is None else cash_shift_projection(shift)}
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
        shift = cash_shift_detail(actor=_actor(request), shift_id=shift_id)
        return Response(CashShiftProjectionSerializer(cash_shift_projection(shift)).data)


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
        shift, replayed = close_cash_shift(
            actor=_actor(request),
            shift_id=shift_id,
            correlation_id=get_request_id(request),
            idempotency_key=_idempotency_key(request),
            data=dict(serializer.validated_data),
        )
        payload = {
            "shift": cash_shift_projection(shift),
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
