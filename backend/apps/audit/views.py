from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAuditAccess
from apps.audit.models import AuditEvent
from apps.audit.serializers import (
    AuditEventDetailSerializer,
    AuditEventFilterSerializer,
    AuditEventListItemSerializer,
    AuditEventListResponseSerializer,
)
from config.api.serializers import ErrorEnvelopeSerializer

PAGE_SIZE = 50


def _filtered_events(request: Request) -> QuerySet[AuditEvent]:
    events = AuditEvent.objects.select_related("actor").all()
    filters = AuditEventFilterSerializer(data=request.query_params)
    filters.is_valid(raise_exception=True)
    query = filters.validated_data
    search = query.get("search", "").strip()
    if search:
        events = events.filter(
            Q(actor_display_name__icontains=search)
            | Q(actor_email__icontains=search)
            | Q(action__icontains=search)
            | Q(object_type__icontains=search)
            | Q(object_id__icontains=search)
            | Q(object_label__icontains=search)
            | Q(description__icontains=search)
        )
    if actor_id := query.get("actor_id"):
        events = events.filter(actor_id=actor_id)
    if section := query.get("section"):
        events = events.filter(section=section)
    if date_from := query.get("date_from"):
        events = events.filter(occurred_at__gte=date_from)
    if date_to := query.get("date_to"):
        events = events.filter(occurred_at__lte=date_to)
    if cursor := query.get("cursor"):
        cursor_event = get_object_or_404(AuditEvent, pk=cursor)
        events = events.filter(
            Q(occurred_at__lt=cursor_event.occurred_at)
            | Q(occurred_at=cursor_event.occurred_at, id__lt=cursor_event.id)
        )
    return events


class AuditEventListView(APIView):
    permission_classes = [HasAuditAccess]

    @extend_schema(
        operation_id="audit_event_list",
        summary="List append-only audit events for an administrator",
        parameters=[AuditEventFilterSerializer],
        responses={
            status.HTTP_200_OK: AuditEventListResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["audit"],
    )
    def get(self, request: Request) -> Response:
        page = list(_filtered_events(request)[: PAGE_SIZE + 1])
        has_next_page = len(page) > PAGE_SIZE
        page = page[:PAGE_SIZE]
        return Response(
            {
                "events": AuditEventListItemSerializer(page, many=True).data,
                "next_cursor": page[-1].id if has_next_page and page else None,
            }
        )


class AuditEventDetailView(APIView):
    permission_classes = [HasAuditAccess]

    @extend_schema(
        operation_id="audit_event_retrieve",
        summary="Return redacted before/after details for one audit event",
        responses={
            status.HTTP_200_OK: AuditEventDetailSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["audit"],
    )
    def get(self, request: Request, event_id: str) -> Response:
        event = get_object_or_404(AuditEvent.objects.select_related("actor"), pk=event_id)
        return Response(AuditEventDetailSerializer(event).data)
