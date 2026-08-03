from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User, UserRole
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.clinic.models import AppointmentStatusConfig, ClinicWorkday, Room, Service
from apps.patients.models import Patient
from apps.patients.selectors import patients_visible_to
from apps.scheduling.models import Appointment, AppointmentServiceLine
from apps.scheduling.selectors import (
    AVAILABILITY_STEP_MINUTES,
    CLINIC_TIMEZONE,
    appointments_visible_to,
)
from config.api.exceptions import ApiProblem


def appointment_snapshot(appointment: Appointment) -> dict[str, Any]:
    selected_services = _appointment_services_read_model(appointment)
    return {
        "public_number": appointment.public_number,
        "patient_id": appointment.patient_id,
        "specialist_id": appointment.specialist_id,
        "service_id": appointment.service_id,
        "service_ids": [item["id"] for item in selected_services],
        "room_id": appointment.room_id,
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
        "duration_minutes": appointment.duration_minutes,
        "service_name_snapshot": appointment.service_name_snapshot,
        "service_color_snapshot": appointment.service_color_snapshot,
        "room_label_snapshot": appointment.room_label_snapshot,
        "status": appointment.status_id,
        "complaints": appointment.complaints,
        "has_no_complaints": appointment.has_no_complaints,
        "comment": appointment.comment,
        "cancellation_reason": appointment.cancellation_reason,
        "version": appointment.version,
    }


def appointment_read_model(appointment: Appointment) -> dict[str, Any]:
    selected_services = _appointment_services_read_model(appointment)
    return {
        "id": appointment.pk,
        "public_number": appointment.public_number,
        "starts_at": appointment.starts_at,
        "ends_at": appointment.ends_at,
        "duration_minutes": appointment.duration_minutes,
        "patient": {
            "id": appointment.patient_id,
            "public_number": appointment.patient.public_number,
            "display_name": appointment.patient.display_name,
            "phone": appointment.patient.phone,
        },
        "service": {
            "id": appointment.service_id,
            "code": appointment.service.code,
            "name": appointment.service_name_snapshot,
            "color": appointment.service_color_snapshot,
        },
        "services": selected_services,
        "specialist": {
            "id": appointment.specialist_id,
            "display_name": appointment.specialist.display_name,
        },
        "room": {
            "id": appointment.room_id,
            "name": appointment.room_label_snapshot,
        },
        "status": {
            "code": appointment.status_id,
            "label": appointment.status.label,
            "color": appointment.status.color,
        },
        "complaints": appointment.complaints,
        "has_no_complaints": appointment.has_no_complaints,
        "comment": appointment.comment,
        "cancellation_reason": appointment.cancellation_reason,
        "version": appointment.version,
        "created_at": appointment.created_at,
        "updated_at": appointment.updated_at,
    }


def _appointment_services_read_model(appointment: Appointment) -> list[dict[str, Any]]:
    prefetched = getattr(appointment, "_prefetched_objects_cache", {}).get("service_lines")
    lines = (
        list(prefetched)
        if prefetched is not None
        else list(appointment.service_lines.select_related("service").all())
    )
    if not lines:
        return [
            {
                "id": appointment.service_id,
                "code": appointment.service.code,
                "name": appointment.service_name_snapshot,
                "color": appointment.service_color_snapshot,
                "duration_minutes": appointment.duration_minutes,
            }
        ]
    return [
        {
            "id": line.service_id,
            "code": line.service.code,
            "name": line.service_name_snapshot,
            "color": line.service_color_snapshot,
            "duration_minutes": line.duration_minutes,
        }
        for line in lines
    ]


STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "NEW": ("PENDING_CONFIRMATION", "CONFIRMED", "NO_SHOW"),
    "PENDING_CONFIRMATION": ("CONFIRMED", "NO_SHOW"),
    "CONFIRMED": ("ARRIVED", "NO_SHOW"),
    "ARRIVED": (),
    "IN_PROGRESS": (),
    "COMPLETED": (),
    "CANCELED": (),
    "NO_SHOW": (),
}
STATUS_ORDER = (
    "NEW",
    "PENDING_CONFIRMATION",
    "CONFIRMED",
    "ARRIVED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELED",
    "NO_SHOW",
)
EDITABLE_STATUSES = {"NEW", "PENDING_CONFIRMATION", "CONFIRMED", "ARRIVED"}
CANCELABLE_STATUSES = EDITABLE_STATUSES
TERMINAL_STATUSES = {"COMPLETED", "CANCELED", "NO_SHOW"}
VISIT_MANAGED_STATUSES = {"IN_PROGRESS", "COMPLETED"}


def _role_can_set_status(*, actor: User, config: AppointmentStatusConfig) -> bool:
    role_fields: dict[str, str] = {
        UserRole.ADMIN: "manual_admin",
        UserRole.RECEPTION: "manual_reception",
        UserRole.PODOLOGIST: "manual_podologist",
    }
    role_field = role_fields[actor.role]
    return bool(getattr(config, role_field))


def _can_cancel(*, actor: User, appointment: Appointment) -> bool:
    if appointment.status_id not in CANCELABLE_STATUSES:
        return False
    canceled = AppointmentStatusConfig.objects.filter(pk="CANCELED").first()
    return canceled is not None and _role_can_set_status(actor=actor, config=canceled)


def _allowed_status_configs(
    *,
    actor: User,
    appointment: Appointment,
) -> list[AppointmentStatusConfig]:
    allowed_codes = STATUS_TRANSITIONS.get(appointment.status_id, ())
    if appointment.starts_at > timezone.now():
        allowed_codes = tuple(code for code in allowed_codes if code != "NO_SHOW")
    configs = {
        item.code: item for item in AppointmentStatusConfig.objects.filter(code__in=allowed_codes)
    }
    return [
        configs[code]
        for code in STATUS_ORDER
        if code in configs
        and code not in VISIT_MANAGED_STATUSES
        and _role_can_set_status(actor=actor, config=configs[code])
    ]


def appointment_detail_read_model(
    *,
    actor: User,
    appointment: Appointment,
) -> dict[str, Any]:
    result = appointment_read_model(appointment)
    editable = appointment.status_id in EDITABLE_STATUSES
    visit = getattr(appointment, "visit", None)
    can_access_visit = actor.role == UserRole.ADMIN or (
        actor.role == UserRole.PODOLOGIST and appointment.specialist_id == actor.pk
    )
    result.update(
        {
            "allowed_status_transitions": [
                {
                    "code": item.code,
                    "label": item.label,
                    "color": item.color,
                }
                for item in _allowed_status_configs(actor=actor, appointment=appointment)
            ],
            "can_edit": editable,
            "can_reschedule": editable,
            "can_cancel": _can_cancel(actor=actor, appointment=appointment),
            "can_start_visit": can_access_visit
            and appointment.status_id == "ARRIVED"
            and visit is None,
            "visit_id": visit.pk if can_access_visit and visit is not None else None,
        }
    )
    return result


def _validate_complaints(*, complaints: str, has_no_complaints: bool) -> None:
    if has_no_complaints == bool(complaints):
        raise ApiProblem(
            code="complaints_required",
            message="Укажіть скарги або явно позначте, що скарг немає.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={
                "complaints": ["Заповніть причину звернення або виберіть «Скарг немає»."],
                "has_no_complaints": ["Оберіть лише один із двох варіантів."],
            },
        )


def _visible_patient(*, actor: User, patient_id: UUID) -> Patient:
    patient = patients_visible_to(actor).filter(pk=patient_id).first()
    if patient is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return patient


