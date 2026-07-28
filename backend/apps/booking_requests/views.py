from urllib.parse import parse_qs, urlparse
from uuid import UUID

from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasBookingRequestAccess, IsAdmin
from apps.booking_requests.authentication import (
    BookingRequestBearerAuthentication,
    BookingRequestCredentialAuth,
)
from apps.booking_requests.integration_services import (
    create_external_booking_request,
    rotate_booking_request_api_token,
)
from apps.booking_requests.models import BookingRequestApiCredential, BookingRequestStatus
from apps.booking_requests.selectors import booking_requests_visible_to
from apps.booking_requests.serializers import (
    BookingRequestApiCredentialRotatedSerializer,
    BookingRequestApiCredentialRotateSerializer,
    BookingRequestApiCredentialSerializer,
    BookingRequestFilterSerializer,
    BookingRequestListResponseSerializer,
    BookingRequestProcessSerializer,
    BookingRequestSerializer,
    ExternalBookingRequestResponseSerializer,
    ExternalBookingRequestSerializer,
)
from apps.booking_requests.services import process_booking_request
from apps.patients.normalization import phone_digits
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer
from config.middleware import get_request_id


class BookingRequestCursorPagination(CursorPagination):
    page_size = 30
    cursor_query_param = "cursor"
    ordering = ("-created_at", "-id")


