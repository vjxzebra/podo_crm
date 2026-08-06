from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from drf_spectacular.generators import SchemaGenerator
from psycopg.types.range import Range
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import AppointmentStatusConfig, Room, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.visits.models import (
    Visit,
    VisitPhoto,
    VisitPhotoKind,
    VisitPhotoPreviewStatus,
    VisitRecommendation,
    VisitServiceLine,
    VisitStatus,
)
from tests.financial_fixtures import complete_visit_with_neutral_pricing

KYIV = ZoneInfo("Europe/Kyiv")
PASSWORD = "test-only-password-placeholder"  # noqa: S105


def _user(*, email: str, role: str, first_name: str) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name=first_name,
        last_name="Працівник",
    )


def _client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _domain() -> tuple[User, User, User, User, Patient, Service, Room]:
    admin = _user(email="admin@example.test", role=UserRole.ADMIN, first_name="Адмін")
    reception = _user(email="reception@example.test", role=UserRole.RECEPTION, first_name="Ресепшн")
    podologist = _user(
        email="podologist@example.test", role=UserRole.PODOLOGIST, first_name="Олена"
    )
    foreign = _user(email="foreign@example.test", role=UserRole.PODOLOGIST, first_name="Ірина")
    patient = Patient.objects.create(
        first_name="Марія",
        last_name="Бондар",
        phone="0671234567",
        primary_podologist=podologist,
        created_by=admin,
    )
    service = Service.objects.create(
        code="HISTORY",
        name="Медичний педикюр",
        duration_minutes=45,
        price_minor=150000,
        color="#0F766E",
    )
    room = Room.objects.create(name="Кабінет історії")
    for code, label in (("IN_PROGRESS", "Прийом триває"), ("COMPLETED", "Завершено")):
        AppointmentStatusConfig.objects.update_or_create(
            code=code,
            defaults={
                "label": label,
                "color": "#15803D",
                "manual_admin": True,
                "manual_reception": False,
                "manual_podologist": True,
            },
        )
    return admin, reception, podologist, foreign, patient, service, room


def _visit(
    *,
    day: int,
    patient: Patient,
    specialist: User,
    service: Service,
    room: Room,
    status: str = VisitStatus.COMPLETED,
    complete_fields: bool = True,
) -> Visit:
    starts_at = datetime(2026, 7, day, 10, 0, tzinfo=KYIV)
    persisted_status = status if complete_fields else VisitStatus.DRAFT
    appointment_status = "COMPLETED" if persisted_status == VisitStatus.COMPLETED else "IN_PROGRESS"
    appointment = Appointment.objects.create(
        patient=patient,
        specialist=specialist,
        service=service,
        room=room,
        time_range=Range(starts_at, starts_at + timedelta(minutes=45), bounds="[)"),
        duration_minutes=45,
        service_name_snapshot=service.name,
        service_color_snapshot=service.color,
        room_label_snapshot=room.name,
        status=AppointmentStatusConfig.objects.get(pk=appointment_status),
        complaints="Біль під час ходьби",
        has_no_complaints=False,
        version=5,
    )
    visit = Visit.objects.create(
        appointment=appointment,
        patient=patient,
        specialist=specialist,
        status=VisitStatus.DRAFT,
        complaints=appointment.complaints,
        objective_examination="Локальний гіперкератоз.",
        podologist_notes=f"Клінічний підсумок {day}.",
        total_minor=None,
        payment_handoff_requested=False,
        version=2,
        started_by=specialist,
        completed_at=None,
    )
    VisitServiceLine.objects.create(
        visit=visit,
        service=service,
        service_code=service.code,
        service_name=f"Snapshot {day}",
        duration_minutes=service.duration_minutes,
        price_minor=service.price_minor,
        quantity=1,
        is_primary=True,
    )
    if persisted_status == VisitStatus.COMPLETED:
        complete_visit_with_neutral_pricing(
            visit,
            completed_at=starts_at + timedelta(minutes=50),
            payment_handoff_requested=True,
        )
    return visit


