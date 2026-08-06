from uuid import UUID

from django.db import IntegrityError
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.accounts.permissions import IsAdmin
from apps.discounts.models import Discount, LoyaltyPolicy
from apps.discounts.serializers import (
    DiscountCreateSerializer,
    DiscountListSerializer,
    DiscountSerializer,
    DiscountUpdateSerializer,
    LoyaltyPolicySerializer,
    LoyaltyPolicyUpdateSerializer,
)
from apps.discounts.services import create_discount, update_discount, update_loyalty_policy
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


def _require_admin(request: Request, view: APIView) -> User:
    if not IsAdmin().has_permission(request, view):
        view.permission_denied(request)
    return _actor(request)


def _name_conflict() -> ApiProblem:
    return ApiProblem(
        code="discount_name_conflict",
        message="Знижка з такою назвою вже існує.",
        status_code=status.HTTP_409_CONFLICT,
        fields={"name": ["Назва має бути унікальною."]},
    )


class DiscountListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="discount_list",
        parameters=[
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=["active", "inactive", "all"],
                default="active",
                description=(
                    "Admins may filter the catalog; other roles always receive active discounts."
                ),
            )
        ],
        responses={
            status.HTTP_200_OK: DiscountListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
        },
        tags=["discounts"],
    )
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        requested_status = str(request.query_params.get("status", "active"))
        if requested_status not in {"active", "inactive", "all"}:
            raise ApiProblem(
                code="invalid_discount_status",
                message="Невідомий фільтр статусу знижки.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={"status": ["Використайте active, inactive або all."]},
            )
        discounts = Discount.objects.all()
        if actor.role != UserRole.ADMIN:
            discounts = discounts.filter(is_active=True)
        elif requested_status == "active":
            discounts = discounts.filter(is_active=True)
        elif requested_status == "inactive":
            discounts = discounts.filter(is_active=False)
        return Response({"discounts": DiscountSerializer(discounts, many=True).data})

    @extend_schema(
        operation_id="discount_create",
        request=DiscountCreateSerializer,
        responses={
            status.HTTP_201_CREATED: DiscountSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["discounts"],
    )
    def post(self, request: Request) -> Response:
        actor = _require_admin(request, self)
        serializer = DiscountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            discount = create_discount(
                actor=actor,
                correlation_id=get_request_id(request),
                data=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _name_conflict() from exc
        return Response(DiscountSerializer(discount).data, status=status.HTTP_201_CREATED)


class DiscountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="discount_retrieve",
        responses={
            status.HTTP_200_OK: DiscountSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["discounts"],
    )
    def get(self, request: Request, discount_id: UUID) -> Response:
        actor = _actor(request)
        discounts = Discount.objects.filter(pk=discount_id)
        if actor.role != UserRole.ADMIN:
            discounts = discounts.filter(is_active=True)
        discount = discounts.first()
        if discount is None:
            raise ApiProblem(
                code="not_found",
                message="Ресурс не знайдено.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(DiscountSerializer(discount).data)

    @extend_schema(
        operation_id="discount_update",
        request=DiscountUpdateSerializer,
        responses={
            status.HTTP_200_OK: DiscountSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["discounts"],
    )
    def patch(self, request: Request, discount_id: UUID) -> Response:
        actor = _require_admin(request, self)
        serializer = DiscountUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            discount = update_discount(
                actor=actor,
                discount_id=discount_id,
                correlation_id=get_request_id(request),
                changes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _name_conflict() from exc
        return Response(DiscountSerializer(discount).data)


class LoyaltyPolicyView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="loyalty_policy_retrieve",
        responses={
            status.HTTP_200_OK: LoyaltyPolicySerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
        },
        tags=["discounts"],
    )
    def get(self, request: Request) -> Response:
        return Response(LoyaltyPolicySerializer(LoyaltyPolicy.objects.get(key="default")).data)

    @extend_schema(
        operation_id="loyalty_policy_update",
        request=LoyaltyPolicyUpdateSerializer,
        responses={
            status.HTTP_200_OK: LoyaltyPolicySerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["discounts"],
    )
    def patch(self, request: Request) -> Response:
        serializer = LoyaltyPolicyUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        policy = update_loyalty_policy(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            changes=dict(serializer.validated_data),
        )
        return Response(LoyaltyPolicySerializer(policy).data)