def _active_specialist(*, actor: User, specialist_id: int) -> User:
    if actor.role == UserRole.PODOLOGIST and specialist_id != actor.pk:
        raise ApiProblem(
            code="appointment_specialist_scope_violation",
            message="Подолог може створити запис лише до себе.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"specialist_id": ["Оберіть власний профіль подолога."]},
        )
    specialist = (
        User.objects.select_for_update()
        .filter(pk=specialist_id, role=UserRole.PODOLOGIST, is_active=True)
        .first()
    )
    if specialist is None:
        raise ApiProblem(
            code="appointment_specialist_unavailable",
            message="Спеціаліст недоступний для нового запису.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"specialist_id": ["Оберіть активного подолога."]},
        )
    return specialist


def _active_services(service_ids: list[UUID]) -> list[Service]:
    services_by_id = {
        service.pk: service
        for service in Service.objects.select_for_update().filter(
            pk__in=service_ids,
            is_active=True,
        )
    }
    if len(services_by_id) != len(service_ids):
        raise ApiProblem(
            code="appointment_service_unavailable",
            message="Одна або кілька послуг недоступні для нового запису.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"service_ids": ["Оберіть лише активні послуги."]},
        )
    return [services_by_id[service_id] for service_id in service_ids]


def _active_service(service_id: UUID) -> Service:
    """Compatibility helper for single-service follow-up appointment workflows."""
    try:
        return _active_services([service_id])[0]
    except ApiProblem as exc:
        raise ApiProblem(
            code=exc.problem_code,
            message="Послуга недоступна для нового запису.",
            status_code=exc.status_code,
            fields={"service_id": ["Оберіть активну послугу."]},
        ) from exc


def _replace_service_lines(
    *,
    appointment: Appointment,
    services: list[Service],
) -> None:
    appointment.service_lines.all().delete()
    AppointmentServiceLine.objects.bulk_create(
        [
            AppointmentServiceLine(
                appointment=appointment,
                service=service,
                position=position,
                duration_minutes=service.duration_minutes,
                service_name_snapshot=service.name,
                service_color_snapshot=service.color,
            )
            for position, service in enumerate(services)
        ]
    )


def _active_room(room_id: UUID) -> Room:
    room = Room.objects.select_for_update().filter(pk=room_id, is_active=True).first()
    if room is None:
        raise ApiProblem(
            code="appointment_room_unavailable",
            message="Кабінет недоступний для нового запису.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"room_id": ["Оберіть активний кабінет."]},
        )
    return room


def _validate_clinic_time(*, starts_at: datetime, ends_at: datetime) -> None:
    local_start = starts_at.astimezone(CLINIC_TIMEZONE)
    local_end = ends_at.astimezone(CLINIC_TIMEZONE)
    if (
        local_start.second != 0
        or local_start.microsecond != 0
        or local_start.minute % AVAILABILITY_STEP_MINUTES != 0
    ):
        raise ApiProblem(
            code="appointment_time_step_invalid",
            message="Час початку має відповідати 15-хвилинній сітці календаря.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"starts_at": ["Оберіть час із доступних вікон."]},
        )

    workday = (
        ClinicWorkday.objects.select_for_update()
        .prefetch_related("breaks")
        .filter(weekday=local_start.weekday())
        .first()
    )
    if (
        workday is None
        or not workday.is_working
        or workday.start_time is None
        or workday.end_time is None
        or local_start.date() != local_end.date()
        or local_start.timetz().replace(tzinfo=None) < workday.start_time
        or local_end.timetz().replace(tzinfo=None) > workday.end_time
    ):
        raise ApiProblem(
            code="appointment_outside_working_hours",
            message="Запис не вміщується в робочий день клініки.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"starts_at": ["Оберіть час у межах робочого дня."]},
        )

    for item in workday.breaks.all():
        if (
            local_start.timetz().replace(tzinfo=None) < item.end_time
            and local_end.timetz().replace(tzinfo=None) > item.start_time
        ):
            raise ApiProblem(
                code="appointment_during_break",
                message="Обраний час перетинається з перервою клініки.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={"starts_at": ["Оберіть вільне вікно поза перервою."]},
            )


