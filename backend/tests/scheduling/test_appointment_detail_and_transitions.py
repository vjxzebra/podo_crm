from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections, connections
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import Room, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from tests.scheduling.test_create_appointment import (
    KYIV,
    appointment_payload,
    authenticated_client,
    create_user,
    scheduling_fixture,
)


def next_monday_at_ten() -> datetime:
    local_now = timezone.localtime()
    days_until_monday = 7 - local_now.weekday()
    return datetime.combine(
        (local_now + timedelta(days=days_until_monday)).date(),
        time(10, 0),
        tzinfo=KYIV,
    )


def create_appointment_response(
    *,
    actor: User,
    specialist: User,
    service: Service,
    room: Room,
    patient: Patient,
    starts_at: datetime | None = None,
) -> dict[str, object]:
    response = authenticated_client(actor).post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
            starts_at=starts_at,
        ),
        format="json",
    )
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.mark.django_db
def test_detail_is_role_scoped_and_describes_allowed_actions() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    other_specialist = create_user(
        email="other@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Ірина",
    )
    created = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
        starts_at=next_monday_at_ten(),
    )
    url = f"/api/v1/appointments/{created['id']}"

    admin_detail = authenticated_client(admin).get(url)
    own_detail = authenticated_client(specialist).get(url)
    hidden_detail = authenticated_client(other_specialist).get(url)

    assert admin_detail.status_code == 200
    assert [item["code"] for item in admin_detail.json()["allowed_status_transitions"]] == [
        "PENDING_CONFIRMATION",
        "CONFIRMED",
    ]
    assert admin_detail.json()["can_edit"] is True
    assert admin_detail.json()["can_reschedule"] is True
    assert admin_detail.json()["can_cancel"] is True
    assert own_detail.status_code == 200
    assert own_detail.json()["allowed_status_transitions"] == []
    assert own_detail.json()["can_cancel"] is False
    assert hidden_detail.status_code == 404


@pytest.mark.django_db
def test_patch_updates_content_once_and_rejects_stale_version_without_extra_audit() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    created = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    url = f"/api/v1/appointments/{created['id']}"
    client = authenticated_client(admin)

    updated = client.patch(
        url,
        {"version": created["version"], "comment": "  Просить нагадати за годину  "},
        format="json",
    )
    stale = client.patch(
        url,
        {"version": created["version"], "comment": "Втрачена зміна"},
        format="json",
    )

    assert updated.status_code == 200
    assert updated.json()["comment"] == "Просить нагадати за годину"
    assert updated.json()["version"] == int(created["version"]) + 1
    assert stale.status_code == 409
    assert stale.json()["code"] == "appointment_version_conflict"
    appointment = Appointment.objects.get(pk=created["id"])
    assert appointment.comment == "Просить нагадати за годину"
    events = AuditEvent.objects.filter(action=AuditAction.APPOINTMENT_UPDATED)
    assert events.count() == 1
    assert events.get().before["comment"] == "Перший візит"