def _photo(
    *,
    visit: Visit,
    actor: User,
    kind: str,
    suffix: str,
    preview_status: str = VisitPhotoPreviewStatus.READY,
) -> VisitPhoto:
    return VisitPhoto.objects.create(
        visit=visit,
        kind=kind,
        object_key=f"patients/history/{suffix}.jpg",
        content_type="image/jpeg",
        size=2048,
        width=1200,
        height=900,
        original_name=f"private-{suffix}.jpg",
        preview_object_key=(
            f"patients/history/{suffix}-preview.jpg"
            if preview_status == VisitPhotoPreviewStatus.READY
            else ""
        ),
        preview_content_type=(
            "image/jpeg" if preview_status == VisitPhotoPreviewStatus.READY else ""
        ),
        preview_status=preview_status,
        created_by=actor,
    )


@pytest.mark.django_db
def test_admin_history_is_completed_snapshot_newest_first_and_populates_card_preview() -> None:
    admin, _, podologist, _, patient, service, room = _domain()
    older = _visit(
        day=20,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
    )
    recent = _visit(
        day=22,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
    )
    _visit(
        day=23,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
        status=VisitStatus.DRAFT,
    )
    _visit(
        day=24,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
        complete_fields=False,
    )
    _photo(visit=recent, actor=podologist, kind=VisitPhotoKind.BEFORE, suffix="before")
    VisitRecommendation.objects.create(
        visit=recent,
        author=podologist,
        text="Домашній догляд.",
    )

    history = _client(admin).get(f"/api/v1/patients/{patient.pk}/visits")
    detail = _client(admin).get(f"/api/v1/patients/{patient.pk}")

    assert history.status_code == 200
    assert [row["id"] for row in history.json()["visits"]] == [str(recent.pk), str(older.pk)]
    first = history.json()["visits"][0]
    assert first["services"] == [
        {"service_name": "Snapshot 22", "quantity": 1, "line_total_minor": 150000}
    ]
    assert first["specialist"]["display_name"] == podologist.display_name
    assert first["clinical_summary"] == "Клінічний підсумок 22."
    assert first["total_minor"] == 150000
    assert first["has_photos"] is True
    assert first["before_photo_count"] == 1
    assert first["after_photo_count"] == 0
    assert first["recommendations_count"] == 1
    assert detail.status_code == 200
    assert [row["id"] for row in detail.json()["visit_history"]] == [
        str(recent.pk),
        str(older.pk),
    ]
    assert detail.json()["photo_archive"][0]["visit_id"] == str(recent.pk)


@pytest.mark.django_db
def test_reception_history_physically_omits_medical_photo_and_recommendation_data() -> None:
    _, reception, podologist, _, patient, service, room = _domain()
    visit = _visit(
        day=21,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
    )
    _photo(visit=visit, actor=podologist, kind=VisitPhotoKind.AFTER, suffix="secret-photo")
    recommendation = VisitRecommendation.objects.create(
        visit=visit,
        author=podologist,
        text="Секретна медична рекомендація.",
    )
    client = _client(reception)

    history = client.get(f"/api/v1/patients/{patient.pk}/visits")
    detail = client.get(f"/api/v1/patients/{patient.pk}")
    photos = client.get(f"/api/v1/patients/{patient.pk}/photos")
    recommendations = client.get(f"/api/v1/patients/{patient.pk}/recommendations")
    recommendation_create = client.post(
        f"/api/v1/visits/{visit.pk}/recommendations",
        {"text": "Недозволена рекомендація."},
        format="json",
    )
    recommendation_detail = client.get(
        f"/api/v1/visits/{visit.pk}/recommendations/{recommendation.pk}"
    )

    assert history.status_code == 200
    row = history.json()["visits"][0]
    forbidden = {
        "clinical_summary",
        "has_photos",
        "before_photo_count",
        "after_photo_count",
        "recommendations_count",
        "photos",
        "recommendations",
    }
    assert forbidden.isdisjoint(row)
    assert forbidden.isdisjoint(detail.json()["visit_history"][0])
    serialized = str(history.json()) + str(detail.json())
    assert "Секретна" not in serialized
    assert "secret-photo" not in serialized
    assert photos.status_code == 403
    assert recommendations.status_code == 403
    assert recommendation_create.status_code == 403
    assert recommendation_detail.status_code == 403


