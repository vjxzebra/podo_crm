from uuid import UUID

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.clinic.models import Room, Service
from apps.scheduling.selectors import (
    appointment_availability,
    appointments_visible_to,
    calendar_read_model,
)
from apps.scheduling.serializers import (
    AppointmentCancelSerializer,
    AppointmentCreateSerializer,
    AppointmentDetailResponseSerializer,
    AppointmentResponseSerializer,
    AppointmentStatusTransitionSerializer,
    AppointmentUpdateSerializer,
    AvailabilityFilterSerializer,
    AvailabilityResponseSerializer,
    CalendarFilterSerializer,
    CalendarResponseSerializer,
)
from apps.scheduling.services import (
    appointment_detail_read_model,
    appointment_read_model,
    cancel_appointment,
    create_appointment,
    transition_appointment_status,
    update_appointment,
)
from config.api.exceptions import ApiProblem
from config.api.serializers import ErrorEnvelopeSerializer
from config.middleware import get_request_id

APPOINTMENT_UPDATE_REQUEST_SCHEMA = {
    "type": "object",
    "required": ["version"],
    "minProperties": 2,
    "properties": {
        "version": {"type": "integer", "minimum": 1},
        "specialist_id": {"type": "integer", "minimum": 1},
        "service_id": {"type": "string", "format": "uuid"},
        "room_id": {"type": "string", "format": "uuid"},
        "starts_at": {"type": "string", "format": "date-time"},
        "complaints": {"type": "string", "maxLength": 4000},
        "has_no_complaints": {"type": "boolean"},
        "comment": {"type": "string", "maxLength": 4000},
    },
}


