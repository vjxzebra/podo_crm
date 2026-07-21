from datetime import time

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import (
    AppointmentStatusConfig,
    ClinicBreak,
    ClinicWorkday,
    SystemStatusProtectedError,
)

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def schedule_payload() -> dict[str, list[dict[str, object]]]:
    return {
        "workdays": [
            {
                "weekday": item.weekday,
                "is_working": item.is_working,
                "start_time": item.start_time.strftime("%H:%M") if item.start_time else None,
                "end_time": item.end_time.strftime("%H:%M") if item.end_time else None,
                "breaks": [
                    {
                        "start_time": schedule_break.start_time.strftime("%H:%M"),
                        "end_time": schedule_break.end_time.strftime("%H:%M"),
                    }
                    for schedule_break in item.breaks.all()
                ],
                "version": item.version,
            }
            for item in ClinicWorkday.objects.prefetch_related("breaks").order_by("weekday")
        ]
    }


@pytest.mark.django_db
def test_migration_seeds_exactly_eight_system_statuses_and_weekly_schedule():
    assert list(AppointmentStatusConfig.objects.values_list("code", flat=True)) == [
        "ARRIVED",
        "CANCELED",
        "COMPLETED",
        "CONFIRMED",
        "IN_PROGRESS",
        "NEW",
        "NO_SHOW",
        "PENDING_CONFIRMATION",
    ]
    assert ClinicWorkday.objects.count() == 7
    assert ClinicWorkday.objects.filter(is_working=True).count() == 5
    assert ClinicBreak.objects.count() == 5
    assert all(item.workday_id < 5 for item in ClinicBreak.objects.all())


@pytest.mark.django_db
def test_admin_updates_status_presentation_and_manual_role_flags_with_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    status_config = AppointmentStatusConfig.objects.get(code="ARRIVED")
    client = authenticated_client(admin)

    listed = client.get("/api/v1/appointment-status-configs")
    updated = client.patch(
        "/api/v1/appointment-status-configs/arrived",
        {
            "label": "У клініці",
            "color": "#a855f7",
            "manual_admin": True,
            "manual_reception": False,
            "manual_podologist": True,
            "version": status_config.version,
        },
        format="json",
    )

    assert listed.status_code == 200
    assert len(listed.json()["statuses"]) == 8
    assert updated.status_code == 200
    assert updated.json()["code"] == "ARRIVED"
    assert updated.json()["label"] == "У клініці"
    assert updated.json()["color"] == "#A855F7"
    assert updated.json()["manual_reception"] is False
    event = AuditEvent.objects.get(action=AuditAction.APPOINTMENT_STATUS_CONFIG_UPDATED)
    assert event.before["code"] == "ARRIVED"
    assert event.after["label"] == "У клініці"


@pytest.mark.django_db
def test_status_code_is_not_writable_or_deletable_and_stale_updates_are_rejected():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    status_config = AppointmentStatusConfig.objects.get(code="NEW")
    client = authenticated_client(admin)

    current = client.patch(
        "/api/v1/appointment-status-configs/NEW",
        {"label": "Новий запис", "version": status_config.version},
        format="json",
    )
    stale = client.patch(
        "/api/v1/appointment-status-configs/NEW",
        {"label": "Втрачена зміна", "version": status_config.version},
        format="json",
    )
    deleted = client.delete("/api/v1/appointment-status-configs/NEW")

    assert current.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"
    assert deleted.status_code == 405
    with pytest.raises(SystemStatusProtectedError):
        status_config.delete()
    with pytest.raises(SystemStatusProtectedError):
        AppointmentStatusConfig.objects.filter(code="NEW").update(code="RENAMED")


@pytest.mark.django_db
def test_database_trigger_protects_system_status_code_and_row():
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE clinic_appointmentstatusconfig SET code = %s WHERE code = %s",
            ["RENAMED", "NEW"],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM clinic_appointmentstatusconfig WHERE code = %s", ["NEW"])
    assert AppointmentStatusConfig.objects.filter(code="NEW").exists()


