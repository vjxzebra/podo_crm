from collections.abc import Mapping
from typing import Any

from django.db.models import Q, QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAuditAccess
from apps.audit import exports as audit_exports
from apps.audit.models import AuditEvent
from apps.audit.serializers import (
    AuditEventDetailSerializer,
    AuditEventExportFilterSerializer,
    AuditEventFilterSerializer,
    AuditEventListItemSerializer,
    AuditEventListResponseSerializer,
)
from config.api.csv import SafeCsvRenderer
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer

PAGE_SIZE = 50


def _events_for_filters(query: Mapping[str, Any]) -> QuerySet[AuditEvent]:
    events = AuditEvent.objects.select_related("actor").all()
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
    return events


def _filtered_events(request: Request) -> QuerySet[AuditEvent]:
    filters = AuditEventFilterSerializer(data=request.query_params)
    filters.is_valid(raise_exception=True)
    query = filters.validated_data
    events = _events_for_filters(query)
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


class AuditEventExportView(APIView):
    permission_classes = [HasAuditAccess]
    renderer_classes = [JSONRenderer, SafeCsvRenderer]

    @extend_schema(
        operation_id="audit_event_export",
        summary="Export the filtered administrator audit journal as safe CSV",
        parameters=[AuditEventExportFilterSerializer],
        responses={
            (status.HTTP_200_OK, "text/csv"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description=(
                    "UTF-8 BOM CSV with one report summary and at most 5000 "
                    "minimal audit-event rows."
                ),
            ),
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["audit"],
    )
    def get(self, request: Request) -> HttpResponse:
        supported_query = {"search", "actor_id", "section", "date_from", "date_to"}
        unsupported = sorted(set(request.query_params) - supported_query)
        if unsupported:
            raise ApiProblem(
                code="audit_export_query_not_supported",
                message="Експорт журналу приймає лише фільтри головного списку.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    name: ["Приберіть unsupported query parameter з export-запиту."]
                    for name in unsupported
                },
            )
        serializer = AuditEventExportFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = dict(serializer.validated_data)
        events = list(_events_for_filters(filters)[: audit_exports.AUDIT_EXPORT_ROW_LIMIT + 1])
        if len(events) > audit_exports.AUDIT_EXPORT_ROW_LIMIT:
            raise ApiProblem(
                code="audit_export_too_large",
                message="Експорт містить забагато подій. Звузьте фільтри.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    "filters": [
                        f"Максимум {audit_exports.AUDIT_EXPORT_ROW_LIMIT} подій за один файл."
                    ]
                },
            )
        filename = timezone.localtime().strftime("audit-events-%Y%m%d-%H%M%S.csv")
        response = HttpResponse(
            audit_exports.render_audit_csv(events, filters),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        response["X-Export-Event-Count"] = str(len(events))
        response["X-Export-Row-Count"] = str(len(events) + 1)
        return response


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
