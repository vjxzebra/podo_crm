import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.test import Client

from apps.accounts.models import User, UserRole
from apps.accounts.team_services import update_team_user
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from config.api.exceptions import ApiProblem

PASSWORD = "correct horse battery staple"  # noqa: S105
TEMPORARY_PASSWORD = "temporary correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str, is_active: bool = True, **extra):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        role=role,
        is_active=is_active,
        **extra,
    )


def json_request(client: Client, method: str, path: str, body: dict):
    return getattr(client, method)(
        path,
        data=json.dumps(body),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_admin_can_search_filter_and_retrieve_team_members():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    active = create_user(
        email="active@example.test",
        role=UserRole.RECEPTION,
        first_name="Ірина",
        last_name="Коваль",
        phone="+380 50 111 22 33",
    )
    inactive = create_user(
        email="inactive@example.test",
        role=UserRole.PODOLOGIST,
        is_active=False,
        first_name="Олена",
        last_name="Мельник",
        phone="+380 67 444 55 66",
    )
    client = Client()
    client.force_login(admin)

    response = client.get(
        "/api/v1/users",
        {"search": "Олена", "status": "inactive", "role": "podologist"},
    )

    assert response.status_code == 200
    assert len(response.json()["users"]) == 1
    assert response.json()["users"][0] == {
        "id": inactive.pk,
        "first_name": "Олена",
        "last_name": "Мельник",
        "display_name": "Олена Мельник",
        "phone": "+380 67 444 55 66",
        "email": "inactive@example.test",
        "role": "podologist",
        "is_active": False,
        "must_change_password": False,
        "temporary_password_expires_at": None,
        "last_login": None,
    }
    detail = client.get(f"/api/v1/users/{active.pk}")
    assert detail.status_code == 200
    assert detail.json()["email"] == active.email


@pytest.mark.django_db
def test_admin_creates_employee_with_temporary_password_and_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = Client()
    client.force_login(admin)

    response = json_request(
        client,
        "post",
        "/api/v1/users",
        {
            "first_name": " Марія ",
            "last_name": " Бондар ",
            "phone": "+380 93 555 66 77",
            "email": "NEW.Employee@Example.Test",
            "role": "reception",
            "temporary_password": TEMPORARY_PASSWORD,
            "temporary_password_confirmation": TEMPORARY_PASSWORD,
            "is_active": True,
            "must_change_password": True,
        },
    )

    assert response.status_code == 201
    assert "temporary_password" not in response.json()
    user = User.objects.get(pk=response.json()["id"])
    assert user.email == "new.employee@example.test"
    assert user.display_name == "Марія Бондар"
    assert user.check_password(TEMPORARY_PASSWORD)
    assert user.must_change_password is True
    assert user.temporary_password_expires_at is not None
    event = AuditEvent.objects.get(action=AuditAction.USER_CREATED)
    assert event.actor_id == admin.pk
    assert event.object_id == str(user.pk)
    assert "password" not in event.after


@pytest.mark.django_db
def test_create_rejects_case_insensitive_duplicate_and_password_mismatch():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    create_user(email="employee@example.test", role=UserRole.RECEPTION)
    client = Client()
    client.force_login(admin)
    base = {
        "first_name": "Марія",
        "last_name": "Бондар",
        "phone": "",
        "email": "EMPLOYEE@EXAMPLE.TEST",
        "role": "reception",
        "temporary_password": TEMPORARY_PASSWORD,
        "temporary_password_confirmation": TEMPORARY_PASSWORD,
        "is_active": True,
        "must_change_password": True,
    }

    duplicate = json_request(client, "post", "/api/v1/users", base)
    mismatch = json_request(
        client,
        "post",
        "/api/v1/users",
        {
            **base,
            "email": "other@example.test",
            "temporary_password_confirmation": "different password",
        },
    )

    assert duplicate.status_code == 422
    assert "email" in duplicate.json()["fields"]
    assert mismatch.status_code == 422
    assert "temporary_password_confirmation" in mismatch.json()["fields"]
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_role_change_updates_contacts_revokes_sessions_and_writes_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    target = create_user(
        email="employee@example.test",
        role=UserRole.RECEPTION,
        first_name="Олена",
        last_name="Мельник",
    )
    target_client = Client()
    target_client.force_login(target)
    target_session_key = target_client.session.session_key
    admin_client = Client()
    admin_client.force_login(admin)

    response = json_request(
        admin_client,
        "patch",
        f"/api/v1/users/{target.pk}",
        {
            "first_name": "Олександра",
            "phone": "+380 50 000 00 00",
            "email": "updated@example.test",
            "role": "podologist",
        },
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Олександра Мельник"
    assert response.json()["role"] == "podologist"
    assert target_session_key is not None
    assert target_client.get("/api/v1/session").status_code == 401
    event = AuditEvent.objects.get(action=AuditAction.USER_ROLE_CHANGED)
    assert event.before["role"] == "reception"
    assert event.after["role"] == "podologist"
    assert event.after["phone"] == "+380 50 000 00 00"


@pytest.mark.django_db
def test_deactivation_revokes_login_but_preserves_profile_and_can_be_reactivated():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    target = create_user(
        email="employee@example.test",
        role=UserRole.PODOLOGIST,
        first_name="Олена",
        last_name="Мельник",
    )
    target_client = Client()
    target_client.force_login(target)
    admin_client = Client()
    admin_client.force_login(admin)

    deactivated = admin_client.post(f"/api/v1/users/{target.pk}/deactivate")

    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert User.objects.filter(pk=target.pk, is_active=False).exists()
    assert target_client.get("/api/v1/session").status_code == 401
    assert AuditEvent.objects.filter(action=AuditAction.USER_DEACTIVATED).exists()

    activated = json_request(
        admin_client,
        "patch",
        f"/api/v1/users/{target.pk}",
        {"is_active": True},
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True
    assert AuditEvent.objects.filter(action=AuditAction.USER_REACTIVATED).exists()


@pytest.mark.django_db
def test_last_active_admin_cannot_be_demoted_or_deactivated():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = Client()
    client.force_login(admin)

    demotion = json_request(
        client,
        "patch",
        f"/api/v1/users/{admin.pk}",
        {"role": "reception"},
    )
    deactivation = client.post(f"/api/v1/users/{admin.pk}/deactivate")

    assert demotion.status_code == 409
    assert demotion.json()["code"] == "last_admin_protected"
    assert deactivation.status_code == 409
    assert deactivation.json()["code"] == "last_admin_protected"
    admin.refresh_from_db()
    assert admin.role == UserRole.ADMIN
    assert admin.is_active is True
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.PODOLOGIST, UserRole.RECEPTION])
def test_non_admin_cannot_access_any_team_endpoint(role):
    user = create_user(email=f"{role}@example.test", role=role)
    target = create_user(email="target@example.test", role=UserRole.PODOLOGIST)
    client = Client()
    client.force_login(user)

    assert client.get("/api/v1/users").status_code == 403
    assert client.get(f"/api/v1/users/{target.pk}").status_code == 403
    assert json_request(client, "post", "/api/v1/users", {}).status_code == 403
    assert json_request(client, "patch", f"/api/v1/users/{target.pk}", {}).status_code == 403
    assert client.post(f"/api/v1/users/{target.pk}/deactivate").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_concurrent_admin_demotions_preserve_one_active_admin():
    first = create_user(email="first@example.test", role=UserRole.ADMIN)
    second = create_user(email="second@example.test", role=UserRole.ADMIN)
    barrier = Barrier(2)

    def demote(user_id: int) -> str:
        close_old_connections()
        actor = User.objects.get(pk=user_id)
        barrier.wait(timeout=5)
        try:
            update_team_user(
                actor=actor,
                target_id=user_id,
                correlation_id=f"concurrent-{user_id}",
                changes={"role": UserRole.RECEPTION},
            )
        except ApiProblem as exc:
            return exc.problem_code
        finally:
            close_old_connections()
        return "updated"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(demote, [first.pk, second.pk]))

    assert sorted(results) == ["last_admin_protected", "updated"]
    assert User.objects.filter(role=UserRole.ADMIN, is_active=True).count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.USER_ROLE_CHANGED).count() == 1
