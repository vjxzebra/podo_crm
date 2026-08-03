from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connections
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import AppointmentStatusConfig, Service
from apps.inventory.models import InventoryOperation, StockMovement
from apps.scheduling.models import Appointment, AppointmentServiceLine
from apps.visits.models import DetectedCondition, Visit, VisitStatus
from tests.scheduling.test_create_appointment import (
    appointment_payload,
    authenticated_client,
    create_user,
    scheduling_fixture,
)


def arrived_appointment(*, actor: User) -> Appointment:
    specialist, service, room, patient = scheduling_fixture()
    arrived, _ = AppointmentStatusConfig.objects.update_or_create(
        code="ARRIVED",
        defaults={
            "label": "Пацієнт прийшов",
            "color": "#7C3AED",
            "manual_admin": True,
            "manual_reception": True,
            "manual_podologist": True,
        },
    )
    AppointmentStatusConfig.objects.update_or_create(
        code="IN_PROGRESS",
        defaults={
            "label": "Прийом триває",
            "color": "#0F766E",
            "manual_admin": True,
            "manual_reception": False,
            "manual_podologist": True,
        },
    )
    AppointmentStatusConfig.objects.update_or_create(
        code="COMPLETED",
        defaults={
            "label": "Завершено",
            "color": "#15803D",
            "manual_admin": False,
            "manual_reception": False,
            "manual_podologist": False,
        },
    )
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
    assert response.status_code == 201, response.json()
    appointment = Appointment.objects.get(pk=response.json()["id"])
    appointment.status = arrived
    appointment.version = 4
    appointment.save(update_fields=("status", "version", "updated_at"))
    return appointment


def start(client: APIClient, appointment: Appointment, *, version: int | None = None):
    return client.post(
        f"/api/v1/appointments/{appointment.pk}/start-visit",
        {"version": appointment.version if version is None else version},
        format="json",
    )


@pytest.mark.django_db
def test_assigned_podologist_starts_one_seeded_visit_idempotently() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    podologist = appointment.specialist
    client = authenticated_client(podologist)

    before = client.get(f"/api/v1/appointments/{appointment.pk}")
    first = start(client, appointment)
    replay = start(client, appointment)
    after = client.get(f"/api/v1/appointments/{appointment.pk}")

    assert before.status_code == 200
    assert before.json()["can_start_visit"] is True
    assert before.json()["visit_id"] is None
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert first.json()["complaints"] == appointment.complaints
    assert first.json()["has_no_complaints"] is False
    assert first.json()["status"] == VisitStatus.DRAFT
    assert first.json()["version"] == 1
    assert first.json()["appointment"]["status_code"] == "IN_PROGRESS"
    assert Visit.objects.count() == 1
    appointment.refresh_from_db()
    assert appointment.status_id == "IN_PROGRESS"
    assert appointment.version == 5
    assert after.json()["can_start_visit"] is False
    assert after.json()["visit_id"] == first.json()["id"]
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_STARTED).count() == 1
    assert InventoryOperation.objects.count() == 0
    assert StockMovement.objects.count() == 0


@pytest.mark.django_db
def test_start_visit_copies_every_appointment_service_into_the_draft() -> None:
    admin = create_user(email="admin-multi@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    additional = Service.objects.create(
        code="NAILS",
        name="Обробка нігтів",
        duration_minutes=30,
        price_minor=80000,
        color="#7C3AED",
    )
    AppointmentServiceLine.objects.create(
        appointment=appointment,
        service=additional,
        position=1,
        duration_minutes=additional.duration_minutes,
        service_name_snapshot=additional.name,
        service_color_snapshot=additional.color,
    )

    response = start(authenticated_client(admin), appointment)

    assert response.status_code == 201
    assert [line["service_id"] for line in response.json()["service_lines"]] == [
        str(appointment.service_id),
        str(additional.pk),
    ]
    assert response.json()["service_lines"][0]["is_primary"] is True
    assert response.json()["service_lines"][1]["is_primary"] is False


@pytest.mark.django_db
def test_start_rejects_stale_version_and_non_arrived_status_without_visit() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    client = authenticated_client(admin)

    stale = start(client, appointment, version=appointment.version - 1)
    appointment.status = AppointmentStatusConfig.objects.get(pk="CONFIRMED")
    appointment.save(update_fields=("status", "updated_at"))
    invalid_status = start(client, appointment)

    assert stale.status_code == 409
    assert stale.json()["code"] == "appointment_version_conflict"
    assert invalid_status.status_code == 409
    assert invalid_status.json()["code"] == "appointment_not_ready_for_visit"
    assert Visit.objects.count() == 0
    assert not AuditEvent.objects.filter(action=AuditAction.VISIT_STARTED).exists()


@pytest.mark.django_db
def test_start_and_visit_reads_enforce_medical_role_and_assignment_scope() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    appointment = arrived_appointment(actor=admin)

    reception_start = start(authenticated_client(reception), appointment)
    foreign_start = start(authenticated_client(foreign), appointment)
    created = start(authenticated_client(admin), appointment)
    visit_url = f"/api/v1/visits/{created.json()['id']}"

    assert reception_start.status_code == 403
    assert reception_start.json()["code"] == "visit_forbidden"
    assert foreign_start.status_code == 404
    assert authenticated_client(reception).get(visit_url).status_code == 403
    assert authenticated_client(foreign).get(visit_url).status_code == 404
    assert authenticated_client(appointment.specialist).get(visit_url).status_code == 200
    assert authenticated_client(admin).get(visit_url).status_code == 200


