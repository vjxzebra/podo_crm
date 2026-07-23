import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction, AuditSection
from apps.patients.models import Patient
from apps.work_items.models import WorkItem, WorkItemKind

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str, is_active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        first_name="Тест",
        last_name=role,
        is_active=is_active,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_patient(*, primary_podologist: User | None = None) -> Patient:
    return Patient.objects.create(
        first_name="Марія",
        last_name="Бондар",
        phone="067 123 45 67",
        note="Приватна адміністративна примітка.",
        primary_podologist=primary_podologist,
    )


def create_item(
    *,
    assignee: User,
    created_by: User,
    title: str,
    patient: Patient | None = None,
    is_completed: bool = False,
) -> WorkItem:
    return WorkItem.objects.create(
        kind=WorkItemKind.OTHER,
        title=title,
        due_at=timezone.now() + timedelta(hours=2),
        assignee=assignee,
        patient=patient,
        is_completed=is_completed,
        completed_at=timezone.now() if is_completed else None,
        completed_by=created_by if is_completed else None,
        created_by=created_by,
    )


@pytest.mark.django_db
def test_admin_creates_patient_callback_with_atomic_audit() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    patient = create_patient()

    response = authenticated_client(admin).post(
        "/api/v1/work-items",
        {
            "kind": "callback",
            "title": "  Перетелефонувати Марії  ",
            "due_at": (timezone.now() + timedelta(hours=3)).isoformat(),
            "assignee_id": reception.pk,
            "patient_id": str(patient.pk),
            "comment": "  Уточнити зручний час.  ",
            "is_important": True,
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "callback"
    assert body["title"] == "Перетелефонувати Марії"
    assert body["assignee"]["id"] == reception.pk
    assert body["patient"] == {
        "id": str(patient.pk),
        "public_number": patient.public_number,
        "display_name": patient.display_name,
        "phone": patient.phone,
    }
    assert body["comment"] == "Уточнити зручний час."
    assert body["version"] == 1
    event = AuditEvent.objects.get(action=AuditAction.WORK_ITEM_CREATED)
    assert event.section == AuditSection.WORK_ITEMS
    assert event.before == {}
    assert event.after["patient_id"] == str(patient.pk)
    assert event.after["assignee_id"] == reception.pk


@pytest.mark.django_db
def test_callback_requires_patient_and_inactive_assignee_is_rejected() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    inactive = create_user(
        email="inactive@example.test",
        role=UserRole.RECEPTION,
        is_active=False,
    )
    client = authenticated_client(admin)
    payload = {
        "kind": "callback",
        "title": "Перетелефонувати",
        "due_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "assignee_id": admin.pk,
    }

    missing_patient = client.post("/api/v1/work-items", payload, format="json")
    payload.update({"kind": "other", "assignee_id": inactive.pk})
    inactive_assignee = client.post("/api/v1/work-items", payload, format="json")

    assert missing_patient.status_code == 422
    assert "patient_id" in missing_patient.json()["fields"]
    assert inactive_assignee.status_code == 422
    assert inactive_assignee.json()["code"] == "work_item_assignee_invalid"
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_podologist_cannot_link_foreign_patient_or_receive_unrelated_patient_task() -> None:
    owner = create_user(email="owner@example.test", role=UserRole.PODOLOGIST)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    patient = create_patient(primary_podologist=foreign)
    payload = {
        "kind": "callback",
        "title": "Перетелефонувати",
        "due_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "assignee_id": owner.pk,
        "patient_id": str(patient.pk),
    }

    hidden = authenticated_client(owner).post("/api/v1/work-items", payload, format="json")
    invalid_assignment = authenticated_client(admin).post(
        "/api/v1/work-items", payload, format="json"
    )

    assert hidden.status_code == 404
    assert hidden.json()["code"] == "not_found"
    assert invalid_assignment.status_code == 422
    assert invalid_assignment.json()["code"] == "work_item_assignee_patient_scope_violation"
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_list_applies_own_all_scope_by_role_and_returns_safe_summary() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    patient = create_patient(primary_podologist=podologist)
    create_item(assignee=admin, created_by=admin, title="Справи власника")
    create_item(assignee=reception, created_by=admin, title="Справи ресепшну")
    create_item(
        assignee=podologist,
        created_by=admin,
        title="Справи подолога",
        patient=patient,
    )

    admin_all = authenticated_client(admin).get("/api/v1/work-items?scope=all&status=all")
    reception_own = authenticated_client(reception).get("/api/v1/work-items?scope=own&status=all")
    podologist_all = authenticated_client(podologist).get("/api/v1/work-items?scope=all&status=all")

    assert admin_all.status_code == reception_own.status_code == podologist_all.status_code == 200
    assert len(admin_all.json()["work_items"]) == 3
    assert admin_all.json()["effective_scope"] == "all"
    assert admin_all.json()["summary"]["open"] == 3
    assert [item["title"] for item in reception_own.json()["work_items"]] == ["Справи ресепшну"]
    assert reception_own.json()["effective_scope"] == "own"
    podologist_body = podologist_all.json()
    assert podologist_body["effective_scope"] == "own"
    assert [item["title"] for item in podologist_body["work_items"]] == ["Справи подолога"]
    assert "note" not in podologist_body["work_items"][0]["patient"]
    assert "medical_profile" not in podologist_body["work_items"][0]["patient"]
    assert len(podologist_body["assignees"]) == 3


@pytest.mark.django_db
def test_assignee_completes_and_reopens_item_with_versioned_audit() -> None:
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    item = create_item(assignee=podologist, created_by=podologist, title="Контроль")
    client = authenticated_client(podologist)

    completed = client.patch(
        f"/api/v1/work-items/{item.pk}",
        {"version": 1, "is_completed": True},
        format="json",
    )
    stale = client.patch(
        f"/api/v1/work-items/{item.pk}",
        {"version": 1, "is_completed": False},
        format="json",
    )
    reopened = client.patch(
        f"/api/v1/work-items/{item.pk}",
        {"version": 2, "is_completed": False},
        format="json",
    )

    assert completed.status_code == 200
    assert completed.json()["is_completed"] is True
    assert completed.json()["completed_by"]["id"] == podologist.pk
    assert completed.json()["version"] == 2
    assert stale.status_code == 409
    assert stale.json()["code"] == "work_item_version_conflict"
    assert reopened.status_code == 200
    assert reopened.json()["is_completed"] is False
    assert reopened.json()["completed_at"] is None
    assert reopened.json()["version"] == 3
    events = list(AuditEvent.objects.order_by("occurred_at").values_list("action", flat=True))
    assert events == [
        AuditAction.WORK_ITEM_COMPLETED,
        AuditAction.WORK_ITEM_REOPENED,
    ]


@pytest.mark.django_db
def test_podologist_foreign_item_patch_is_same_not_found_and_completed_edit_is_guarded() -> None:
    owner = create_user(email="owner@example.test", role=UserRole.PODOLOGIST)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    foreign_item = create_item(assignee=foreign, created_by=foreign, title="Чужа справа")
    completed_item = create_item(
        assignee=owner,
        created_by=owner,
        title="Виконана справа",
        is_completed=True,
    )
    client = authenticated_client(owner)

    hidden = client.patch(
        f"/api/v1/work-items/{foreign_item.pk}",
        {"version": 1, "is_completed": True},
        format="json",
    )
    guarded = client.patch(
        f"/api/v1/work-items/{completed_item.pk}",
        {"version": 1, "title": "Змінена справа"},
        format="json",
    )

    assert hidden.status_code == 404
    assert hidden.json()["code"] == "not_found"
    assert guarded.status_code == 409
    assert guarded.json()["code"] == "work_item_completed"
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_update_requires_explicit_version() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    item = create_item(assignee=reception, created_by=reception, title="Передзвонити")

    response = authenticated_client(reception).patch(
        f"/api/v1/work-items/{item.pk}",
        {"is_completed": True},
        format="json",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "version" in response.json()["fields"]
    item.refresh_from_db()
    assert item.is_completed is False
    assert AuditEvent.objects.count() == 0


def test_openapi_requires_update_version() -> None:
    schema = json.loads(
        (Path(__file__).parents[2] / "openapi" / "schema.json").read_text(encoding="utf-8")
    )
    operation = schema["paths"]["/api/v1/work-items/{work_item_id}"]["patch"]
    request_body = operation["requestBody"]
    component_ref = request_body["content"]["application/json"]["schema"]["$ref"]
    component = schema["components"]["schemas"][component_ref.rsplit("/", maxsplit=1)[-1]]

    assert request_body["required"] is True
    assert "version" in component["required"]


@pytest.mark.django_db
def test_work_item_endpoints_require_authentication() -> None:
    item_owner = create_user(email="owner@example.test", role=UserRole.RECEPTION)
    item = create_item(assignee=item_owner, created_by=item_owner, title="Справи")
    client = APIClient()

    assert client.get("/api/v1/work-items").status_code == 401
    assert client.post("/api/v1/work-items", {}, format="json").status_code == 401
    assert (
        client.patch(
            f"/api/v1/work-items/{item.pk}",
            {"version": 1, "is_completed": True},
            format="json",
        ).status_code
        == 401
    )