@pytest.mark.django_db
def test_podologist_reads_only_own_completed_visits_and_foreign_patient_is_not_found() -> None:
    admin, _, podologist, foreign, patient, service, room = _domain()
    own = _visit(
        day=20,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
    )
    foreign_visit = _visit(
        day=21,
        patient=patient,
        specialist=foreign,
        service=service,
        room=room,
    )
    _photo(visit=own, actor=podologist, kind=VisitPhotoKind.BEFORE, suffix="own")
    _photo(visit=foreign_visit, actor=foreign, kind=VisitPhotoKind.AFTER, suffix="foreign")
    VisitRecommendation.objects.create(visit=own, author=podologist, text="Власна.")
    VisitRecommendation.objects.create(visit=foreign_visit, author=foreign, text="Чужа.")
    client = _client(podologist)

    history = client.get(f"/api/v1/patients/{patient.pk}/visits")
    photos = client.get(f"/api/v1/patients/{patient.pk}/photos")
    recommendations = client.get(f"/api/v1/patients/{patient.pk}/recommendations")
    foreign_create = client.post(
        f"/api/v1/visits/{foreign_visit.pk}/recommendations",
        {"text": "Спроба"},
        format="json",
    )
    hidden_patient = Patient.objects.create(
        first_name="Чужа",
        last_name="Пацієнтка",
        phone="0501112233",
        primary_podologist=foreign,
        created_by=admin,
    )

    assert [row["id"] for row in history.json()["visits"]] == [str(own.pk)]
    assert [row["id"] for row in photos.json()["visits"]] == [str(own.pk)]
    assert [row["text"] for row in recommendations.json()["recommendations"]] == ["Власна."]
    assert foreign_create.status_code == 404
    assert client.get(f"/api/v1/patients/{hidden_patient.pk}/visits").status_code == 404
    assert client.get(f"/api/v1/patients/{hidden_patient.pk}/photos").status_code == 404


@pytest.mark.django_db
def test_photo_archive_groups_completed_photos_with_fresh_private_urls_and_no_object_keys() -> None:
    admin, _, podologist, _, patient, service, room = _domain()
    completed = _visit(
        day=20,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
    )
    draft = _visit(
        day=21,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
        status=VisitStatus.DRAFT,
    )
    _photo(visit=completed, actor=podologist, kind=VisitPhotoKind.BEFORE, suffix="ready")
    _photo(
        visit=completed,
        actor=podologist,
        kind=VisitPhotoKind.AFTER,
        suffix="failed-preview",
        preview_status=VisitPhotoPreviewStatus.FAILED,
    )
    _photo(visit=draft, actor=podologist, kind=VisitPhotoKind.BEFORE, suffix="draft")

    response = _client(admin).get(f"/api/v1/patients/{patient.pk}/photos")

    assert response.status_code == 200
    assert len(response.json()["visits"]) == 1
    photos = response.json()["visits"][0]["photos"]
    assert [photo["kind"] for photo in photos] == ["BEFORE", "AFTER"]
    assert photos[0]["preview_url"].startswith("/api/v1/visit-photo-content?token=")
    assert photos[1]["preview_url"] is None
    assert photos[1]["image_url"].startswith("/api/v1/visit-photo-content?token=")
    assert "object_key" not in str(response.json())
    assert "patients/history" not in str(response.json())


