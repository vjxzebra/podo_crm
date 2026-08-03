from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from django.db import close_old_connections, connections
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import AppointmentStatusConfig, ClinicBreak, ClinicWorkday, Room, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, AppointmentServiceLine

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


def scheduling_fixture() -> tuple[User, Service, Room, Patient]:
    specialist = create_user(
        email="specialist@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Олена",
    )
    service = Service.objects.create(
        code="CARE",
        name="Медичний педикюр",
        duration_minutes=45,
        price_minor=150000,
        color="#0F766E",
    )
    room, _ = Room.objects.get_or_create(name="Кабінет 1")
    if not room.is_active:
        room.is_active = True
        room.save(update_fields=("is_active",))
    patient = Patient.objects.create(
        first_name="Марія",
        last_name="Бондар",
        phone="0671234567",
        primary_podologist=specialist,
    )
    status_config, _ = AppointmentStatusConfig.objects.update_or_create(
        code="NEW",
        defaults={
            "label": "Новий",
            "color": "#64748B",
            "manual_admin": True,
            "manual_reception": True,
            "manual_podologist": False,
        },
    )
    workday, _ = ClinicWorkday.objects.update_or_create(
        weekday=0,
        defaults={
            "is_working": True,
            "start_time": time(9, 0),
            "end_time": time(18, 0),
        },
    )
    workday.breaks.all().delete()
    ClinicBreak.objects.create(
        workday=workday,
        start_time=time(13, 0),
        end_time=time(14, 0),
    )
    assert status_config.pk == "NEW"
    return specialist, service, room, patient


def appointment_payload(
    *,
    specialist: User,
    service: Service,
    room: Room,
    patient: Patient,
    starts_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "patient_id": str(patient.pk),
        "specialist_id": specialist.pk,
        "service_id": str(service.pk),
        "room_id": str(room.pk),
        "starts_at": (starts_at or datetime(2026, 7, 27, 10, 0, tzinfo=KYIV)).isoformat(),
        "complaints": "Біль під час ходьби",
        "has_no_complaints": False,
        "comment": "Перший візит",
        "status_code": "NEW",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.RECEPTION])
def test_admin_and_reception_create_audited_appointment_with_server_snapshots(role: str) -> None:
    specialist, service, room, patient = scheduling_fixture()
    actor = create_user(email=f"{role}@example.test", role=role)

    response = authenticated_client(actor).post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
        ),
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["starts_at"] == "2026-07-27T07:00:00Z"
    assert body["ends_at"] == "2026-07-27T07:45:00Z"
    assert body["duration_minutes"] == 45
    assert body["service"] == {
        "id": str(service.pk),
        "code": "CARE",
        "name": "Медичний педикюр",
        "color": "#0F766E",
    }
    assert body["room"] == {"id": str(room.pk), "name": "Кабінет 1"}
    assert body["status"]["code"] == "NEW"
    appointment = Appointment.objects.get()
    assert appointment.service_name_snapshot == service.name
    assert appointment.room_label_snapshot == room.name
    event = AuditEvent.objects.get(action=AuditAction.APPOINTMENT_CREATED)
    assert event.object_id == str(appointment.pk)
    assert event.actor_id == actor.pk
    assert event.after["patient_id"] == str(patient.pk)