@pytest.mark.django_db
def test_draft_save_is_versioned_audited_and_has_no_posting_side_effects() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    started = start(authenticated_client(admin), appointment)
    visit_id = started.json()["id"]

    response = authenticated_client(admin).put(
        f"/api/v1/visits/{visit_id}",
        {
            "version": 1,
            "complaints": "  Дискомфорт під час ходьби  ",
            "has_no_complaints": False,
            "objective_examination": "  Локальний гіперкератоз правої стопи  ",
            "detected_conditions": [
                DetectedCondition.HYPERKERATOSIS,
                DetectedCondition.TENDERNESS,
            ],
            "podologist_notes": "  Рекомендовано зменшити навантаження  ",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["complaints"] == "Дискомфорт під час ходьби"
    assert response.json()["objective_examination"] == "Локальний гіперкератоз правої стопи"
    assert response.json()["detected_conditions"] == ["HYPERKERATOSIS", "TENDERNESS"]
    assert response.json()["podologist_notes"] == "Рекомендовано зменшити навантаження"
    appointment.refresh_from_db()
    assert appointment.status_id == "IN_PROGRESS"
    assert InventoryOperation.objects.count() == 0
    assert StockMovement.objects.count() == 0
    event = AuditEvent.objects.get(action=AuditAction.VISIT_DRAFT_SAVED)
    assert event.before["version"] == 1
    assert event.after["version"] == 2


@pytest.mark.django_db
def test_draft_validation_rejects_complaint_xor_duplicate_conditions_and_empty_patch() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    started = start(authenticated_client(admin), appointment)
    url = f"/api/v1/visits/{started.json()['id']}"
    client = authenticated_client(admin)

    complaints = client.put(
        url,
        {"version": 1, "complaints": "", "has_no_complaints": False},
        format="json",
    )
    duplicates = client.put(
        url,
        {
            "version": 1,
            "detected_conditions": [
                DetectedCondition.REDNESS,
                DetectedCondition.REDNESS,
            ],
        },
        format="json",
    )
    empty = client.put(url, {"version": 1}, format="json")

    assert complaints.status_code == 422
    assert complaints.json()["code"] == "complaints_required"
    assert duplicates.status_code == 422
    assert duplicates.json()["code"] == "visit_conditions_duplicate"
    assert empty.status_code == 422
    assert Visit.objects.get().version == 1
    assert not AuditEvent.objects.filter(action=AuditAction.VISIT_DRAFT_SAVED).exists()


@pytest.mark.django_db
def test_draft_rejects_stale_or_completed_visit() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    started = start(authenticated_client(admin), appointment)
    url = f"/api/v1/visits/{started.json()['id']}"
    client = authenticated_client(admin)

    saved = client.put(url, {"version": 1, "podologist_notes": "Перша версія"}, format="json")
    stale = client.put(url, {"version": 1, "podologist_notes": "Втрачена зміна"}, format="json")
    visit = Visit.objects.get()
    visit.status = VisitStatus.COMPLETED
    visit.save(update_fields=("status", "updated_at"))
    completed = client.put(
        url,
        {"version": saved.json()["version"], "podologist_notes": "Не можна"},
        format="json",
    )

    assert saved.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "visit_version_conflict"
    assert completed.status_code == 409
    assert completed.json()["code"] == "visit_not_editable"
    assert Visit.objects.get().podologist_notes == "Перша версія"


@pytest.mark.django_db
def test_draft_rolls_back_when_audit_write_fails() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    started = start(authenticated_client(admin), appointment)
    visit = Visit.objects.get(pk=started.json()["id"])

    with patch("apps.visits.services.record_audit_event", side_effect=RuntimeError("audit down")):
        response = authenticated_client(admin).put(
            f"/api/v1/visits/{visit.pk}",
            {"version": 1, "objective_examination": "Не має зберегтися"},
            format="json",
        )

    assert response.status_code == 500
    visit.refresh_from_db()
    assert visit.objective_examination == ""
    assert visit.version == 1
    assert not AuditEvent.objects.filter(action=AuditAction.VISIT_DRAFT_SAVED).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_start_creates_exactly_one_visit_and_one_audit() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=admin)
    barrier = Barrier(2)

    def post_start() -> tuple[int, str]:
        close_old_connections()
        actor = User.objects.get(pk=admin.pk)
        barrier.wait(timeout=5)
        try:
            response = start(authenticated_client(actor), appointment, version=4)
            return response.status_code, response.json()["id"]
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: post_start(), range(2)))

    assert sorted(code for code, _ in results) == [200, 201]
    assert len({visit_id for _, visit_id in results}) == 1
    assert Visit.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_STARTED).count() == 1


@pytest.mark.django_db
def test_openapi_exposes_versioned_visit_contracts() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    start_operation = schema["paths"]["/api/v1/appointments/{appointment_id}/start-visit"]["post"]
    visit_path = schema["paths"]["/api/v1/visits/{visit_id}"]
    start_schema = schema["components"]["schemas"]["StartVisitRequest"]
    draft_schema = schema["components"]["schemas"]["VisitDraftUpdateRequest"]

    assert start_operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisitResponse"
    }
    assert visit_path["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisitResponse"
    }
    assert start_schema["required"] == ["version"]
    assert "version" in draft_schema["required"]