@pytest.mark.django_db
def test_recommendation_create_update_version_scope_and_audit() -> None:
    admin, _, podologist, foreign, patient, service, room = _domain()
    visit = _visit(
        day=20,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
    )
    other_visit = _visit(
        day=21,
        patient=patient,
        specialist=foreign,
        service=service,
        room=room,
    )
    client = _client(podologist)

    created = client.post(
        f"/api/v1/visits/{visit.pk}/recommendations",
        {"text": "  Щоденний догляд.  "},
        format="json",
    )
    recommendation_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/visits/{visit.pk}/recommendations/{recommendation_id}",
        {"version": 1, "text": "Оновлений догляд."},
        format="json",
    )
    stale = client.patch(
        f"/api/v1/visits/{visit.pk}/recommendations/{recommendation_id}",
        {"version": 1, "text": "Застаріла зміна."},
        format="json",
    )
    refreshed = client.get(f"/api/v1/visits/{visit.pk}/recommendations/{recommendation_id}")
    mismatch = _client(admin).patch(
        f"/api/v1/visits/{other_visit.pk}/recommendations/{recommendation_id}",
        {"version": 2, "text": "Інший visit."},
        format="json",
    )
    blank = client.post(
        f"/api/v1/visits/{visit.pk}/recommendations",
        {"text": "   "},
        format="json",
    )
    inconsistent = _visit(
        day=22,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
        complete_fields=False,
    )
    incomplete = client.post(
        f"/api/v1/visits/{inconsistent.pk}/recommendations",
        {"text": "Не для неповного legacy visit."},
        format="json",
    )

    assert created.status_code == 201
    assert created.json()["text"] == "Щоденний догляд."
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["author_id"] == podologist.pk
    assert stale.status_code == 409
    assert stale.json()["code"] == "recommendation_version_conflict"
    assert refreshed.status_code == 200
    assert refreshed.json()["version"] == 2
    assert refreshed.json()["text"] == "Оновлений догляд."
    assert mismatch.status_code == 404
    assert blank.status_code == 422
    assert incomplete.status_code == 409
    assert incomplete.json()["code"] == "recommendation_visit_not_completed"
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_RECOMMENDATION_CREATED).count() == 1
    event = AuditEvent.objects.get(action=AuditAction.VISIT_RECOMMENDATION_UPDATED)
    assert event.before["text"] == "Щоденний догляд."
    assert event.after["text"] == "Оновлений догляд."


@pytest.mark.django_db
def test_recommendation_audit_failure_rolls_back_create() -> None:
    admin, _, podologist, _, patient, service, room = _domain()
    visit = _visit(
        day=20,
        patient=patient,
        specialist=podologist,
        service=service,
        room=room,
    )

    with patch(
        "apps.visits.recommendation_services.record_audit_event",
        side_effect=RuntimeError("audit unavailable"),
    ):
        response = _client(admin).post(
            f"/api/v1/visits/{visit.pk}/recommendations",
            {"text": "Не має зберегтися."},
            format="json",
        )

    assert response.status_code == 500
    assert not VisitRecommendation.objects.exists()


@pytest.mark.django_db
def test_history_cursor_paginates_without_duplicates() -> None:
    admin, _, podologist, _, patient, service, room = _domain()
    visits = [
        _visit(
            day=day,
            patient=patient,
            specialist=podologist,
            service=service,
            room=room,
        )
        for day in range(1, 22)
    ]

    first = _client(admin).get(f"/api/v1/patients/{patient.pk}/visits")
    cursor = first.json()["next_cursor"]
    second = _client(admin).get(
        f"/api/v1/patients/{patient.pk}/visits",
        {"cursor": cursor},
    )

    first_ids = [row["id"] for row in first.json()["visits"]]
    second_ids = [row["id"] for row in second.json()["visits"]]
    assert first.status_code == 200
    assert len(first_ids) == 20
    assert cursor
    assert second.status_code == 200
    assert second_ids == [str(visits[0].pk)]
    assert set(first_ids).isdisjoint(second_ids)
    assert second.json()["next_cursor"] is None


@pytest.mark.django_db
def test_tp605_openapi_paths_and_safe_history_schema() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)

    archive_paths = (
        "/api/v1/patients/{patient_id}/visits",
        "/api/v1/patients/{patient_id}/photos",
        "/api/v1/patients/{patient_id}/recommendations",
    )
    for path in archive_paths:
        assert path in schema["paths"]
        query_parameters = schema["paths"][path]["get"]["parameters"]
        assert any(parameter["name"] == "cursor" for parameter in query_parameters)
    assert "/api/v1/visits/{visit_id}/recommendations" in schema["paths"]
    recommendation_detail = schema["paths"][
        "/api/v1/visits/{visit_id}/recommendations/{recommendation_id}"
    ]
    assert {"get", "patch"}.issubset(recommendation_detail)
    safe_properties = schema["components"]["schemas"]["PatientHistoryBaseItem"]["properties"]
    assert {
        "clinical_summary",
        "has_photos",
        "before_photo_count",
        "after_photo_count",
        "recommendations_count",
    }.isdisjoint(safe_properties)
