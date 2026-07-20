from uuid import UUID

from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin
from apps.clinic import storage
from apps.clinic.models import Room, Service
from apps.clinic.serializers import (
    ClinicLogoUploadSerializer,
    ClinicProfileSerializer,
    ClinicProfileUpdateSerializer,
    RoomCreateSerializer,
    RoomListSerializer,
    RoomSerializer,
    RoomUpdateSerializer,
    ServiceCreateSerializer,
    ServiceFilterSerializer,
    ServiceListSerializer,
    ServicePickerSerializer,
    ServiceSerializer,
    ServiceUpdateSerializer,
)
from apps.clinic.services import (
    create_room,
    create_service,
    get_clinic_profile,
    update_clinic_logo,
    update_clinic_profile,
    update_room,
    update_service,
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


def _is_admin(request: Request, view: APIView) -> bool:
    return IsAdmin().has_permission(request, view)


class ClinicProfileView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="clinic_profile_retrieve",
        summary="Return the singleton clinic profile",
        responses={
            status.HTTP_200_OK: ClinicProfileSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
        },
        tags=["clinic settings"],
    )
    def get(self, request: Request) -> Response:
        return Response(ClinicProfileSerializer(get_clinic_profile()).data)

    @extend_schema(
        operation_id="clinic_profile_update",
        summary="Update clinic contact and identity fields",
        request=ClinicProfileUpdateSerializer,
        responses={
            status.HTTP_200_OK: ClinicProfileSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["clinic settings"],
    )
    def patch(self, request: Request) -> Response:
        serializer = ClinicProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = update_clinic_profile(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            changes=dict(serializer.validated_data),
        )
        return Response(ClinicProfileSerializer(profile).data)


class ClinicLogoView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        operation_id="clinic_logo_retrieve",
        summary="Read the private clinic logo for an authenticated employee",
        responses={
            (status.HTTP_200_OK, "image/png"): bytes,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_503_SERVICE_UNAVAILABLE: ErrorEnvelopeSerializer,
        },
        tags=["clinic settings"],
    )
    def get(self, request: Request) -> HttpResponse:
        profile = get_clinic_profile()
        if not profile.logo_object_key:
            raise ApiProblem(
                code="clinic_logo_not_found",
                message="Логотип кабінету ще не завантажено.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        try:
            content = storage.get_private_object(object_key=profile.logo_object_key)
        except Exception as exc:
            raise ApiProblem(
                code="logo_storage_unavailable",
                message="Не вдалося отримати логотип. Спробуйте ще раз.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        response = HttpResponse(content, content_type=profile.logo_content_type)
        response["Cache-Control"] = "private, max-age=300"
        response["Content-Disposition"] = 'inline; filename="clinic-logo"'
        return response

    @extend_schema(
        operation_id="clinic_logo_update",
        summary="Validate and replace the private clinic logo",
        request=ClinicLogoUploadSerializer,
        responses={
            status.HTTP_200_OK: ClinicProfileSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
            status.HTTP_503_SERVICE_UNAVAILABLE: ErrorEnvelopeSerializer,
        },
        tags=["clinic settings"],
    )
    def put(self, request: Request) -> Response:
        if not IsAdmin().has_permission(request, self):
            self.permission_denied(request)
        serializer = ClinicLogoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = update_clinic_logo(
            actor=_actor(request),
            correlation_id=get_request_id(request),
            upload=serializer.validated_data["logo"],
            expected_version=serializer.validated_data["version"],
        )
        return Response(ClinicProfileSerializer(profile).data)


class RoomListCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="room_list",
        summary="List active and inactive rooms for the single clinic location",
        responses={
            status.HTTP_200_OK: RoomListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
        },
        tags=["clinic settings"],
    )
    def get(self, request: Request) -> Response:
        return Response({"rooms": RoomSerializer(Room.objects.all(), many=True).data})

    @extend_schema(
        operation_id="room_create",
        summary="Create a room for the single clinic location",
        request=RoomCreateSerializer,
        responses={
            status.HTTP_201_CREATED: RoomSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["clinic settings"],
    )
    def post(self, request: Request) -> Response:
        serializer = RoomCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            room = create_room(
                actor=_actor(request),
                correlation_id=get_request_id(request),
                data=serializer.validated_data,
            )
        except IntegrityError as exc:
            raise _room_name_conflict() from exc
        return Response(RoomSerializer(room).data, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id="room_update",
        summary="Rename, deactivate or reactivate a room without deleting history",
        request=RoomUpdateSerializer,
        responses={
            status.HTTP_200_OK: RoomSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["clinic settings"],
    )
    def patch(self, request: Request, room_id: UUID) -> Response:
        get_object_or_404(Room, pk=room_id)
        serializer = RoomUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            room = update_room(
                actor=_actor(request),
                room_id=room_id,
                correlation_id=get_request_id(request),
                changes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _room_name_conflict() from exc
        return Response(RoomSerializer(room).data)


def _room_name_conflict() -> ApiProblem:
    return ApiProblem(
        code="room_name_already_exists",
        message="Кімната з такою назвою вже існує.",
        status_code=status.HTTP_409_CONFLICT,
        fields={"name": ["Укажіть іншу назву кімнати."]},
    )


class ServiceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="service_list",
        summary="Search services; non-admin employees receive active picker records only",
        parameters=[ServiceFilterSerializer],
        responses={
            status.HTTP_200_OK: ServiceListSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["services"],
    )
    def get(self, request: Request) -> Response:
        filters = ServiceFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        services = Service.objects.all()
        if search := query.get("search", "").strip():
            services = services.filter(Q(code__icontains=search) | Q(name__icontains=search))
        if _is_admin(request, self):
            if query.get("status") == "active":
                services = services.filter(is_active=True)
            elif query.get("status") == "inactive":
                services = services.filter(is_active=False)
            serialized = ServiceSerializer(services, many=True).data
        else:
            services = services.filter(is_active=True)
            serialized = ServicePickerSerializer(services, many=True).data
        return Response({"services": serialized})

    @extend_schema(
        operation_id="service_create",
        summary="Create a service in the administrator catalog",
        request=ServiceCreateSerializer,
        responses={
            status.HTTP_201_CREATED: ServiceSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["services"],
    )
    def post(self, request: Request) -> Response:
        if not _is_admin(request, self):
            self.permission_denied(request)
        serializer = ServiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service = create_service(
                actor=_actor(request),
                correlation_id=get_request_id(request),
                data=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _service_code_conflict() from exc
        return Response(ServiceSerializer(service).data, status=status.HTTP_201_CREATED)


class ServiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="service_retrieve",
        summary="Return a service; non-admin employees can retrieve active picker records only",
        responses={
            status.HTTP_200_OK: ServiceSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["services"],
    )
    def get(self, request: Request, service_id: UUID) -> Response:
        if _is_admin(request, self):
            service = get_object_or_404(Service, pk=service_id)
            return Response(ServiceSerializer(service).data)
        service = get_object_or_404(Service, pk=service_id, is_active=True)
        return Response(ServicePickerSerializer(service).data)

    @extend_schema(
        operation_id="service_update",
        summary="Edit, deactivate or reactivate a service without deleting history",
        request=ServiceUpdateSerializer,
        responses={
            status.HTTP_200_OK: ServiceSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["services"],
    )
    def patch(self, request: Request, service_id: UUID) -> Response:
        if not _is_admin(request, self):
            self.permission_denied(request)
        target = get_object_or_404(Service, pk=service_id)
        serializer = ServiceUpdateSerializer(data=request.data, context={"target": target})
        serializer.is_valid(raise_exception=True)
        try:
            service = update_service(
                actor=_actor(request),
                service_id=service_id,
                correlation_id=get_request_id(request),
                changes=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _service_code_conflict() from exc
        return Response(ServiceSerializer(service).data)


def _service_code_conflict() -> ApiProblem:
    return ApiProblem(
        code="service_code_already_exists",
        message="Послуга з таким кодом уже існує.",
        status_code=status.HTTP_409_CONFLICT,
        fields={"code": ["Укажіть інший унікальний код послуги."]},
    )
