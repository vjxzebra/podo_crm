from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import Service

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_service(
    *,
    code: str,
    name: str,
    is_active: bool = True,
    duration_minutes: int = 45,
    price_minor: int = 120000,
    color: str = "#4F46E5",
) -> Service:
    return Service.objects.create(
        code=code,
        name=name,
        duration_minutes=duration_minutes,
        price_minor=price_minor,
        color=color,
        is_active=is_active,
    )


@pytest.mark.django_db
def test_admin_searches_and_filters_full_service_catalog():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    active = create_service(code="CONSULT", name="Первинна консультація")
    inactive = create_service(code="OLD-CALLUS", name="Архівна обробка", is_active=False)
    client = authenticated_client(admin)

    all_services = client.get("/api/v1/services")
    search = client.get("/api/v1/services", {"search": "consult"})
    inactive_only = client.get("/api/v1/services", {"status": "inactive"})
    detail = client.get(f"/api/v1/services/{inactive.pk}")

    assert all_services.status_code == 200
    assert {item["id"] for item in all_services.json()["services"]} == {
        str(active.pk),
        str(inactive.pk),
    }
    assert [item["id"] for item in search.json()["services"]] == [str(active.pk)]
    assert [item["id"] for item in inactive_only.json()["services"]] == [str(inactive.pk)]
    assert detail.status_code == 200
    assert detail.json()["is_active"] is False
    assert "version" in detail.json()


@pytest.mark.django_db
def test_admin_creates_normalized_service_and_records_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)

    response = authenticated_client(admin).post(
        "/api/v1/services",
        {
            "code": "  nail-care_1 ",
            "name": "  Обробка нігтів  ",
            "duration_minutes": 60,
            "price_minor": 0,
            "color": "#a855f7",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["code"] == "NAIL-CARE_1"
    assert response.json()["name"] == "Обробка нігтів"
    assert response.json()["price_minor"] == 0
    assert response.json()["color"] == "#A855F7"
    event = AuditEvent.objects.get(action=AuditAction.SERVICE_CREATED)
    assert event.actor_id == admin.pk
    assert event.after["duration_minutes"] == 60
    assert event.after["price_minor"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("code", "не-латиниця"),
        ("duration_minutes", 0),
        ("price_minor", -1),
        ("color", "violet"),
    ],
)
def test_service_create_rejects_invalid_domain_values(field: str, value: object):
    admin = create_user(email=f"{field}@example.test", role=UserRole.ADMIN)
    payload: dict[str, object] = {
        "code": "VALID",
        "name": "Валідна послуга",
        "duration_minutes": 30,
        "price_minor": 50000,
        "color": "#0EA5E9",
    }
    payload[field] = value

    response = authenticated_client(admin).post("/api/v1/services", payload, format="json")

    assert response.status_code == 422
    assert field in response.json()["fields"]
    assert Service.objects.count() == 0


@pytest.mark.django_db
def test_service_code_conflict_and_stale_update_preserve_current_values():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    first = create_service(code="CONSULT", name="Консультація")
    second = create_service(code="CARE", name="Догляд")
    client = authenticated_client(admin)

    duplicate = client.post(
        "/api/v1/services",
        {
            "code": "consult",
            "name": "Дублікат",
            "duration_minutes": 15,
            "price_minor": 10000,
            "color": "#DC2626",
        },
        format="json",
    )
    updated = client.patch(
        f"/api/v1/services/{second.pk}",
        {"price_minor": 135000, "duration_minutes": 75, "version": second.version},
        format="json",
    )
    stale = client.patch(
        f"/api/v1/services/{second.pk}",
        {"name": "Втрачена зміна", "version": second.version},
        format="json",
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "service_code_already_exists"
    assert duplicate.json()["fields"]["code"]
    assert updated.status_code == 200
    assert updated.json()["price_minor"] == 135000
    assert updated.json()["duration_minutes"] == 75
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"
    second.refresh_from_db()
    assert second.name == "Догляд"
    assert Service.objects.filter(pk=first.pk).exists()


@pytest.mark.django_db
def test_service_deactivation_is_reversible_and_delete_is_not_available():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    service = create_service(code="CALLUS", name="Обробка мозоля")
    client = authenticated_client(admin)

    deactivated = client.patch(
        f"/api/v1/services/{service.pk}",
        {"is_active": False, "version": service.version},
        format="json",
    )
    reactivated = client.patch(
        f"/api/v1/services/{service.pk}",
        {"is_active": True, "version": deactivated.json()["version"]},
        format="json",
    )
    deleted = client.delete(f"/api/v1/services/{service.pk}")

    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert deleted.status_code == 405
    assert Service.objects.filter(pk=service.pk).exists()
    assert list(AuditEvent.objects.order_by("occurred_at").values_list("action", flat=True)) == [
        AuditAction.SERVICE_DEACTIVATED,
        AuditAction.SERVICE_REACTIVATED,
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.PODOLOGIST, UserRole.RECEPTION])
def test_non_admin_receives_active_picker_projection_and_cannot_mutate(role: str):
    user = create_user(email=f"{role}@example.test", role=role)
    active = create_service(code="ACTIVE", name="Активна")
    inactive = create_service(code="INACTIVE", name="Неактивна", is_active=False)
    client = authenticated_client(user)

    listed = client.get("/api/v1/services", {"status": "inactive"})
    active_detail = client.get(f"/api/v1/services/{active.pk}")
    inactive_detail = client.get(f"/api/v1/services/{inactive.pk}")
    created = client.post(
        "/api/v1/services",
        {
            "code": "NOPE",
            "name": "Заборонена",
            "duration_minutes": 30,
            "price_minor": 100,
            "color": "#000000",
        },
        format="json",
    )
    updated = client.patch(
        f"/api/v1/services/{active.pk}",
        {"is_active": False, "version": active.version},
        format="json",
    )

    assert listed.status_code == 200
    assert listed.json()["services"] == [
        {
            "id": str(active.pk),
            "code": "ACTIVE",
            "name": "Активна",
            "duration_minutes": 45,
            "price_minor": 120000,
            "color": "#4F46E5",
        }
    ]
    assert active_detail.status_code == 200
    assert set(active_detail.json()) == {
        "id",
        "code",
        "name",
        "duration_minutes",
        "price_minor",
        "color",
    }
    assert inactive_detail.status_code == 404
    assert created.status_code == 403
    assert updated.status_code == 403


@pytest.mark.django_db
def test_service_endpoints_require_authentication():
    service = create_service(code="PRIVATE", name="Приватна")
    client = APIClient()

    assert client.get("/api/v1/services").status_code == 401
    assert client.get(f"/api/v1/services/{service.pk}").status_code == 401
    assert client.post("/api/v1/services", {}, format="json").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_database_enforces_service_code_duration_and_price_constraints():
    create_service(code="UNIQUE", name="Унікальна")
    with pytest.raises(IntegrityError), transaction.atomic():
        create_service(code="unique", name="Дублікат")
    with pytest.raises(IntegrityError), transaction.atomic():
        Service.objects.create(
            id=uuid4(),
            code="ZERO",
            name="Нульова тривалість",
            duration_minutes=0,
            price_minor=100,
            color="#000000",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Service.objects.create(
            id=uuid4(),
            code="NEGATIVE",
            name="Від’ємна ціна",
            duration_minutes=30,
            price_minor=-1,
            color="#000000",
        )
