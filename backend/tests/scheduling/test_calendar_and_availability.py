from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.clinic.models import AppointmentStatusConfig, Room, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment

PASSWORD = "test-only-password-placeholder"  # noqa: S105
KYIV = ZoneInfo("Europe/Kyiv")


def create_user(*, email: str, role: str, first_name: str = "Тест") -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name=first_name,
        last_name="Працівник",
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_service(*, code: str = "CARE", duration_minutes: int = 45) -> Service:
    return Service.objects.create(
        code=code,
        name="Медичний педикюр",
        duration_minutes=duration_minutes,
        price_minor=150000,
        color="#0F766E",
    )


def create_patient(*, suffix: str = "") -> Patient:
    return Patient.objects.create(
        first_name=f"Марія{suffix}",
        last_name="Бондар",
        phone=f"0671234{567 + len(suffix):03d}",
    )


def create_appointment(
    *,
    patient: Patient,
    specialist: User,
    service: Service,
    room: Room,
    starts_at: datetime,
    status_code: str = "CONFIRMED",
) -> Appointment:
    ends_at = starts_at + timedelta(minutes=service.duration_minutes)
    status_config, _ = AppointmentStatusConfig.objects.get_or_create(
        code=status_code,
        defaults={
            "label": status_code.title(),
            "color": "#2563EB",
        },
    )
    return Appointment.objects.create(
        patient=patient,
        specialist=specialist,
        service=service,
        room=room,
        time_range=(starts_at, ends_at),
        duration_minutes=service.duration_minutes,
        service_name_snapshot=service.name,
        service_color_snapshot=service.color,
        room_label_snapshot=room.name,
        status=status_config,
        has_no_complaints=True,
    )


