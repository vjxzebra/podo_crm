from urllib.parse import parse_qs, urlparse
from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.notifications.selectors import notification_counts, notifications_visible_to
from apps.notifications.serializers import (
    NotificationFilterSerializer,
    NotificationListResponseSerializer,
    NotificationMarkAllResponseSerializer,
    NotificationSerializer,
)
from apps.notifications.services import mark_all_notifications_read, mark_notification_read
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer


class NotificationCursorPagination(CursorPagination):
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


def _ensure_empty_body(request: Request) -> None:
    if request.data != {}:
        raise ApiProblem(
            code="validation_error",
            message="Перевірте передані дані.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"non_field_errors": ["Тіло запиту має бути порожнім."]},
        )


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="notification_list",
        summary="List recipient-owned internal notifications",
        parameters=[NotificationFilterSerializer],
        responses={
            status.HTTP_200_OK: NotificationListResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["notifications"],
    )
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        filters = NotificationFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = notifications_visible_to(actor)
        if filters.validated_data["status"] == "unread":
            queryset = queryset.filter(read_at__isnull=True)
        paginator = NotificationCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        payload = {
            "notifications": NotificationSerializer(page, many=True).data,
            **notification_counts(actor),
            "next_cursor": _next_cursor(paginator.get_next_link()),
        }
        return Response(NotificationListResponseSerializer(payload).data)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="notification_read",
        summary="Idempotently mark one recipient-owned notification as read",
        request=None,
        responses={
            status.HTTP_200_OK: NotificationSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["notifications"],
    )
    def post(self, request: Request, notification_id: UUID) -> Response:
        _ensure_empty_body(request)
        notification = mark_notification_read(
            actor=_actor(request),
            notification_id=notification_id,
        )
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="notification_read_all",
        summary="Idempotently mark all current recipient notifications as read",
        request=None,
        responses={
            status.HTTP_200_OK: NotificationMarkAllResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["notifications"],
    )
    def post(self, request: Request) -> Response:
        _ensure_empty_body(request)
        marked_count = mark_all_notifications_read(actor=_actor(request))
        return Response({"marked_count": marked_count, "unread_count": 0})