def _validate_occupancy(
    *,
    specialist: User,
    room: Room,
    starts_at: datetime,
    ends_at: datetime,
    exclude_appointment_id: UUID | None = None,
) -> None:
    blocking = Appointment.objects.filter(
        ~Q(status_id="CANCELED"),
        time_range__overlap=(starts_at, ends_at),
    )
    if exclude_appointment_id is not None:
        blocking = blocking.exclude(pk=exclude_appointment_id)
    if blocking.filter(specialist=specialist).exists():
        raise ApiProblem(
            code="appointment_slot_conflict",
            message="Спеціаліст уже має запис у цей час. Оберіть інше вікно.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"starts_at": ["Час спеціаліста вже зайнятий."]},
        )
    if blocking.filter(room=room).exists():
        raise ApiProblem(
            code="appointment_slot_conflict",
            message="Кабінет уже зайнятий у цей час. Оберіть інший кабінет або час.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"room_id": ["Кабінет уже зайнятий."]},
        )


@transaction.atomic
def create_appointment(
    *,
    actor: User,
    correlation_id: str,
    data: dict[str, Any],
) -> Appointment:
    complaints = str(data.get("complaints", "")).strip()
    has_no_complaints = bool(data.get("has_no_complaints", False))
    _validate_complaints(
        complaints=complaints,
        has_no_complaints=has_no_complaints,
    )
    patient = _visible_patient(actor=actor, patient_id=data["patient_id"])
    specialist = _active_specialist(actor=actor, specialist_id=data["specialist_id"])
    services = _active_services(data["service_ids"])
    primary_service = services[0]
    room = _active_room(data["room_id"])
    starts_at = data["starts_at"]
    duration_minutes = sum(service.duration_minutes for service in services)
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    _validate_clinic_time(starts_at=starts_at, ends_at=ends_at)
    _validate_occupancy(
        specialist=specialist,
        room=room,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    status_config = AppointmentStatusConfig.objects.get(pk=data["status_code"])
    appointment = Appointment.objects.create(
        patient=patient,
        specialist=specialist,
        service=primary_service,
        room=room,
        time_range=(starts_at, ends_at),
        duration_minutes=duration_minutes,
        service_name_snapshot=primary_service.name,
        service_color_snapshot=primary_service.color,
        room_label_snapshot=room.name,
        status=status_config,
        complaints=complaints,
        has_no_complaints=has_no_complaints,
        comment=str(data.get("comment", "")).strip(),
    )
    _replace_service_lines(appointment=appointment, services=services)
    appointment.refresh_from_db()
    record_audit_event(
        actor=actor,
        action=AuditAction.APPOINTMENT_CREATED,
        object_type="appointment",
        object_id=appointment.pk,
        object_label=appointment.public_number,
        correlation_id=correlation_id,
        after=appointment_snapshot(appointment),
        description="Створено запис пацієнта.",
    )
    return appointment


def _locked_visible_appointment(*, actor: User, appointment_id: UUID) -> Appointment:
    appointment = (
        appointments_visible_to(actor)
        .select_for_update(of=("self",))
        .filter(pk=appointment_id)
        .first()
    )
    if appointment is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return appointment


def _validate_version(*, appointment: Appointment, requested_version: int) -> None:
    if appointment.version != requested_version:
        raise ApiProblem(
            code="appointment_version_conflict",
            message="Запис уже змінив інший користувач. Завантажте актуальну версію.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія запису застаріла."]},
        )