def _actor(request: Request) -> User:
    if not isinstance(request.user, User):
        raise ApiProblem(
            code="authentication_required",
            message="Потрібна автентифікація.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return request.user


class CalendarView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="calendar_retrieve",
        summary="Return a role-scoped day or week calendar read model",
        parameters=[CalendarFilterSerializer],
        responses={
            status.HTTP_200_OK: CalendarResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["scheduling"],
    )
    def get(self, request: Request) -> Response:
        filters = CalendarFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        result = calendar_read_model(
            actor=_actor(request),
            range_start=query["from"],
            range_end=query["to"],
            specialist_id=query.get("specialist_id"),
        )
        return Response(CalendarResponseSerializer(result).data)


class AppointmentAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="appointment_availability_retrieve",
        summary="Return free slots inside clinic hours without specialist or room conflicts",
        parameters=[AvailabilityFilterSerializer],
        responses={
            status.HTTP_200_OK: AvailabilityResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["scheduling"],
    )
    def get(self, request: Request) -> Response:
        filters = AvailabilityFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        query = filters.validated_data
        specialist = get_object_or_404(
            User,
            pk=query["specialist_id"],
            role=UserRole.PODOLOGIST,
            is_active=True,
        )
        service = get_object_or_404(Service, pk=query["service_id"], is_active=True)
        room = None
        if room_id := query.get("room_id"):
            room = get_object_or_404(Room, pk=room_id, is_active=True)
        result = appointment_availability(
            actor=_actor(request),
            local_date=query["date"],
            specialist=specialist,
            service=service,
            requested_room=room,
        )
        return Response(AvailabilityResponseSerializer(result).data)


class AppointmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="appointment_create",
        summary="Create an appointment inside clinic hours with role and occupancy protection",
        request=AppointmentCreateSerializer,
        responses={
            status.HTTP_201_CREATED: AppointmentResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["scheduling"],
    )
    def post(self, request: Request) -> Response:
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = create_appointment(
                actor=_actor(request),
                correlation_id=get_request_id(request),
                data=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _appointment_slot_conflict(exc) from exc
        return Response(
            AppointmentResponseSerializer(appointment_read_model(appointment)).data,
            status=status.HTTP_201_CREATED,
        )


class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="appointment_retrieve",
        summary="Return role-scoped appointment details and allowed actions",
        responses={
            status.HTTP_200_OK: AppointmentDetailResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
        },
        tags=["scheduling"],
    )
    def get(self, request: Request, appointment_id: UUID) -> Response:
        actor = _actor(request)
        appointment = get_object_or_404(appointments_visible_to(actor), pk=appointment_id)
        return Response(
            AppointmentDetailResponseSerializer(
                appointment_detail_read_model(actor=actor, appointment=appointment)
            ).data
        )

    @extend_schema(
        operation_id="appointment_update",
        summary="Edit or reschedule a role-scoped appointment with optimistic concurrency",
        request={"application/json": APPOINTMENT_UPDATE_REQUEST_SCHEMA},
        responses={
            status.HTTP_200_OK: AppointmentDetailResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["scheduling"],
    )
    def patch(self, request: Request, appointment_id: UUID) -> Response:
        actor = _actor(request)
        serializer = AppointmentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            appointment = update_appointment(
                actor=actor,
                appointment_id=appointment_id,
                correlation_id=get_request_id(request),
                data=dict(serializer.validated_data),
            )
        except IntegrityError as exc:
            raise _appointment_slot_conflict(exc) from exc
        return Response(
            AppointmentDetailResponseSerializer(
                appointment_detail_read_model(actor=actor, appointment=appointment)
            ).data
        )


class AppointmentStatusTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="appointment_status_transition",
        summary="Apply an allowed manual appointment status transition",
        request=AppointmentStatusTransitionSerializer,
        responses={
            status.HTTP_200_OK: AppointmentDetailResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["scheduling"],
    )
    def post(self, request: Request, appointment_id: UUID) -> Response:
        actor = _actor(request)
        serializer = AppointmentStatusTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = transition_appointment_status(
            actor=actor,
            appointment_id=appointment_id,
            correlation_id=get_request_id(request),
            requested_version=serializer.validated_data["version"],
            status_code=serializer.validated_data["status_code"],
        )
        return Response(
            AppointmentDetailResponseSerializer(
                appointment_detail_read_model(actor=actor, appointment=appointment)
            ).data
        )


class AppointmentCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="appointment_cancel",
        summary="Cancel an eligible appointment with a required reason",
        request=AppointmentCancelSerializer,
        responses={
            status.HTTP_200_OK: AppointmentDetailResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: ErrorEnvelopeSerializer,
            status.HTTP_403_FORBIDDEN: ErrorEnvelopeSerializer,
            status.HTTP_404_NOT_FOUND: ErrorEnvelopeSerializer,
            status.HTTP_409_CONFLICT: ErrorEnvelopeSerializer,
            status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorEnvelopeSerializer,
        },
        tags=["scheduling"],
    )
    def post(self, request: Request, appointment_id: UUID) -> Response:
        actor = _actor(request)
        serializer = AppointmentCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        appointment = cancel_appointment(
            actor=actor,
            appointment_id=appointment_id,
            correlation_id=get_request_id(request),
            requested_version=serializer.validated_data["version"],
            reason=serializer.validated_data["reason"],
        )
        return Response(
            AppointmentDetailResponseSerializer(
                appointment_detail_read_model(actor=actor, appointment=appointment)
            ).data
        )


def _appointment_slot_conflict(exc: IntegrityError) -> ApiProblem:
    cause = getattr(exc, "__cause__", None)
    constraint = getattr(getattr(cause, "diag", None), "constraint_name", "")
    fields = (
        {"room_id": ["Кабінет уже зайнятий."]}
        if constraint == "scheduling_no_room_overlap"
        else {"starts_at": ["Час спеціаліста вже зайнятий."]}
    )
    message = (
        "Кабінет уже зайнятий у цей час. Оберіть інший кабінет або час."
        if constraint == "scheduling_no_room_overlap"
        else "Спеціаліст уже має запис у цей час. Оберіть інше вікно."
    )
    return ApiProblem(
        code="appointment_slot_conflict",
        message=message,
        status_code=status.HTTP_409_CONFLICT,
        fields=fields,
    )