@pytest.mark.django_db
def test_admin_atomically_updates_clinic_wide_schedule_and_breaks_with_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    payload = schedule_payload()
    monday = payload["workdays"][0]
    monday["start_time"] = "08:30"
    monday["end_time"] = "19:00"
    monday["breaks"] = [
        {"start_time": "12:00", "end_time": "12:30"},
        {"start_time": "15:30", "end_time": "16:00"},
    ]

    retrieved = client.get("/api/v1/clinic-workdays")
    updated = client.put("/api/v1/clinic-workdays", payload, format="json")

    assert retrieved.status_code == 200
    assert retrieved.json()["timezone"] == "Europe/Kyiv"
    assert len(retrieved.json()["workdays"]) == 7
    assert updated.status_code == 200
    assert updated.json()["workdays"][0]["start_time"] == "08:30"
    assert updated.json()["workdays"][0]["breaks"] == [
        {
            "id": updated.json()["workdays"][0]["breaks"][0]["id"],
            "start_time": "12:00",
            "end_time": "12:30",
        },
        {
            "id": updated.json()["workdays"][0]["breaks"][1]["id"],
            "start_time": "15:30",
            "end_time": "16:00",
        },
    ]
    event = AuditEvent.objects.get(action=AuditAction.CLINIC_SCHEDULE_UPDATED)
    assert event.before["timezone"] == "Europe/Kyiv"
    assert event.after["workdays"][0]["breaks"][1]["start_time"] == "15:30"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "breaks",
    [
        [{"start_time": "08:30", "end_time": "09:30"}],
        [
            {"start_time": "10:00", "end_time": "11:00"},
            {"start_time": "10:30", "end_time": "11:30"},
        ],
        [{"start_time": "12:00", "end_time": "12:00"}],
    ],
)
def test_invalid_break_ranges_rollback_the_entire_schedule(breaks: list[dict[str, str]]):
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    payload = schedule_payload()
    payload["workdays"][0]["breaks"] = breaks

    response = authenticated_client(admin).put("/api/v1/clinic-workdays", payload, format="json")

    assert response.status_code == 422
    monday = ClinicWorkday.objects.get(weekday=0)
    assert monday.start_time == time(9, 0)
    assert list(monday.breaks.values_list("start_time", "end_time")) == [(time(13, 0), time(14, 0))]
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_stale_schedule_version_rejects_every_change():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    payload = schedule_payload()
    ClinicWorkday.objects.filter(weekday=3).update(version=2)
    payload["workdays"][0]["start_time"] = "08:00"

    response = authenticated_client(admin).put("/api/v1/clinic-workdays", payload, format="json")

    assert response.status_code == 409
    assert response.json()["code"] == "stale_version"
    assert ClinicWorkday.objects.get(weekday=0).start_time == time(9, 0)
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_database_enforces_workday_and_break_time_ranges():
    with pytest.raises(IntegrityError), transaction.atomic():
        ClinicWorkday.objects.create(
            weekday=8,
            is_working=True,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
    monday = ClinicWorkday.objects.get(weekday=0)
    with pytest.raises(IntegrityError), transaction.atomic():
        ClinicBreak.objects.create(
            workday=monday,
            start_time=time(14, 0),
            end_time=time(13, 0),
        )


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.PODOLOGIST, UserRole.RECEPTION])
def test_non_admin_cannot_read_or_mutate_status_and_schedule_settings(role: str):
    user = create_user(email=f"{role}@example.test", role=role)
    client = authenticated_client(user)
    status_config = AppointmentStatusConfig.objects.get(code="NEW")

    assert client.get("/api/v1/appointment-status-configs").status_code == 403
    assert (
        client.patch(
            "/api/v1/appointment-status-configs/NEW",
            {"label": "Nope", "version": status_config.version},
            format="json",
        ).status_code
        == 403
    )
    assert client.get("/api/v1/clinic-workdays").status_code == 403
    assert (
        client.put("/api/v1/clinic-workdays", schedule_payload(), format="json").status_code == 403
    )


@pytest.mark.django_db
def test_status_and_schedule_endpoints_require_authentication():
    client = APIClient()

    assert client.get("/api/v1/appointment-status-configs").status_code == 401
    assert client.get("/api/v1/clinic-workdays").status_code == 401