def _actor(request: Request) -> User:
    if not isinstance(request.user, User):
        raise ApiProblem(
            code="authentication_required",
            message="Потрібна автентифікація.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return request.user


def _next_cursor(next_link: str | None) -> str | None:
    if next_link is None:
        return None
    values = parse_qs(urlparse(next_link).query).get("cursor")
    return values[0] if values else None


class BookingRequestListView(APIView):
    permission_classes = [HasBookingRequestAccess]

    @extend_schema(
        operation_id="booking_request_list",
        summary="List booking requests visible to admin and reception",
        parameters=[BookingRequestFilterSerializer],
        responses={
            status.HTTP_200_OK: BookingRequestListResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["booking-requests"],
    )
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        filters = BookingRequestFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        scoped = booking_requests_visible_to(actor)
        counts = scoped.aggregate(
            new=Count("id", filter=Q(status=BookingRequestStatus.NEW)),
            processed=Count("id", filter=Q(status=BookingRequestStatus.PROCESSED)),
            total=Count("id"),
        )

        if filters.validated_data["status"] != "ALL":
            scoped = scoped.filter(status=filters.validated_data["status"])
        if filters.validated_data["source"] != "ALL":
            scoped = scoped.filter(source=filters.validated_data["source"])
        if search := filters.validated_data.get("search", "").strip():
            search_digits = phone_digits(search)
            search_query = (
                Q(public_number__icontains=search)
                | Q(client_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(service__icontains=search)
                | Q(contact_handle__icontains=search)
            )
            if search_digits:
                search_query |= Q(phone_normalized__icontains=search_digits)
            scoped = scoped.filter(search_query)

        paginator = BookingRequestCursorPagination()
        page = paginator.paginate_queryset(scoped, request, view=self)
        payload = {
            "booking_requests": BookingRequestSerializer(page, many=True).data,
            "counts": counts,
            "next_cursor": _next_cursor(paginator.get_next_link()),
        }
        return Response(BookingRequestListResponseSerializer(payload).data)


class BookingRequestDetailView(APIView):
    permission_classes = [HasBookingRequestAccess]

    @extend_schema(
        operation_id="booking_request_retrieve",
        summary="Retrieve one booking request",
        responses={
            status.HTTP_200_OK: BookingRequestSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["booking-requests"],
    )
    def get(self, request: Request, booking_request_id: UUID) -> Response:
        item = booking_requests_visible_to(_actor(request)).filter(pk=booking_request_id).first()
        if item is None:
            raise ApiProblem(
                code="not_found",
                message="Ресурс не знайдено.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(BookingRequestSerializer(item).data)


class BookingRequestProcessView(APIView):
    permission_classes = [HasBookingRequestAccess]

    @extend_schema(
        operation_id="booking_request_process",
        summary="Idempotently mark one booking request as processed",
        request=BookingRequestProcessSerializer,
        responses={
            status.HTTP_200_OK: BookingRequestSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["booking-requests"],
    )
    def post(self, request: Request, booking_request_id: UUID) -> Response:
        serializer = BookingRequestProcessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = process_booking_request(
            actor=_actor(request),
            booking_request_id=booking_request_id,
            requested_version=serializer.validated_data["version"],
            correlation_id=get_request_id(request),
        )
        return Response(BookingRequestSerializer(item).data)


class BookingRequestApiCredentialView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="booking_request_integration_retrieve",
        summary="Return safe booking-request API credential metadata",
        responses={
            status.HTTP_200_OK: BookingRequestApiCredentialSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
        },
        tags=["booking-request-integration"],
    )
    def get(self, request: Request) -> Response:
        _actor(request)
        credential, _ = BookingRequestApiCredential.objects.get_or_create(
            pk=BookingRequestApiCredential.SINGLETON_ID
        )
        return Response(
            BookingRequestApiCredentialSerializer(credential).data,
            headers={"Cache-Control": "no-store"},
        )


class BookingRequestApiCredentialRotateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="booking_request_integration_token_rotate",
        summary="Generate or rotate the booking-request API token",
        request=BookingRequestApiCredentialRotateSerializer,
        responses={
            status.HTTP_200_OK: BookingRequestApiCredentialRotatedSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["booking-request-integration"],
    )
    def post(self, request: Request) -> Response:
        serializer = BookingRequestApiCredentialRotateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential, token = rotate_booking_request_api_token(
            actor=_actor(request),
            requested_version=serializer.validated_data["version"],
            correlation_id=get_request_id(request),
        )
        payload = {
            **BookingRequestApiCredentialSerializer(credential).data,
            "token": token,
        }
        return Response(payload, headers={"Cache-Control": "no-store"})


def _external_credential_auth(request: Request) -> BookingRequestCredentialAuth:
    if not isinstance(request.auth, BookingRequestCredentialAuth):
        raise ApiProblem(
            code="invalid_bearer_token",
            message="Bearer token відсутній або недійсний.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return request.auth


def _idempotency_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key", "").strip()
    if not value:
        raise ApiProblem(
            code="idempotency_key_required",
            message="Для створення заявки потрібен Idempotency-Key.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"idempotency_key": ["Додайте стабільний Idempotency-Key."]},
        )
    if len(value) > 128:
        raise ApiProblem(
            code="validation_error",
            message="Дані запиту не пройшли перевірку.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"idempotency_key": ["Idempotency-Key може містити до 128 символів."]},
        )
    return value


class ExternalBookingRequestCreateView(APIView):
    authentication_classes = [BookingRequestBearerAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="external_booking_request_create",
        summary="Create a booking request from a server-side integration",
        request=ExternalBookingRequestSerializer,
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="Stable unique value for one logical form submission.",
            ),
        ],
        responses={
            status.HTTP_201_CREATED: ExternalBookingRequestResponseSerializer,
            status.HTTP_200_OK: ExternalBookingRequestResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                response=ErrorEnvelopeSerializer,
                description="Rate limit exceeded; Retry-After is included.",
            ),
            status.HTTP_503_SERVICE_UNAVAILABLE: ErrorEnvelopeSerializer,
        },
        tags=["booking-request-integration"],
    )
    def post(self, request: Request) -> Response:
        serializer = ExternalBookingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item, replayed = create_external_booking_request(
            data=dict(serializer.validated_data),
            idempotency_key=_idempotency_key(request),
            auth=_external_credential_auth(request),
            correlation_id=get_request_id(request),
        )
        headers = {"Cache-Control": "no-store"}
        if replayed:
            headers["Idempotent-Replayed"] = "true"
        return Response(
            ExternalBookingRequestResponseSerializer(item).data,
            status=status.HTTP_200_OK if replayed else status.HTTP_201_CREATED,
            headers=headers,
        )
