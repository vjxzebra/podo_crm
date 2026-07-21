from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.patients.models import Patient, PatientMedicalProfile

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="Тест",
        last_name=role,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_patient(
    *,
    primary_podologist: User | None = None,
    allergies: list[str] | None = None,
) -> Patient:
    patient = Patient.objects.create(
        first_name="Марія",
        last_name="Бондар",
        phone="067 123 45 67",
        birth_date=date(1991, 6, 14),
        email="maria@example.test",
        note="Телефонувати після 16:00.",
        primary_podologist=primary_podologist,
    )
    PatientMedicalProfile.objects.create(
        patient=patient,
        allergies=allergies or ["Латекс"],
        chronic_conditions=["Цукровий діабет"],
        notes="Чутливість нігтьової пластини.",
    )
    return patient


@pytest.mark.django_db
def test_admin_retrieves_medical_patient_projection_and_empty_domain_shells() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    patient = create_patient()

    response = authenticated_client(admin).get(f"/api/v1/patients/{patient.pk}")

    assert response.status_code == 200
    body = response.json()
    assert body["projection"] == "medical"
    assert body["medical_profile"]["allergies"] == ["Латекс"]
    assert body["medical_profile"]["chronic_conditions"] == ["Цукровий діабет"]
    assert body["photo_archive"] == []
    assert body["visit_history"] == []
    assert body["upcoming_appointment"] is None
    assert body["service_started_at"] == body["created_at"]
    assert isinstance(body["age"], int)


@pytest.mark.django_db
def test_reception_projection_omits_medical_and_photo_keys_and_values() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    patient = create_patient()

    response = authenticated_client(reception).get(f"/api/v1/patients/{patient.pk}")

    assert response.status_code == 200
    body = response.json()
    assert body["projection"] == "reception"
    forbidden_keys = {
        "medical_profile",
        "photo_archive",
        "allergies",
        "chronic_conditions",
        "medical_notes",
    }
    assert forbidden_keys.isdisjoint(body)
    assert "Латекс" not in str(body)
    assert body["visit_history"] == []


@pytest.mark.django_db
def test_reception_updates_safe_contacts_but_response_and_audit_stay_role_safe() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    patient = create_patient()

    response = authenticated_client(reception).patch(
        f"/api/v1/patients/{patient.pk}",
        {"phone": "050 111 22 33", "email": " NEW@example.test ", "note": " Нова нотатка "},
        format="json",
    )

    assert response.status_code == 200
    assert "medical_profile" not in response.json()
    patient.refresh_from_db()
    assert patient.normalized_phone == "+380501112233"
    assert patient.email == "new@example.test"
    assert patient.note == "Нова нотатка"
    event = AuditEvent.objects.get(action=AuditAction.PATIENT_UPDATED)
    assert event.before["phone"] == "067 123 45 67"
    assert event.after["phone"] == "050 111 22 33"
    assert "medical_profile" not in event.before
    assert "medical_profile" not in event.after


@pytest.mark.django_db
def test_reception_cannot_submit_medical_profile_changes() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    patient = create_patient()

    response = authenticated_client(reception).patch(
        f"/api/v1/patients/{patient.pk}",
        {"medical_profile": {"allergies": ["Інше"]}},
        format="json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "patient_medical_access_denied"
    assert patient.medical_profile.allergies == ["Латекс"]
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_podologist_foreign_patient_id_is_not_found_for_get_and_patch() -> None:
    owner = create_user(email="owner@example.test", role=UserRole.PODOLOGIST)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    patient = create_patient(primary_podologist=foreign)
    client = authenticated_client(owner)

    retrieved = client.get(f"/api/v1/patients/{patient.pk}")
    updated = client.patch(
        f"/api/v1/patients/{patient.pk}",
        {"medical_profile": {"notes": "Спроба доступу"}},
        format="json",
    )

    assert retrieved.status_code == 404
    assert updated.status_code == 404
    assert retrieved.json()["code"] == updated.json()["code"] == "not_found"
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_podologist_updates_own_medical_profile_and_cannot_unassign_patient() -> None:
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    patient = create_patient(primary_podologist=podologist)
    client = authenticated_client(podologist)

    updated = client.patch(
        f"/api/v1/patients/{patient.pk}",
        {
            "medical_profile": {
                "allergies": [" Латекс ", "латекс", "Йод"],
                "chronic_conditions": [],
                "notes": "  Контроль через місяць.  ",
            }
        },
        format="json",
    )
    unassigned = client.patch(
        f"/api/v1/patients/{patient.pk}",
        {"primary_podologist_id": None},
        format="json",
    )

    assert updated.status_code == 200
    assert updated.json()["medical_profile"]["allergies"] == ["Латекс", "Йод"]
    assert updated.json()["medical_profile"]["notes"] == "Контроль через місяць."
    assert unassigned.status_code == 422
    assert unassigned.json()["code"] == "patient_podologist_scope_violation"
    patient.refresh_from_db()
    assert patient.primary_podologist == podologist
    assert AuditEvent.objects.filter(action=AuditAction.PATIENT_UPDATED).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"phone": "123"}, "phone"),
        ({"birth_date": (date.today() + timedelta(days=1)).isoformat()}, "birth_date"),
        ({"first_name": "  "}, "first_name"),
    ],
)
def test_patient_patch_rejects_invalid_safe_fields(payload: dict[str, object], field: str) -> None:
    admin = create_user(email=f"{field}@example.test", role=UserRole.ADMIN)
    patient = create_patient()

    response = authenticated_client(admin).patch(
        f"/api/v1/patients/{patient.pk}", payload, format="json"
    )

    assert response.status_code == 422
    assert field in response.json()["fields"]
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_detail_endpoints_require_authentication_and_create_builds_medical_profile() -> None:
    anonymous = APIClient()
    patient = create_patient()
    assert anonymous.get(f"/api/v1/patients/{patient.pk}").status_code == 401
    assert anonymous.patch(f"/api/v1/patients/{patient.pk}", {}, format="json").status_code == 401

    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    created = authenticated_client(admin).post(
        "/api/v1/patients",
        {
            "first_name": "Олена",
            "last_name": "Коваль",
            "phone": "067 555 44 33",
        },
        format="json",
    )

    assert created.status_code == 201
    assert PatientMedicalProfile.objects.filter(patient_id=created.json()["patient"]["id"]).exists()