@pytest.mark.django_db
def test_reschedule_recomputes_snapshots_duration_and_audit() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    created = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    follow_up = Service.objects.create(
        code="FOLLOW_UP",
        name="Повторна консультація",
        duration_minutes=60,
        price_minor=90000,
        color="#7C3AED",
    )
    room_two = Room.objects.create(name="Кабінет 2")

    response = authenticated_client(admin).patch(
        f"/api/v1/appointments/{created['id']}",
        {
            "version": created["version"],
            "service_id": str(follow_up.pk),
            "room_id": str(room_two.pk),
            "starts_at": datetime(2026, 7, 27, 14, 0, tzinfo=KYIV).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["starts_at"] == "2026-07-27T11:00:00Z"
    assert response.json()["ends_at"] == "2026-07-27T12:00:00Z"
    assert response.json()["duration_minutes"] == 60
    assert response.json()["service"]["name"] == "Повторна консультація"
    assert response.json()["service"]["color"] == "#7C3AED"
    assert response.json()["room"]["name"] == "Кабінет 2"
    event = AuditEvent.objects.get(action=AuditAction.APPOINTMENT_RESCHEDULED)
    assert event.before["starts_at"] == "2026-07-27T07:00:00+00:00"
    assert event.after["starts_at"] == "2026-07-27T11:00:00+00:00"


@pytest.mark.django_db
def test_conflicting_reschedule_rolls_back_appointment_and_audit() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    first = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
        starts_at=datetime(2026, 7, 27, 11, 0, tzinfo=KYIV),
    )

    response = authenticated_client(admin).patch(
        f"/api/v1/appointments/{first['id']}",
        {
            "version": first["version"],
            "starts_at": datetime(2026, 7, 27, 11, 0, tzinfo=KYIV).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "appointment_slot_conflict"
    appointment = Appointment.objects.get(pk=first["id"])
    assert appointment.starts_at == datetime(2026, 7, 27, 10, 0, tzinfo=KYIV).astimezone(
        appointment.starts_at.tzinfo
    )
    assert not AuditEvent.objects.filter(action=AuditAction.APPOINTMENT_RESCHEDULED).exists()


@pytest.mark.django_db
def test_status_transitions_increment_version_audit_and_block_invalid_reverse() -> None:
    specialist, service, room, patient = scheduling_fixture()
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    created = create_appointment_response(
        actor=reception,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    url = f"/api/v1/appointments/{created['id']}/status"
    client = authenticated_client(reception)

    confirmed = client.post(
        url,
        {"version": created["version"], "status_code": "CONFIRMED"},
        format="json",
    )
    arrived = client.post(
        url,
        {"version": confirmed.json()["version"], "status_code": "ARRIVED"},
        format="json",
    )
    reverse = client.post(
        url,
        {"version": arrived.json()["version"], "status_code": "CONFIRMED"},
        format="json",
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"]["code"] == "CONFIRMED"
    assert arrived.status_code == 200
    assert arrived.json()["status"]["code"] == "ARRIVED"
    assert reverse.status_code == 409
    assert reverse.json()["code"] == "appointment_status_transition_invalid"
    assert AuditEvent.objects.filter(action=AuditAction.APPOINTMENT_STATUS_CHANGED).count() == 2


@pytest.mark.django_db
def test_no_show_requires_past_start_and_terminal_record_is_locked() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    future = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
        starts_at=next_monday_at_ten(),
    )
    past = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
        starts_at=datetime(2026, 7, 20, 10, 0, tzinfo=KYIV),
    )
    client = authenticated_client(admin)

    too_early = client.post(
        f"/api/v1/appointments/{future['id']}/status",
        {"version": future["version"], "status_code": "NO_SHOW"},
        format="json",
    )
    no_show = client.post(
        f"/api/v1/appointments/{past['id']}/status",
        {"version": past["version"], "status_code": "NO_SHOW"},
        format="json",
    )
    locked = client.patch(
        f"/api/v1/appointments/{past['id']}",
        {"version": no_show.json()["version"], "comment": "Не можна"},
        format="json",
    )

    assert too_early.status_code == 409
    assert too_early.json()["code"] == "appointment_no_show_too_early"
    assert no_show.status_code == 200
    assert no_show.json()["status"]["code"] == "NO_SHOW"
    assert no_show.json()["can_edit"] is False
    assert locked.status_code == 409
    assert locked.json()["code"] == "appointment_terminal"


@pytest.mark.django_db
def test_podologist_cannot_apply_reception_status_or_cancel() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    created = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    client = authenticated_client(specialist)

    status_response = client.post(
        f"/api/v1/appointments/{created['id']}/status",
        {"version": created["version"], "status_code": "CONFIRMED"},
        format="json",
    )
    cancel_response = client.post(
        f"/api/v1/appointments/{created['id']}/cancel",
        {"version": created["version"], "reason": "Неактуально"},
        format="json",
    )

    assert status_response.status_code == 403
    assert status_response.json()["code"] == "appointment_status_forbidden"
    assert cancel_response.status_code == 403
    assert cancel_response.json()["code"] == "appointment_cancel_forbidden"


@pytest.mark.django_db
def test_cancel_requires_reason_and_releases_the_occupied_slot() -> None:
    specialist, service, room, patient = scheduling_fixture()
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    created = create_appointment_response(
        actor=reception,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    client = authenticated_client(reception)
    url = f"/api/v1/appointments/{created['id']}/cancel"

    missing_reason = client.post(
        url,
        {"version": created["version"], "reason": "  "},
        format="json",
    )
    canceled = client.post(
        url,
        {"version": created["version"], "reason": "Пацієнтка захворіла"},
        format="json",
    )
    replacement = client.post(
        "/api/v1/appointments",
        appointment_payload(
            specialist=specialist,
            service=service,
            room=room,
            patient=patient,
        ),
        format="json",
    )

    assert missing_reason.status_code == 422
    assert canceled.status_code == 200
    assert canceled.json()["status"]["code"] == "CANCELED"
    assert canceled.json()["cancellation_reason"] == "Пацієнтка захворіла"
    assert canceled.json()["can_cancel"] is False
    assert replacement.status_code == 201
    event = AuditEvent.objects.get(action=AuditAction.APPOINTMENT_CANCELED)
    assert event.after["cancellation_reason"] == "Пацієнтка захворіла"


@pytest.mark.django_db(transaction=True)
def test_concurrent_patches_accept_exactly_one_version_and_one_audit() -> None:
    specialist, service, room, patient = scheduling_fixture()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    created = create_appointment_response(
        actor=admin,
        specialist=specialist,
        service=service,
        room=room,
        patient=patient,
    )
    barrier = Barrier(2)

    def patch_appointment(index: int) -> int:
        close_old_connections()
        actor = User.objects.get(pk=admin.pk)
        client = authenticated_client(actor)
        barrier.wait(timeout=5)
        try:
            response = client.patch(
                f"/api/v1/appointments/{created['id']}",
                {"version": created["version"], "comment": f"Зміна {index}"},
                format="json",
            )
            return response.status_code
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(patch_appointment, range(2)))

    assert sorted(results) == [200, 409]
    assert Appointment.objects.get(pk=created["id"]).version == int(created["version"]) + 1
    assert AuditEvent.objects.filter(action=AuditAction.APPOINTMENT_UPDATED).count() == 1


@pytest.mark.django_db
def test_openapi_keeps_version_required_for_every_appointment_mutation() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    detail_path = schema["paths"]["/api/v1/appointments/{appointment_id}"]
    update_schema = detail_path["patch"]["requestBody"]["content"]["application/json"]["schema"]
    cancel_schema = schema["components"]["schemas"]["AppointmentCancelRequest"]
    status_schema = schema["components"]["schemas"]["AppointmentStatusTransitionRequest"]

    assert detail_path["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AppointmentDetailResponse"
    }
    assert update_schema["required"] == ["version"]
    assert update_schema["minProperties"] == 2
    assert set(cancel_schema["required"]) == {"reason", "version"}
    assert set(status_schema["required"]) == {"status_code", "version"}