@pytest.mark.django_db
def test_create_sums_multiple_services_and_keeps_ordered_color_snapshots() -> None:
    specialist, service, room, patient = scheduling_fixture()
    additional = Service.objects.create(
        code="NAILS",
        name="Обробка нігтів",
        duration_minutes=30,
        price_minor=80000,
        color="#7C3AED",
    )
    admin = create_user(email="admin-multi@example.test", role=UserRole.ADMIN)
    payload = appointment_payload(
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    payload.pop("service_id")
    payload["service_ids"] = [str(service.pk), str(additional.pk)]

    response = authenticated_client(admin).post(
        "/api/v1/appointments",
        payload,
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["duration_minutes"] == 75
    assert body["ends_at"] == "2026-07-27T08:15:00Z"
    assert body["services"] == [
        {
            "id": str(service.pk),
            "code": service.code,
            "name": service.name,
            "color": service.color,
            "duration_minutes": 45,
        },
        {
            "id": str(additional.pk),
            "code": additional.code,
            "name": additional.name,
            "color": additional.color,
            "duration_minutes": 30,
        },
    ]
    appointment = Appointment.objects.get()
    assert appointment.service_id == service.pk
    assert appointment.duration_minutes == 75
    assert list(
        AppointmentServiceLine.objects.values_list(
            "service_id", "position", "duration_minutes", "service_color_snapshot"
        )
    ) == [
        (service.pk, 0, 45, "#0F766E"),
        (additional.pk, 1, 30, "#7C3AED"),
    ]
    event = AuditEvent.objects.get(action=AuditAction.APPOINTMENT_CREATED)
    assert event.after["service_ids"] == [str(service.pk), str(additional.pk)]


@pytest.mark.django_db
def test_podologist_can_create_only_for_self_and_visible_patient() -> None:
    specialist, service, room, patient = scheduling_fixture()
    other_specialist = create_user(
        email="other@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Ірина",
    )
    foreign_patient = Patient.objects.create(
        first_name="Чужа",
        last_name="Пацієнтка",
        phone="0509876543",
        primary_podologist=other_specialist,
    )
    client = authenticated_client(specialist)

    foreign_specialist = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=other_specialist,
            service=service,
            room=room,
            patient=patient,
        ),
        format="json",
    )
    hidden_patient = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=foreign_patient,
        ),
        format="json",
    )
    created = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
        ),
        format="json",
    )

    assert foreign_specialist.status_code == 422
    assert foreign_specialist.json()["code"] == "appointment_specialist_scope_violation"
    assert hidden_patient.status_code == 404
    assert created.status_code == 201
    assert created.json()["specialist"]["id"] == specialist.pk
    assert Appointment.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("complaints", "has_no_complaints"),
    [("", False), ("Біль", True)],
)
def test_complaints_xor_returns_specific_validation_problem(
    complaints: str,
    has_no_complaints: bool,
) -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    payload = appointment_payload(
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    payload.update({"complaints": complaints, "has_no_complaints": has_no_complaints})

    response = authenticated_client(admin).post(
        "/api/v1/appointments",
        payload,
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "complaints_required"
    assert not Appointment.objects.exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_create_rejects_invalid_grid_break_and_workday_boundaries() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)

    invalid_grid = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
            starts_at=datetime(2026, 7, 27, 10, 7, tzinfo=KYIV),
        ),
        format="json",
    )
    during_break = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
            starts_at=datetime(2026, 7, 27, 12, 30, tzinfo=KYIV),
        ),
        format="json",
    )
    outside_hours = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
            starts_at=datetime(2026, 7, 27, 17, 30, tzinfo=KYIV),
        ),
        format="json",
    )

    assert invalid_grid.status_code == 422
    assert invalid_grid.json()["code"] == "appointment_time_step_invalid"
    assert during_break.status_code == 422
    assert during_break.json()["code"] == "appointment_during_break"
    assert outside_hours.status_code == 422
    assert outside_hours.json()["code"] == "appointment_outside_working_hours"
    assert not Appointment.objects.exists()


@pytest.mark.django_db
def test_create_rejects_inactive_resources() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    base = appointment_payload(
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )

    service.is_active = False
    service.save(update_fields=("is_active",))
    inactive_service = client.post("/api/v1/appointments", base, format="json")
    service.is_active = True
    service.save(update_fields=("is_active",))
    room.is_active = False
    room.save(update_fields=("is_active",))
    inactive_room = client.post("/api/v1/appointments", base, format="json")
    room.is_active = True
    room.save(update_fields=("is_active",))
    specialist.is_active = False
    specialist.save(update_fields=("is_active",))
    inactive_specialist = client.post("/api/v1/appointments", base, format="json")

    assert inactive_service.status_code == 422
    assert inactive_service.json()["code"] == "appointment_service_unavailable"
    assert inactive_room.status_code == 422
    assert inactive_room.json()["code"] == "appointment_room_unavailable"
    assert inactive_specialist.status_code == 422
    assert inactive_specialist.json()["code"] == "appointment_specialist_unavailable"
    assert not Appointment.objects.exists()


@pytest.mark.django_db
def test_create_maps_specialist_and_room_conflicts_without_losing_field_context() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    other_specialist = create_user(
        email="other@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Ірина",
    )
    other_room = Room.objects.create(name="Кабінет 2")
    client = authenticated_client(admin)
    created = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
        ),
        format="json",
    )
    specialist_conflict = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=other_room,
            patient=patient,
        ),
        format="json",
    )
    room_conflict = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=other_specialist,
            service=service,
            room=room,
            patient=patient,
        ),
        format="json",
    )

    assert created.status_code == 201
    assert specialist_conflict.status_code == 409
    assert specialist_conflict.json()["code"] == "appointment_slot_conflict"
    assert "starts_at" in specialist_conflict.json()["fields"]
    assert room_conflict.status_code == 409
    assert room_conflict.json()["code"] == "appointment_slot_conflict"
    assert "room_id" in room_conflict.json()["fields"]
    assert Appointment.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.APPOINTMENT_CREATED).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_posts_create_exactly_one_appointment_and_audit_event() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    payload = appointment_payload(
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    barrier = Barrier(2)

    def post_appointment(_: int) -> int:
        close_old_connections()
        actor = User.objects.get(pk=admin.pk)
        client = authenticated_client(actor)
        barrier.wait(timeout=5)
        try:
            return client.post("/api/v1/appointments", payload, format="json").status_code
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(post_appointment, range(2)))

    assert sorted(results) == [201, 409]
    assert Appointment.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.APPOINTMENT_CREATED).count() == 1
