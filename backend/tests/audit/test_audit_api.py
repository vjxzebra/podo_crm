import pytest
from django.db import transaction
from django.test import Client

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.audit.services import REDACTED, record_audit_event


def create_user(role: str, email: str) -> User:
    return User.objects.create_user(
        email=email,
        role=role,
        first_name="Олена",
        last_name="Мельник",
    )


def create_event(actor: User) -> AuditEvent:
    with transaction.atomic():
        return record_audit_event(
            actor=actor,
            action=AuditAction.USER_ROLE_CHANGED,
            object_type="user",
            object_id=actor.pk,
            object_label=actor.display_name,
            correlation_id="api-audit-check",
            before={"role": UserRole.RECEPTION, "password_hash": "old-secret"},
            after={"role": UserRole.ADMIN, "password_hash": "new-secret"},
            description="Змінено роль працівника.",
            note="Підтверджено власником клініки.",
        )


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.PODOLOGIST, UserRole.RECEPTION])
def test_audit_endpoints_are_admin_only(role):
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    event = create_event(admin)
    client = Client()
    user = create_user(role, f"{role}@example.test")
    client.force_login(user)

    assert client.get("/api/v1/audit-events").status_code == 403
    assert client.get(f"/api/v1/audit-events/{event.pk}").status_code == 403


@pytest.mark.django_db
def test_audit_endpoints_require_authentication():
    client = Client()

    assert client.get("/api/v1/audit-events").status_code == 401


@pytest.mark.django_db
def test_admin_can_filter_list_and_read_redacted_detail_snapshot():
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    event = create_event(admin)
    other = create_user(UserRole.RECEPTION, "other@example.test")
    with transaction.atomic():
        record_audit_event(
            actor=other,
            action=AuditAction.PASSWORD_CHANGED,
            object_type="user",
            object_id=other.pk,
            object_label=other.display_name,
            correlation_id="other-event",
        )

    admin.first_name = "Змінене ім'я"
    admin.save(update_fields=("first_name",))
    client = Client()
    client.force_login(admin)

    listing = client.get(
        "/api/v1/audit-events",
        {"section": "team", "actor_id": admin.pk, "search": "роль"},
    )
    assert listing.status_code == 200
    assert listing.json()["next_cursor"] is None
    assert len(listing.json()["events"]) == 1
    item = listing.json()["events"][0]
    assert item["id"] == str(event.pk)
    assert item["actor"] == {
        "id": admin.pk,
        "display_name": "Олена Мельник",
        "email": "admin@example.test",
        "role": UserRole.ADMIN,
    }
    assert item["object"] == {
        "type": "user",
        "id": str(admin.pk),
        "label": "Олена Мельник",
    }

    detail = client.get(f"/api/v1/audit-events/{event.pk}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["before"]["password_hash"] == REDACTED
    assert payload["after"]["password_hash"] == REDACTED
    assert payload["changes"] == [
        {"field": "role", "before": UserRole.RECEPTION, "after": UserRole.ADMIN}
    ]
    assert payload["note"] == "Підтверджено власником клініки."
    assert payload["correlation_id"] == "api-audit-check"


@pytest.mark.django_db
def test_invalid_filter_uses_shared_validation_envelope():
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    client = Client()
    client.force_login(admin)

    response = client.get("/api/v1/audit-events", {"actor_id": "not-an-id"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert "actor_id" in response.json()["fields"]


@pytest.mark.django_db
def test_list_uses_stable_event_cursor():
    admin = create_user(UserRole.ADMIN, "admin@example.test")
    for index in range(51):
        with transaction.atomic():
            record_audit_event(
                actor=admin,
                action=AuditAction.SETTINGS_UPDATED,
                object_type="clinic_profile",
                object_id="primary",
                object_label="Podoria",
                correlation_id=f"page-{index}",
            )
    client = Client()
    client.force_login(admin)

    first_page = client.get("/api/v1/audit-events")
    assert first_page.status_code == 200
    assert len(first_page.json()["events"]) == 50
    assert first_page.json()["next_cursor"] == first_page.json()["events"][-1]["id"]

    second_page = client.get(
        "/api/v1/audit-events",
        {"cursor": first_page.json()["next_cursor"]},
    )
    assert second_page.status_code == 200
    assert len(second_page.json()["events"]) == 1
    assert second_page.json()["next_cursor"] is None
