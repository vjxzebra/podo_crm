from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Case, IntegerField, Q, QuerySet, Subquery, Value, When
from django.db.models.functions import Concat, Greatest
from django.http import Http404

from apps.accounts.models import User, UserRole
from apps.clinic.models import ClinicWorkday, Room, Service
from apps.patients.normalization import phone_digits
from apps.scheduling.models import Appointment

CLINIC_TIMEZONE_NAME = "Europe/Kyiv"
CLINIC_TIMEZONE = ZoneInfo(CLINIC_TIMEZONE_NAME)
AVAILABILITY_STEP_MINUTES = 15


def appointments_visible_to(actor: User) -> QuerySet[Appointment]:
    queryset = Appointment.objects.select_related(
        "patient",
        "specialist",
        "service",
        "room",
        "status",
        "visit",
    )
    if actor.role == UserRole.PODOLOGIST:
        return queryset.filter(specialist=actor)
    return queryset


def appointments_for_global_search(actor: User, search: str) -> QuerySet[Appointment]:
    from apps.patients.selectors import patients_visible_to, search_patients

    term = search.strip()
    digits = phone_digits(term)
    scoped_appointments = appointments_visible_to(actor).select_related(None)
    matching_appointment_ids = (
        scoped_appointments.filter(
            Q(public_number__icontains=term) | Q(service_name_snapshot__icontains=term)
        )
        .order_by()
        .values("pk")
    )
    matching_patient_ids = (
        search_patients(
            patients_visible_to(actor),
            term,
        )
        .order_by()
        .values("pk")
    )
    matching_service_ids = Service.objects.filter(code__icontains=term).order_by().values("pk")
    matching_patient_appointment_ids = (
        scoped_appointments.filter(patient_id__in=Subquery(matching_patient_ids))
        .order_by()
        .values("pk")
    )
    matching_service_appointment_ids = (
        scoped_appointments.filter(service_id__in=Subquery(matching_service_ids))
        .order_by()
        .values("pk")
    )
    exact_identifier = (
        Q(public_number__iexact=term)
        | Q(service__code__iexact=term)
        | Q(patient__public_number__iexact=term)
    )
    identifier_prefix = (
        Q(public_number__istartswith=term)
        | Q(service__code__istartswith=term)
        | Q(patient__public_number__istartswith=term)
    )
    name_prefix = (
        Q(service_name_snapshot__istartswith=term)
        | Q(patient__first_name__istartswith=term)
        | Q(patient__last_name__istartswith=term)
        | Q(global_search_patient_name__istartswith=term)
    )
    if digits:
        exact_identifier |= Q(patient__normalized_phone=digits)
        identifier_prefix |= Q(patient__normalized_phone__startswith=digits)
    matches = (
        Q(pk__in=Subquery(matching_appointment_ids))
        | Q(pk__in=Subquery(matching_service_appointment_ids))
        | Q(pk__in=Subquery(matching_patient_appointment_ids))
    )
    return (
        scoped_appointments.select_related("patient", "specialist", "status")
        .only(
            "id",
            "public_number",
            "time_range",
            "service_name_snapshot",
            "patient__id",
            "patient__first_name",
            "patient__last_name",
            "specialist__id",
            "specialist__first_name",
            "specialist__last_name",
            "specialist__email",
            "status__code",
            "status__label",
        )
        .alias(
            global_search_patient_name=Concat(
                "patient__first_name",
                Value(" "),
                "patient__last_name",
            )
        )
        .filter(matches)
        .alias(
            global_search_rank=Case(
                When(exact_identifier, then=Value(0)),
                When(identifier_prefix, then=Value(1)),
                When(name_prefix, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            global_search_similarity=Greatest(
                TrigramSimilarity("public_number", term),
                TrigramSimilarity("service_name_snapshot", term),
                TrigramSimilarity("service__code", term),
                TrigramSimilarity("patient__first_name", term),
                TrigramSimilarity("patient__last_name", term),
                TrigramSimilarity("patient__public_number", term),
                TrigramSimilarity("patient__normalized_phone", term),
            ),
        )
        .order_by("global_search_rank", "-global_search_similarity", "-time_range", "id")
    )


def _specialists_for(actor: User, specialist_id: int | None) -> QuerySet[User]:
    queryset = User.objects.filter(role=UserRole.PODOLOGIST, is_active=True).order_by(
        "last_name", "first_name", "email", "pk"
    )
    if actor.role == UserRole.PODOLOGIST:
        if specialist_id is not None and specialist_id != actor.pk:
            raise Http404
        return queryset.filter(pk=actor.pk)
    if specialist_id is not None:
        queryset = queryset.filter(pk=specialist_id)
        if not queryset.exists():
            raise Http404
    return queryset


def _local_datetime(day: date, value: time) -> datetime:
    return datetime.combine(day, value, tzinfo=CLINIC_TIMEZONE)


def _iter_local_dates(range_start: datetime, range_end: datetime) -> list[date]:
    current = range_start.astimezone(CLINIC_TIMEZONE).date()
    final = (range_end - timedelta(microseconds=1)).astimezone(CLINIC_TIMEZONE).date()
    values: list[date] = []
    while current <= final:
        values.append(current)
        current += timedelta(days=1)
    return values


def _specialist_summary(user: User) -> dict[str, object]:
    return {
        "id": user.pk,
        "display_name": user.display_name,
    }


def _room_summary(room: Room) -> dict[str, object]:
    return {
        "id": room.pk,
        "name": room.name,
    }


def calendar_read_model(
    *,
    actor: User,
    range_start: datetime,
    range_end: datetime,
    specialist_id: int | None,
) -> dict[str, object]:
    specialists = list(_specialists_for(actor, specialist_id))
    appointments = (
        Appointment.objects.select_related(
            "patient",
            "specialist",
            "service",
            "room",
            "status",
        )
        .filter(
            specialist__in=specialists,
            time_range__overlap=(range_start, range_end),
        )
        .order_by("time_range", "specialist__last_name", "specialist_id", "id")
    )

    schedule = {
        item.weekday: item for item in ClinicWorkday.objects.prefetch_related("breaks").all()
    }
    days: list[dict[str, object]] = []
    for local_date in _iter_local_dates(range_start, range_end):
        workday = schedule.get(local_date.weekday())
        if (
            workday is None
            or not workday.is_working
            or workday.start_time is None
            or workday.end_time is None
        ):
            days.append(
                {
                    "date": local_date,
                    "is_working": False,
                    "starts_at": None,
                    "ends_at": None,
                    "breaks": [],
                }
            )
            continue
        days.append(
            {
                "date": local_date,
                "is_working": True,
                "starts_at": _local_datetime(local_date, workday.start_time),
                "ends_at": _local_datetime(local_date, workday.end_time),
                "breaks": [
                    {
                        "starts_at": _local_datetime(local_date, item.start_time),
                        "ends_at": _local_datetime(local_date, item.end_time),
                    }
                    for item in workday.breaks.all()
                ],
            }
        )

    events = [
        {
            "id": appointment.pk,
            "public_number": appointment.public_number,
            "starts_at": appointment.starts_at,
            "ends_at": appointment.ends_at,
            "duration_minutes": appointment.duration_minutes,
            "patient": {
                "id": appointment.patient_id,
                "public_number": appointment.patient.public_number,
                "display_name": appointment.patient.display_name,
            },
            "service": {
                "id": appointment.service_id,
                "name": appointment.service_name_snapshot,
                "color": appointment.service_color_snapshot,
            },
            "specialist": _specialist_summary(appointment.specialist),
            "room": {
                "id": appointment.room_id,
                "name": appointment.room_label_snapshot,
            },
            "status": {
                "code": appointment.status_id,
                "label": appointment.status.label,
                "color": appointment.status.color,
            },
        }
        for appointment in appointments
    ]
    return {
        "timezone": CLINIC_TIMEZONE_NAME,
        "range": {
            "from": range_start.astimezone(UTC),
            "to": range_end.astimezone(UTC),
        },
        "specialists": [_specialist_summary(item) for item in specialists],
        "days": days,
        "events": events,
    }


def _overlaps(start: datetime, end: datetime, other_start: datetime, other_end: datetime) -> bool:
    return start < other_end and end > other_start


def appointment_availability(
    *,
    actor: User,
    local_date: date,
    specialist: User,
    service: Service,
    requested_room: Room | None,
) -> dict[str, object]:
    if actor.role == UserRole.PODOLOGIST and specialist.pk != actor.pk:
        raise Http404

    workday = (
        ClinicWorkday.objects.prefetch_related("breaks")
        .filter(weekday=local_date.weekday())
        .first()
    )
    rooms = list(
        Room.objects.filter(pk=requested_room.pk, is_active=True)
        if requested_room is not None
        else Room.objects.filter(is_active=True).order_by("name", "pk")
    )
    slots: list[dict[str, object]] = []
    if (
        workday is not None
        and workday.is_working
        and workday.start_time is not None
        and workday.end_time is not None
        and rooms
    ):
        day_start = _local_datetime(local_date, workday.start_time)
        day_end = _local_datetime(local_date, workday.end_time)
        breaks = [
            (
                _local_datetime(local_date, item.start_time),
                _local_datetime(local_date, item.end_time),
            )
            for item in workday.breaks.all()
        ]
        appointments = list(
            Appointment.objects.filter(
                status__code__in=(
                    "NEW",
                    "PENDING_CONFIRMATION",
                    "CONFIRMED",
                    "ARRIVED",
                    "IN_PROGRESS",
                    "COMPLETED",
                    "NO_SHOW",
                ),
                time_range__overlap=(day_start, day_end),
            )
            .filter(models_query_for_resources(specialist=specialist, rooms=rooms))
            .only("specialist_id", "room_id", "time_range")
        )
        specialist_busy = [
            (item.starts_at, item.ends_at)
            for item in appointments
            if item.specialist_id == specialist.pk
        ]
        room_busy: dict[object, list[tuple[datetime, datetime]]] = {room.pk: [] for room in rooms}
        for appointment in appointments:
            if appointment.room_id in room_busy:
                room_busy[appointment.room_id].append((appointment.starts_at, appointment.ends_at))

        duration = timedelta(minutes=service.duration_minutes)
        step = timedelta(minutes=AVAILABILITY_STEP_MINUTES)
        candidate = day_start
        while candidate + duration <= day_end:
            candidate_end = candidate + duration
            blocked_by_break = any(
                _overlaps(candidate, candidate_end, break_start, break_end)
                for break_start, break_end in breaks
            )
            specialist_is_busy = any(
                _overlaps(candidate, candidate_end, busy_start, busy_end)
                for busy_start, busy_end in specialist_busy
            )
            if not blocked_by_break and not specialist_is_busy:
                free_rooms = [
                    room
                    for room in rooms
                    if not any(
                        _overlaps(candidate, candidate_end, busy_start, busy_end)
                        for busy_start, busy_end in room_busy[room.pk]
                    )
                ]
                if free_rooms:
                    slots.append(
                        {
                            "starts_at": candidate,
                            "ends_at": candidate_end,
                            "rooms": [_room_summary(room) for room in free_rooms],
                        }
                    )
            candidate += step

    return {
        "timezone": CLINIC_TIMEZONE_NAME,
        "date": local_date,
        "specialist": _specialist_summary(specialist),
        "service": {
            "id": service.pk,
            "name": service.name,
            "duration_minutes": service.duration_minutes,
        },
        "requested_room": _room_summary(requested_room) if requested_room is not None else None,
        "step_minutes": AVAILABILITY_STEP_MINUTES,
        "slots": slots,
    }


def models_query_for_resources(*, specialist: User, rooms: list[Room]) -> object:
    """Keep the availability query in one DB round-trip for specialist and room occupancy."""
    from django.db.models import Q

    return Q(specialist=specialist) | Q(room__in=rooms)
