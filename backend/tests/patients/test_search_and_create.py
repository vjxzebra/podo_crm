from datetime import date, timedelta
from uuid import UUID

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.patients.models import Patient
from apps.patients.normalization import InvalidPhoneError, normalize_phone

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str, first_name: str = "Тест") -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name=first_name,
        last_name=role,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_patient(
    *,
    first_name: str,
    phone: str,
    primary_podologist: User | None = None,
    last_name: str = "Пацієнт",
) -> Patient:
    return Patient.objects.create(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        primary_podologist=primary_podologist,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("067 123 45 67", "+380671234567"),
        ("+38 (067) 123-45-67", "+380671234567"),
        ("380671234567", "+380671234567"),
        ("00442079460018", "+442079460018"),
    ],
)
def test_normalize_phone_accepts_local_and_international_formats(raw: str, expected: str):
    assert normalize_phone(raw) == expected


def test_normalize_phone_rejects_invalid_length():
    with pytest.raises(InvalidPhoneError):
        normalize_phone("123")


@pytest.mark.django_db
def test_admin_searches_by_name_full_name_phone_and_public_number():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    maria = Patient.objects.create(
        id=UUID("12345678-90ab-cdef-1234-567890abcdef"),
        first_name="Марія",
        last_name="Бондар",
        phone="067 111 22 33",
    )
    # The digits embedded in Maria's public number are also present in this
    # phone. A full public-number query must still resolve only the exact card.
    create_patient(first_name="Ірина", last_name="Савчук", phone="+12345678901")
    client = authenticated_client(admin)

    by_full_name = client.get("/api/v1/patients", {"search": "Марія Бондар"})
    by_phone = client.get("/api/v1/patients", {"search": "067111"})
    by_number = client.get("/api/v1/patients", {"search": maria.public_number.lower()})

    assert by_full_name.status_code == 200
    assert [item["id"] for item in by_full_name.json()["patients"]] == [str(maria.pk)]
    assert [item["id"] for item in by_phone.json()["patients"]] == [str(maria.pk)]
    assert [item["id"] for item in by_number.json()["patients"]] == [str(maria.pk)]
    assert by_number.json()["patients"][0]["appointment_summary"] is None
    assert by_number.json()["patients"][0]["state_label"] == "Новий пацієнт"


@pytest.mark.django_db
def test_patient_list_uses_stable_cursor_pagination():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    for index in range(21):
        create_patient(first_name=f"Пацієнт {index:02d}", phone=f"067000{index:04d}")
    client = authenticated_client(admin)

    first = client.get("/api/v1/patients")
    second = client.get("/api/v1/patients", {"cursor": first.json()["next_cursor"]})

    assert first.status_code == 200
    assert len(first.json()["patients"]) == 20
    assert first.json()["next_cursor"]
    assert second.status_code == 200
    assert len(second.json()["patients"]) == 1
    assert second.json()["next_cursor"] is None
    assert {item["id"] for item in first.json()["patients"]}.isdisjoint(
        {item["id"] for item in second.json()["patients"]}
    )


@pytest.mark.django_db
def test_create_normalizes_phone_returns_duplicate_warning_and_records_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    existing = create_patient(first_name="Марія", phone="+380 67 123 45 67")

    response = authenticated_client(admin).post(
        "/api/v1/patients",
        {
            "first_name": "  Марина ",
            "last_name": "  Коваль ",
            "phone": "0671234567",
            "birth_date": "1990-06-14",
            "email": " MARINA@example.test ",
            "note": "  Попросила нагадати про запис. ",
        },
        format="json",
    )

    assert response.status_code == 201
    result = response.json()
    assert result["duplicate_warning"] is True
    assert [item["id"] for item in result["possible_duplicates"]] == [str(existing.pk)]
    patient = Patient.objects.get(pk=result["patient"]["id"])
    assert patient.normalized_phone == "+380671234567"
    assert patient.email == "marina@example.test"
    assert patient.note == "Попросила нагадати про запис."
    assert patient.public_number.startswith("P-")
    event = AuditEvent.objects.get(action=AuditAction.PATIENT_CREATED)
    assert event.actor_id == admin.pk
    assert event.object_id == str(patient.pk)
    assert event.after["public_number"] == patient.public_number


