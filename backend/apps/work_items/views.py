from uuid import UUID

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.accounts.permissions import HasWorkItemAccess
from apps.work_items.selectors import active_work_item_assignees, work_items_visible_to
from apps.work_items.serializers import (
    WorkItemAssigneeSerializer,
    WorkItemCreateSerializer,
    WorkItemFilterSerializer,
    WorkItemListResponseSerializer,
    WorkItemSerializer,
    WorkItemUpdateSerializer,
)
from apps.work_items.services import create_work_item, update_work_item
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


class WorkItemListCreateView(APIView):
    permission_classes = [HasWorkItemAccess]

    @extend_schema(
        operation_id="work_item_list",
        summary="List role-scoped internal work items",
        parameters=[WorkItemFilterSerializer],
        responses={
            status.HTTP_200_OK: WorkItemListResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["work-items"],
    )
    def get(self, request: Request) -> Response:
        actor = _actor(request)
        filters = WorkItemFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        requested_scope = filters.validated_data["scope"]
        effective_scope = (
            "own" if actor.role == UserRole.PODOLOGIST or requested_scope == "own" else "all"
        )
        scoped = work_items_visible_to(actor)
        if effective_scope == "own":
            scoped = scoped.filter(assignee=actor)
        summary = scoped.aggregate(
            open=Count("id", filter=Q(is_completed=False)),
            completed=Count("id", filter=Q(is_completed=True)),
            overdue=Count(
                "id",
                filter=Q(is_completed=False, due_at__lt=timezone.now()),
            ),
            important=Count("id", filter=Q(is_completed=False, is_important=True)),
        )
        status_filter = filters.validated_data["status"]
        if status_filter != "all":
            scoped = scoped.filter(is_completed=status_filter == "completed")
        if search := filters.validated_data.get("search", "").strip():
            scoped = scoped.filter(
                Q(title__icontains=search)
                | Q(comment__icontains=search)
                | Q(patient__first_name__icontains=search)
                | Q(patient__last_name__icontains=search)
                | Q(patient__phone__icontains=search)
            )
        return Response(
            {
                "work_items": WorkItemSerializer(scoped, many=True).data,
                "summary": summary,
                "assignees": WorkItemAssigneeSerializer(
                    active_work_item_assignees(),
                    many=True,
                ).data,
                "effective_scope": effective_scope,
            }
        )

    @extend_schema(
        operation_id="work_item_create",
        summary="Create an internal work item",
        request=WorkItemCreateSerializer,
        responses={
            status.HTTP_201_CREATED: WorkItemSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["work-items"],
    )
    def post(self, request: Request) -> Response:
        serializer = WorkItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = create_work_item(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            data=dict(serializer.validated_data),
        )
        return Response(WorkItemSerializer(item).data, status=status.HTTP_201_CREATED)


class WorkItemDetailView(APIView):
    permission_classes = [HasWorkItemAccess]

    @extend_schema(
        operation_id="work_item_update",
        summary="Edit, complete, or reopen a role-scoped internal work item",
        request=WorkItemUpdateSerializer,
        responses={
            status.HTTP_200_OK: WorkItemSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["work-items"],
    )
    def patch(self, request: Request, work_item_id: UUID) -> Response:
        serializer = WorkItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = update_work_item(
            actor=_actor(request),
            work_item_id=work_item_id,
            correlation_id=get_request_id(request),
            data=dict(serializer.validated_data),
        )
        return Response(WorkItemSerializer(item).data)
