from typing import cast

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasAnalyticsAccess
from apps.analytics import exports as analytics_exports
from apps.analytics.selectors import CLINIC_TIMEZONE, analytics_read_model, overview_read_model
from apps.analytics.serializers import (
    AnalyticsFilterSerializer,
    AnalyticsResponseSerializer,
    OverviewFilterSerializer,
    OverviewResponseSerializer,
)
from config.api.csv import SafeCsvRenderer
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer


def _actor(request: Request) -> User:
    return cast(User, request.user)


class OverviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="overview_retrieve",
        summary="Return a role-scoped operational overview for one local clinic date",
        parameters=[OverviewFilterSerializer],
        responses={
            status.HTTP_200_OK: OverviewResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["analytics"],
    )
    def get(self, request: Request) -> Response:
        filters = OverviewFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        local_date = filters.validated_data.get(
            "date", timezone.now().astimezone(CLINIC_TIMEZONE).date()
        )
        result = overview_read_model(actor=_actor(request), local_date=local_date)
        return Response(OverviewResponseSerializer(result).data)


class AnalyticsView(APIView):
    permission_classes = [IsAuthenticated, HasAnalyticsAccess]

    @extend_schema(
        operation_id="analytics_retrieve",
        summary="Return ledger- and visit-derived clinic analytics for an administrator",
        parameters=[
            OpenApiParameter("from", OpenApiTypes.DATE, required=True),
            OpenApiParameter("to", OpenApiTypes.DATE, required=True),
            OpenApiParameter("specialist_id", OpenApiTypes.INT, required=False),
            OpenApiParameter("service_id", OpenApiTypes.UUID, required=False),
        ],
        responses={
            status.HTTP_200_OK: AnalyticsResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["analytics"],
    )
    def get(self, request: Request) -> Response:
        filters = AnalyticsFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        result = analytics_read_model(
            date_from=query["from"],
            date_to=query["to"],
            specialist_id=query.get("specialist_id"),
            service_id=query.get("service_id"),
        )
        return Response(AnalyticsResponseSerializer(result).data)


class AnalyticsExportView(APIView):
    permission_classes = [IsAuthenticated, HasAnalyticsAccess]
    renderer_classes = [JSONRenderer, SafeCsvRenderer]

    @extend_schema(
        operation_id="analytics_export",
        summary="Export the current aggregate administrator analytics projection as safe CSV",
        parameters=[
            OpenApiParameter("from", OpenApiTypes.DATE, required=True),
            OpenApiParameter("to", OpenApiTypes.DATE, required=True),
            OpenApiParameter("specialist_id", OpenApiTypes.INT, required=False),
            OpenApiParameter("service_id", OpenApiTypes.UUID, required=False),
        ],
        responses={
            (status.HTTP_200_OK, "text/csv"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description=(
                    "UTF-8 BOM CSV with an aggregate summary and at most 5000 "
                    "trend/outcome/specialist/service rows."
                ),
            ),
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["analytics"],
    )
    def get(self, request: Request) -> HttpResponse:
        filters = AnalyticsFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        result = analytics_read_model(
            date_from=query["from"],
            date_to=query["to"],
            specialist_id=query.get("specialist_id"),
            service_id=query.get("service_id"),
        )
        row_count = analytics_exports.analytics_export_row_count(result)
        if row_count > analytics_exports.ANALYTICS_EXPORT_ROW_LIMIT:
            raise ApiProblem(
                code="analytics_export_too_large",
                message="Експорт аналітики містить забагато агрегованих рядків.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    "filters": [
                        "Допустимо не більше "
                        f"{analytics_exports.ANALYTICS_EXPORT_ROW_LIMIT} рядків за один файл."
                    ]
                },
            )
        filename = timezone.localtime().strftime("analytics-report-%Y%m%d-%H%M%S.csv")
        response = HttpResponse(
            analytics_exports.render_analytics_csv(result),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        response["X-Export-Row-Count"] = str(row_count)
        return response