@pytest.mark.django_db
def test_reception_sees_all_safe_contacts_and_can_assign_active_podologist():
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    create_patient(first_name="Без", phone="0671111111")
    client = authenticated_client(reception)

    created = client.post(
        "/api/v1/patients",
        {
            "first_name": "Олена",
            "last_name": "Романюк",
            "phone": "0672222222",
            "primary_podologist_id": podologist.pk,
        },
        format="json",
    )
    listed = client.get("/api/v1/patients")

    assert created.status_code == 201
    assert created.json()["patient"]["primary_podologist"] == {
        "id": podologist.pk,
        "display_name": podologist.display_name,
    }
    assert len(listed.json()["patients"]) == 2
    forbidden_keys = {"medical_profile", "allergies", "clinical_notes", "photos"}
    assert forbidden_keys.isdisjoint(listed.json()["patients"][0])


@pytest.mark.django_db
def test_podologist_scope_is_applied_before_search_and_duplicate_serialization():
    owner = create_user(email="owner@example.test", role=UserRole.PODOLOGIST, first_name="Власник")
    foreign = create_user(
        email="foreign@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Чужий",
    )
    own_patient = create_patient(
        first_name="Власна",
        phone="0673333333",
        primary_podologist=owner,
    )
    create_patient(
        first_name="Чужа",
        phone="0674444444",
        primary_podologist=foreign,
    )
    client = authenticated_client(owner)

    listed = client.get("/api/v1/patients")
    foreign_search = client.get("/api/v1/patients", {"search": "0674444444"})
    created = client.post(
        "/api/v1/patients",
        {"first_name": "Нова", "last_name": "Власна", "phone": "0674444444"},
        format="json",
    )

    assert [item["id"] for item in listed.json()["patients"]] == [str(own_patient.pk)]
    assert foreign_search.json()["patients"] == []
    assert created.status_code == 201
    assert created.json()["duplicate_warning"] is False
    assert Patient.objects.get(pk=created.json()["patient"]["id"]).primary_podologist == owner


@pytest.mark.django_db
def test_podologist_cannot_assign_patient_to_another_podologist():
    actor = create_user(email="actor@example.test", role=UserRole.PODOLOGIST)
    other = create_user(email="other@example.test", role=UserRole.PODOLOGIST)

    response = authenticated_client(actor).post(
        "/api/v1/patients",
        {
            "first_name": "Тест",
            "last_name": "Scope",
            "phone": "0675555555",
            "primary_podologist_id": other.pk,
        },
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "patient_podologist_scope_violation"
    assert Patient.objects.count() == 0
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"first_name": "", "last_name": "Коваль", "phone": "0671234567"}, "first_name"),
        ({"first_name": "Олена", "last_name": "", "phone": "0671234567"}, "last_name"),
        ({"first_name": "Олена", "last_name": "Коваль", "phone": "123"}, "phone"),
        (
            {
                "first_name": "Олена",
                "last_name": "Коваль",
                "phone": "0671234567",
                "birth_date": (date.today() + timedelta(days=1)).isoformat(),
            },
            "birth_date",
        ),
    ],
)
def test_create_rejects_invalid_patient_fields(payload: dict[str, object], field: str):
    admin = create_user(email=f"{field}@example.test", role=UserRole.ADMIN)

    response = authenticated_client(admin).post("/api/v1/patients", payload, format="json")

    assert response.status_code == 422
    assert field in response.json()["fields"]
    assert Patient.objects.count() == 0


@pytest.mark.django_db
def test_patient_endpoints_require_authentication():
    client = APIClient()

    assert client.get("/api/v1/patients").status_code == 401
    assert client.post("/api/v1/patients", {}, format="json").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_database_allows_duplicate_normalized_phone_but_rejects_public_number_collision():
    first = create_patient(first_name="Перша", phone="0677777777")
    second = create_patient(first_name="Друга", phone="+38 067 777 77 77")

    assert first.normalized_phone == second.normalized_phone
    assert first.public_number != second.public_number
    with pytest.raises(IntegrityError), transaction.atomic():
        Patient.objects.create(
            public_number=first.public_number,
            first_name="Третя",
            last_name="Пацієнт",
            phone="0678888888",
        )
