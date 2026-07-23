from urllib.parse import parse_qs, urlparse
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.patients.history import (
    completed_visits_for_patient,
    photo_archive_visit_row,
    recommendation_row,
    recommendation_visit_option,
    visit_history_row,
)
from apps.patients.history_serializers import (
    PatientArchiveCursorQuerySerializer,
    PatientHistoryMedicalResponseSerializer,
    PatientHistorySafeResponseSerializer,
    PatientPhotoArchiveResponseSerializer,
    PatientRecommendationResponseSerializer,
)
from apps.patients.models import Patient
from apps.patients.selectors import patients_visible_to
from apps.visits.models import VisitRecommendation, VisitStatus
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer


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


def _validate_archive_query(request: Request) -> None:
    serializer = PatientArchiveCursorQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)


def _patient_for_actor(*, actor: User, patient_id: UUID) -> Patient:
    return get_object_or_404(patients_visible_to(actor), pk=patient_id)


def _require_medical(actor: User) -> None:
    if actor.role not in {UserRole.ADMIN, UserRole.PODOLOGIST}:
        raise ApiProblem(
            code="patient_medical_access_denied",
            message="Медичні дані недоступні для цієї ролі.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class PatientVisitCursorPagination(CursorPagination):
    page_size = 20
    cursor_query_param = "cursor"
    ordering = ("-completed_at", "-id")


class PatientPhotoVisitCursorPagination(CursorPagination):
    page_size = 10
    cursor_query_param = "cursor"
    ordering = ("-completed_at", "-id")


class PatientRecommendationCursorPagination(CursorPagination):
    page_size = 20
    cursor_query_param = "cursor"
    ordering = ("-created_at", "-id")


PATIENT_HISTORY_RESPONSE = PolymorphicProxySerializer(
    component_name="PatientHistoryResponse",
    serializers=[
        PatientHistorySafeResponseSerializer,
        PatientHistoryMedicalResponseSerializer,
    ],
    resource_type_field_name=None,
)


class PatientVisitHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="patient_visit_history",
        summary="List completed visits through a role-safe patient projection",
        parameters=[PatientArchiveCursorQuerySerializer],
        responses={
            status.HTTP_200_OK: PATIENT_HISTORY_RESPONSE,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["patients"],
    )
    def get(self, request: Request, patient_id: UUID) -> Response:
        _validate_archive_query(request)
        actor = _actor(request)
        patient = _patient_for_actor(actor=actor, patient_id=patient_id)
        medical = actor.role in {UserRole.ADMIN, UserRole.PODOLOGIST}
        queryset = completed_visits_for_patient(patient, medical=medical, actor=actor)
        paginator = PatientVisitCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is None:
            page = list(queryset)
        rows = [visit_history_row(visit, medical=medical) for visit in page]
        response = {"visits": rows, "next_cursor": _next_cursor(paginator.get_next_link())}
        serializer_class = (
            PatientHistoryMedicalResponseSerializer
            if medical
            else PatientHistorySafeResponseSerializer
        )
        return Response(serializer_class(response).data)


class PatientPhotoArchiveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="patient_photo_archive",
        summary="List completed visit photos after medical object-scope authorization",
        parameters=[PatientArchiveCursorQuerySerializer],
        responses={
            status.HTTP_200_OK: PatientPhotoArchiveResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["patients"],
    )
    def get(self, request: Request, patient_id: UUID) -> Response:
        _validate_archive_query(request)
        actor = _actor(request)
        patient = _patient_for_actor(actor=actor, patient_id=patient_id)
        _require_medical(actor)
        queryset = (
            completed_visits_for_patient(patient, medical=True, actor=actor)
            .filter(photos__isnull=False)
            .distinct()
        )
        paginator = PatientPhotoVisitCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        if page is None:
            page = list(queryset)
        response = {
            "visits": [photo_archive_visit_row(visit) for visit in page],
            "next_cursor": _next_cursor(paginator.get_next_link()),
        }
        return Response(PatientPhotoArchiveResponseSerializer(response).data)


def _recommendations_for_patient(
    patient: Patient,
    *,
    actor: User,
) -> QuerySet[VisitRecommendation]:
    queryset = (
        VisitRecommendation.objects.filter(
            visit__patient=patient,
            visit__status=VisitStatus.COMPLETED,
        )
        .filter(visit__completed_at__isnull=False, visit__total_minor__isnull=False)
        .select_related("visit", "visit__appointment", "visit__specialist", "author")
        .prefetch_related("visit__service_lines")
        .order_by("-created_at", "-id")
    )
    if actor.role == UserRole.PODOLOGIST:
        return queryset.filter(visit__specialist=actor)
    return queryset


class PatientRecommendationListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="patient_recommendation_list",
        summary="List patient recommendations with eligible completed visits",
        parameters=[PatientArchiveCursorQuerySerializer],
        responses={
            status.HTTP_200_OK: PatientRecommendationResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["patients"],
    )
    def get(self, request: Request, patient_id: UUID) -> Response:
        _validate_archive_query(request)
        actor = _actor(request)
        patient = _patient_for_actor(actor=actor, patient_id=patient_id)
        _require_medical(actor)
        recommendations = _recommendations_for_patient(patient, actor=actor)
        paginator = PatientRecommendationCursorPagination()
        page = paginator.paginate_queryset(recommendations, request, view=self)
        if page is None:
            page = list(recommendations)
        eligible_visits = completed_visits_for_patient(
            patient,
            medical=False,
            actor=actor,
        )
        response = {
            "recommendations": [recommendation_row(item, actor=actor) for item in page],
            "eligible_visits": [
                recommendation_visit_option(visit) for visit in eligible_visits[:50]
            ],
            "next_cursor": _next_cursor(paginator.get_next_link()),
        }
        return Response(PatientRecommendationResponseSerializer(response).data)