def _ensure_appointment_editable(appointment: Appointment) -> None:
    if appointment.status_id in TERMINAL_STATUSES:
        raise ApiProblem(
            code="appointment_terminal",
            message="Завершений, скасований або пропущений запис не можна змінювати.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if appointment.status_id not in EDITABLE_STATUSES:
        raise ApiProblem(
            code="appointment_locked",
            message="Після початку прийому дані запису змінюються лише через visit workflow.",
            status_code=status.HTTP_409_CONFLICT,
        )


@transaction.atomic
def update_appointment(
    *,
    actor: User,
    appointment_id: UUID,
    correlation_id: str,
    data: dict[str, Any],
) -> Appointment:
    requested_version = int(data.pop("version"))
    appointment = _locked_visible_appointment(actor=actor, appointment_id=appointment_id)
    _validate_version(appointment=appointment, requested_version=requested_version)
    _ensure_appointment_editable(appointment)

    before = appointment_snapshot(appointment)
    complaints = str(data.get("complaints", appointment.complaints)).strip()
    has_no_complaints = bool(data.get("has_no_complaints", appointment.has_no_complaints))
    _validate_complaints(complaints=complaints, has_no_complaints=has_no_complaints)

    schedule_fields = {"specialist_id", "service_ids", "room_id", "starts_at"}
    schedule_changed = bool(schedule_fields.intersection(data))
    specialist = appointment.specialist
    current_lines = list(
        appointment.service_lines.select_for_update().select_related("service").all()
    )
    current_services = [line.service for line in current_lines] or [appointment.service]
    services = current_services
    primary_service = appointment.service
    room = appointment.room
    starts_at = appointment.starts_at
    ends_at = appointment.ends_at
    if schedule_changed:
        specialist = _active_specialist(
            actor=actor,
            specialist_id=int(data.get("specialist_id", appointment.specialist_id)),
        )
        requested_service_ids = data.get(
            "service_ids",
            [service.pk for service in current_services],
        )
        services = _active_services(requested_service_ids)
        primary_service = services[0]
        room = _active_room(data.get("room_id", appointment.room_id))
        starts_at = data.get("starts_at", appointment.starts_at)
        ends_at = starts_at + timedelta(
            minutes=sum(service.duration_minutes for service in services)
        )
        _validate_clinic_time(starts_at=starts_at, ends_at=ends_at)
        _validate_occupancy(
            specialist=specialist,
            room=room,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_appointment_id=appointment.pk,
        )

    candidate = {
        "specialist_id": specialist.pk,
        "service_id": primary_service.pk,
        "service_ids": [service.pk for service in services],
        "room_id": room.pk,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "duration_minutes": (
            sum(service.duration_minutes for service in services)
            if schedule_changed
            else appointment.duration_minutes
        ),
        "complaints": complaints,
        "has_no_complaints": has_no_complaints,
        "comment": str(data.get("comment", appointment.comment)).strip(),
    }
    comparable_before = {key: before[key] for key in candidate}
    if comparable_before == candidate:
        raise ApiProblem(
            code="appointment_no_changes",
            message="У записі немає нових змін.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"non_field_errors": ["Змініть хоча б одне поле."]},
        )

    appointment.specialist = specialist
    appointment.service = primary_service
    appointment.room = room
    appointment.time_range = (starts_at, ends_at)
    if schedule_changed:
        appointment.duration_minutes = candidate["duration_minutes"]
        appointment.service_name_snapshot = primary_service.name
        appointment.service_color_snapshot = primary_service.color
        appointment.room_label_snapshot = room.name
    appointment.complaints = complaints
    appointment.has_no_complaints = has_no_complaints
    appointment.comment = candidate["comment"]
    appointment.version += 1
    appointment.save()
    if schedule_changed:
        _replace_service_lines(appointment=appointment, services=services)
    appointment.refresh_from_db()

    action = (
        AuditAction.APPOINTMENT_RESCHEDULED if schedule_changed else AuditAction.APPOINTMENT_UPDATED
    )
    record_audit_event(
        actor=actor,
        action=action,
        object_type="appointment",
        object_id=appointment.pk,
        object_label=appointment.public_number,
        correlation_id=correlation_id,
        before=before,
        after=appointment_snapshot(appointment),
        description=(
            "Перенесено або змінено ресурси запису."
            if schedule_changed
            else "Оновлено дані запису."
        ),
    )
    return appointment


@transaction.atomic
def transition_appointment_status(
    *,
    actor: User,
    appointment_id: UUID,
    correlation_id: str,
    requested_version: int,
    status_code: str,
) -> Appointment:
    appointment = _locked_visible_appointment(actor=actor, appointment_id=appointment_id)
    _validate_version(appointment=appointment, requested_version=requested_version)
    if appointment.status_id in TERMINAL_STATUSES:
        raise ApiProblem(
            code="appointment_terminal",
            message="Термінальний статус не можна змінити.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if status_code == "CANCELED":
        raise ApiProblem(
            code="appointment_cancel_reason_required",
            message="Для скасування використайте окрему дію та вкажіть причину.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"status_code": ["Скористайтеся дією «Скасувати запис»."]},
        )
    if status_code in VISIT_MANAGED_STATUSES:
        raise ApiProblem(
            code="appointment_status_managed_by_visit",
            message="Цей статус встановлюється лише через visit workflow.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if status_code not in STATUS_TRANSITIONS.get(appointment.status_id, ()):
        raise ApiProblem(
            code="appointment_status_transition_invalid",
            message="Такий перехід статусу не дозволений.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"status_code": ["Оберіть одну з доступних дій."]},
        )
    if status_code == "NO_SHOW" and appointment.starts_at > timezone.now():
        raise ApiProblem(
            code="appointment_no_show_too_early",
            message="Неявку можна зафіксувати лише після запланованого початку.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"status_code": ["Дочекайтеся часу початку запису."]},
        )
    target = AppointmentStatusConfig.objects.select_for_update().get(pk=status_code)
    if not _role_can_set_status(actor=actor, config=target):
        raise ApiProblem(
            code="appointment_status_forbidden",
            message="Ваша роль не може вручну встановити цей статус.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    before = appointment_snapshot(appointment)
    appointment.status = target
    appointment.version += 1
    appointment.save()
    record_audit_event(
        actor=actor,
        action=AuditAction.APPOINTMENT_STATUS_CHANGED,
        object_type="appointment",
        object_id=appointment.pk,
        object_label=appointment.public_number,
        correlation_id=correlation_id,
        before=before,
        after=appointment_snapshot(appointment),
        description=f"Статус запису змінено на «{target.label}».",
    )
    if status_code == "ARRIVED":
        from apps.notifications.services import notify_domain_event_on_commit

        notify_domain_event_on_commit(
            event="appointment_arrived",
            object_id=str(appointment.pk),
            event_version=appointment.version,
            actor_id=actor.pk,
        )
    return appointment


@transaction.atomic
def cancel_appointment(
    *,
    actor: User,
    appointment_id: UUID,
    correlation_id: str,
    requested_version: int,
    reason: str,
) -> Appointment:
    appointment = _locked_visible_appointment(actor=actor, appointment_id=appointment_id)
    _validate_version(appointment=appointment, requested_version=requested_version)
    if appointment.status_id not in CANCELABLE_STATUSES:
        raise ApiProblem(
            code="appointment_cancel_forbidden_state",
            message="Цей запис уже не можна скасувати.",
            status_code=status.HTTP_409_CONFLICT,
        )
    target = AppointmentStatusConfig.objects.select_for_update().get(pk="CANCELED")
    if not _role_can_set_status(actor=actor, config=target):
        raise ApiProblem(
            code="appointment_cancel_forbidden",
            message="Ваша роль не може скасувати цей запис.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    before = appointment_snapshot(appointment)
    appointment.status = target
    appointment.cancellation_reason = reason.strip()
    appointment.version += 1
    appointment.save()
    record_audit_event(
        actor=actor,
        action=AuditAction.APPOINTMENT_CANCELED,
        object_type="appointment",
        object_id=appointment.pk,
        object_label=appointment.public_number,
        correlation_id=correlation_id,
        before=before,
        after=appointment_snapshot(appointment),
        description="Запис скасовано із зазначенням причини.",
    )
    from apps.notifications.services import notify_domain_event_on_commit

    notify_domain_event_on_commit(
        event="appointment_canceled",
        object_id=str(appointment.pk),
        event_version=appointment.version,
        actor_id=actor.pk,
    )
    return appointment