@pytest.mark.django_db(transaction=True)
def test_database_blocks_specialist_and_room_overlap_but_allows_independent_resources() -> None:
    first_specialist = create_user(
        email="first@example.test", role=UserRole.PODOLOGIST, first_name="Олена"
    )
    second_specialist = create_user(
        email="second@example.test", role=UserRole.PODOLOGIST, first_name="Ірина"
    )
    first_room, _ = Room.objects.get_or_create(name="Кабінет 1")
    second_room = Room.objects.create(name="Кабінет 2")
    service = create_service()
    starts_at = datetime(2026, 7, 27, 10, 0, tzinfo=KYIV)
    create_appointment(
        patient=create_patient(suffix="A"),
        specialist=first_specialist,
        service=service,
        room=first_room,
        starts_at=starts_at,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_appointment(
            patient=create_patient(suffix="B"),
            specialist=first_specialist,
            service=service,
            room=second_room,
            starts_at=starts_at,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        create_appointment(
            patient=create_patient(suffix="C"),
            specialist=second_specialist,
            service=service,
            room=first_room,
            starts_at=starts_at,
        )

    independent = create_appointment(
        patient=create_patient(suffix="D"),
        specialist=second_specialist,
        service=service,
        room=second_room,
        starts_at=starts_at,
    )
    canceled = create_appointment(
        patient=create_patient(suffix="E"),
        specialist=first_specialist,
        service=service,
        room=first_room,
        starts_at=starts_at,
        status_code="CANCELED",
    )

    assert independent.pk is not None
    assert canceled.status_id == "CANCELED"


@pytest.mark.django_db
def test_calendar_returns_concurrent_columns_and_applies_podologist_scope() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    first_specialist = create_user(
        email="first@example.test", role=UserRole.PODOLOGIST, first_name="Олена"
    )
    second_specialist = create_user(
        email="second@example.test", role=UserRole.PODOLOGIST, first_name="Ірина"
    )
    first_room, _ = Room.objects.get_or_create(name="Кабінет 1")
    second_room = Room.objects.create(name="Кабінет 2")
    service = create_service()
    starts_at = datetime(2026, 7, 27, 10, 0, tzinfo=KYIV)
    first = create_appointment(
        patient=create_patient(suffix="A"),
        specialist=first_specialist,
        service=service,
        room=first_room,
        starts_at=starts_at,
    )
    second = create_appointment(
        patient=create_patient(suffix="B"),
        specialist=second_specialist,
        service=service,
        room=second_room,
        starts_at=starts_at,
    )
    query = "from=2026-07-26T21:00:00Z&to=2026-07-27T21:00:00Z"

    shared = authenticated_client(admin).get(f"/api/v1/calendar?{query}")
    own = authenticated_client(first_specialist).get(f"/api/v1/calendar?{query}")
    hidden = authenticated_client(first_specialist).get(
        f"/api/v1/calendar?{query}&specialist_id={second_specialist.pk}"
    )

    assert shared.status_code == 200
    shared_body = shared.json()
    assert [item["id"] for item in shared_body["events"]] == [str(first.pk), str(second.pk)]
    assert len(shared_body["specialists"]) == 2
    assert shared_body["days"][0]["starts_at"] == "2026-07-27T06:00:00Z"
    assert shared_body["days"][0]["breaks"][0] == {
        "starts_at": "2026-07-27T10:00:00Z",
        "ends_at": "2026-07-27T11:00:00Z",
    }
    assert own.status_code == 200
    assert [item["id"] for item in own.json()["events"]] == [str(first.pk)]
    assert own.json()["specialists"] == [
        {"id": first_specialist.pk, "display_name": first_specialist.display_name}
    ]
    assert hidden.status_code == 404


@pytest.mark.django_db
def test_availability_respects_hours_breaks_duration_specialist_and_room_occupancy() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    target = create_user(email="target@example.test", role=UserRole.PODOLOGIST)
    other = create_user(email="other@example.test", role=UserRole.PODOLOGIST)
    first_room, _ = Room.objects.get_or_create(name="Кабінет 1")
    second_room = Room.objects.create(name="Кабінет 2")
    service = create_service()
    create_appointment(
        patient=create_patient(suffix="A"),
        specialist=target,
        service=service,
        room=first_room,
        starts_at=datetime(2026, 7, 27, 10, 0, tzinfo=KYIV),
    )
    create_appointment(
        patient=create_patient(suffix="B"),
        specialist=other,
        service=service,
        room=first_room,
        starts_at=datetime(2026, 7, 27, 11, 0, tzinfo=KYIV),
    )
    base_query = f"date=2026-07-27&specialist_id={target.pk}&service_id={service.pk}"

    response = authenticated_client(admin).get(f"/api/v1/appointments/availability?{base_query}")
    first_room_only = authenticated_client(admin).get(
        f"/api/v1/appointments/availability?{base_query}&room_id={first_room.pk}"
    )

    assert response.status_code == 200
    body = response.json()
    slots = {item["starts_at"]: item for item in body["slots"]}
    assert body["step_minutes"] == 15
    assert "2026-07-27T06:00:00Z" in slots  # 09:00 local
    assert "2026-07-27T07:15:00Z" not in slots  # overlaps the target's 10:00 booking
    assert "2026-07-27T08:00:00Z" in slots  # room 2 stays free at 11:00
    assert slots["2026-07-27T08:00:00Z"]["rooms"] == [
        {"id": str(second_room.pk), "name": second_room.name}
    ]
    assert "2026-07-27T09:30:00Z" not in slots  # duration crosses the 13:00 break
    assert "2026-07-27T14:15:00Z" in slots  # 17:15–18:00 fits exactly
    assert "2026-07-27T14:30:00Z" not in slots
    assert first_room_only.status_code == 200
    assert "2026-07-27T08:00:00Z" not in {
        item["starts_at"] for item in first_room_only.json()["slots"]
    }


@pytest.mark.django_db
def test_availability_uses_the_sum_of_all_selected_service_durations() -> None:
    admin = create_user(email="admin-multi@example.test", role=UserRole.ADMIN)
    specialist = create_user(email="multi@example.test", role=UserRole.PODOLOGIST)
    Room.objects.get_or_create(name="Кабінет 1")
    first = create_service(code="FIRST", duration_minutes=45)
    second = create_service(code="SECOND", duration_minutes=30)
    second.name = "Обробка нігтів"
    second.color = "#7C3AED"
    second.save(update_fields=("name", "color"))
    query = (
        f"date=2026-07-27&specialist_id={specialist.pk}"
        f"&service_ids={first.pk}&service_ids={second.pk}"
    )

    response = authenticated_client(admin).get(f"/api/v1/appointments/availability?{query}")

    assert response.status_code == 200
    body = response.json()
    assert body["duration_minutes"] == 75
    assert [item["id"] for item in body["services"]] == [str(first.pk), str(second.pk)]
    assert body["slots"][0]["ends_at"] == "2026-07-27T07:15:00Z"
    assert "2026-07-27T13:45:00Z" in {item["starts_at"] for item in body["slots"]}
    assert "2026-07-27T14:00:00Z" not in {item["starts_at"] for item in body["slots"]}


@pytest.mark.django_db
def test_availability_is_closed_on_non_working_day_and_hides_foreign_podologist() -> None:
    podologist = create_user(email="owner@example.test", role=UserRole.PODOLOGIST)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    Room.objects.get_or_create(name="Кабінет 1")
    service = create_service()

    closed = authenticated_client(podologist).get(
        "/api/v1/appointments/availability"
        f"?date=2026-07-26&specialist_id={podologist.pk}&service_id={service.pk}"
    )
    hidden = authenticated_client(podologist).get(
        "/api/v1/appointments/availability"
        f"?date=2026-07-27&specialist_id={foreign.pk}&service_id={service.pk}"
    )

    assert closed.status_code == 200
    assert closed.json()["slots"] == []
    assert hidden.status_code == 404


@pytest.mark.django_db
def test_scheduling_reads_require_authentication_and_validate_calendar_range() -> None:
    client = APIClient()

    assert client.get("/api/v1/calendar").status_code == 401
    assert client.get("/api/v1/appointments/availability").status_code == 401

    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    invalid = authenticated_client(admin).get(
        "/api/v1/calendar?from=2026-07-28T00:00:00Z&to=2026-07-27T00:00:00Z"
    )
    assert invalid.status_code == 422
    assert "to" in invalid.json()["fields"]
