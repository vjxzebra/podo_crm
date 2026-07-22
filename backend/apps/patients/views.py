from urllib.parse import parse_qs, urlparse
from uuid import UUID

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework import status
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.accounts.permissions import HasPatientAccess
from apps.patients.models import Patient
from apps.patients.selectors import patients_visible_to, search_patients
from apps.patients.serializers import (
    MedicalPatientDetailSerializer,
    MedicalPatientUpdateSerializer,
    PatientCreateResponseSerializer,
    PatientCreateSerializer,
    PatientFilterSerializer,
    PatientListItemSerializer,
    PatientListResponseSerializer,
    PatientSerializer,
    ReceptionPatientDetailSerializer,
    ReceptionPatientUpdateSerializer,
)
from apps.patients.services import create_patient, update_patient
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer
from config.middleware import get_request_id


class PatientCursorPagination(CursorPagination):
    page_size = 20
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


class PatientListCreateView(APIView):
    permission_classes = [HasPatientAccess]

    @extend_schema(
        operation_id="patient_list",
        summary="Search the role-scoped patient directory with cursor pagination",
        parameters=[PatientFilterSerializer],
        responses={
            status.HTTP_200_OK: PatientListResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["patients"],
    )
    def get(self, request: Request) -> Response:
        filters = PatientFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        queryset = patients_visible_to(_actor(request))
        if search := filters.validated_data.get("search", ""):
            queryset = search_patients(queryset, search)
        paginator = PatientCursorPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return Response(
            {
                "patients": PatientListItemSerializer(page, many=True).data,
                "next_cursor": _next_cursor(paginator.get_next_link()),
            }
        )

    @extend_schema(
        operation_id="patient_create",
        summary="Create a patient and return role-safe possible phone duplicates",
        request=PatientCreateSerializer,
        responses={
            status.HTTP_201_CREATED: PatientCreateResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["patients"],
    )
    def post(self, request: Request) -> Response:
        serializer = PatientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = create_patient(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            data=dict(serializer.validated_data),
        )
        return Response(
            {
                "patient": PatientSerializer(result.patient).data,
                "duplicate_warning": bool(result.possible_duplicates),
                "possible_duplicates": PatientListItemSerializer(
                    result.possible_duplicates,
                    many=True,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


def _is_medical_role(user: User) -> bool:
    return user.role in {UserRole.ADMIN, UserRole.PODOLOGIST}


def _serialize_detail(patient: Patient, user: User) -> dict[str, object]:
    serializer_class = (
        MedicalPatientDetailSerializer
        if _is_medical_role(user)
        else ReceptionPatientDetailSerializer
    )
    return dict(serializer_class(patient, context={"actor": user}).data)


PATIENT_DETAIL_RESPONSE = PolymorphicProxySerializer(
    component_name="PatientDetailResponse",
    serializers=[ReceptionPatientDetailSerializer, MedicalPatientDetailSerializer],
    resource_type_field_name=None,
)

PATIENT_UPDATE_REQUEST = PolymorphicProxySerializer(
    component_name="PatientUpdateRequest",
    serializers=[ReceptionPatientUpdateSerializer, MedicalPatientUpdateSerializer],
    resource_type_field_name=None,
)


class PatientDetailView(APIView):
    permission_classes = [HasPatientAccess]

    @extend_schema(
        operation_id="patient_retrieve",
        summary="Retrieve a role-scoped patient card projection",
        responses={
            status.HTTP_200_OK: PATIENT_DETAIL_RESPONSE,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["patients"],
    )
    def get(self, request: Request, patient_id: UUID) -> Response:
        actor = _actor(request)
        patient = get_object_or_404(patients_visible_to(actor), pk=patient_id)
        return Response(_serialize_detail(patient, actor))

    @extend_schema(
        operation_id="patient_update",
        summary="Update a patient through the actor's safe role projection",
        request=PATIENT_UPDATE_REQUEST,
        responses={
            status.HTTP_200_OK: PATIENT_DETAIL_RESPONSE,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["patients"],
    )
    def patch(self, request: Request, patient_id: UUID) -> Response:
        actor = _actor(request)
        # Scope lookup comes before payload inspection to avoid foreign-ID disclosure.
        get_object_or_404(patients_visible_to(actor), pk=patient_id)
        if actor.role == UserRole.RECEPTION and "medical_profile" in request.data:
            raise ApiProblem(
                code="patient_medical_access_denied",
                message="Медичні дані недоступні для цієї ролі.",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        serializer_class = (
            MedicalPatientUpdateSerializer
            if _is_medical_role(actor)
            else ReceptionPatientUpdateSerializer
        )
        serializer = serializer_class(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        patient = update_patient(
            actor=actor,
            patient_id=patient_id,
            correlation_id=get_request_id(request),
            data=dict(serializer.validated_data),
        )
        return Response(_serialize_detail(patient, actor))
