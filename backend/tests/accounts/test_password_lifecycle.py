import json
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import Client
from django.utils import timezone

from apps.accounts.models import PasswordResetRequest, User, UserRole

CURRENT_PASSWORD = "correct horse battery staple"  # noqa: S105
NEW_PASSWORD = "new correct horse battery staple"  # noqa: S105
TEMPORARY_PASSWORD = "temporary correct horse battery staple"  # noqa: S105


def csrf_client() -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    response = client.get("/api/v1/session")
    assert response.status_code == 401
    return client, client.cookies[settings.CSRF_COOKIE_NAME].value


def post_json(client: Client, path: str, body: dict[str, str], token: str | None = None):
    headers = {}
    if token is not None:
        headers["X-CSRFToken"] = token
    return client.post(
        path,
        data=json.dumps(body),
        content_type="application/json",
        headers=headers,
    )


def login(client: Client, email: str, password: str, token: str):
    return post_json(
        client,
        "/api/v1/auth/login",
        {"email": email, "password": password},
        token,
    )


@pytest.mark.django_db
def test_forced_first_login_blocks_workspace_and_rotates_session():
    user = User.objects.create_user(
        email="podologist@example.test",
        password=TEMPORARY_PASSWORD,
        role=UserRole.PODOLOGIST,
        must_change_password=True,
        temporary_password_expires_at=timezone.now() + timedelta(hours=1),
    )
    current_client, current_token = csrf_client()
    other_client, other_token = csrf_client()
    assert login(current_client, user.email, TEMPORARY_PASSWORD, current_token).status_code == 200
    assert login(other_client, user.email, TEMPORARY_PASSWORD, other_token).status_code == 200
    old_current_key = current_client.cookies[settings.SESSION_COOKIE_NAME].value
    other_key = other_client.cookies[settings.SESSION_COOKIE_NAME].value

    session_response = current_client.get("/api/v1/session")
    assert session_response.status_code == 200
    assert session_response.json()["must_change_password"] is True
    assert session_response.json()["route_ids"] == []
    blocked_response = current_client.get("/api/v1/password-reset-requests")
    assert blocked_response.status_code == 403

    response = post_json(
        current_client,
        "/api/v1/auth/first-login-password",
        {"new_password": NEW_PASSWORD, "new_password_confirmation": NEW_PASSWORD},
        current_client.cookies[settings.CSRF_COOKIE_NAME].value,
    )

    assert response.status_code == 200
    assert response.json()["must_change_password"] is False
    assert response.json()["route_ids"]
    assert current_client.cookies[settings.SESSION_COOKIE_NAME].value != old_current_key
    assert not Session.objects.filter(session_key=other_key).exists()
    assert current_client.get("/api/v1/session").status_code == 200
    assert other_client.get("/api/v1/session").status_code == 401
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert user.must_change_password is False
    assert user.temporary_password_expires_at is None


@pytest.mark.django_db
def test_first_login_reports_mismatch_policy_and_expired_temporary_password():
    user = User.objects.create_user(
        email="expired@example.test",
        password=TEMPORARY_PASSWORD,
        role=UserRole.RECEPTION,
        must_change_password=True,
        temporary_password_expires_at=timezone.now() + timedelta(hours=1),
    )
    client, token = csrf_client()
    assert login(client, user.email, TEMPORARY_PASSWORD, token).status_code == 200
    current_token = client.cookies[settings.CSRF_COOKIE_NAME].value

    mismatch = post_json(
        client,
        "/api/v1/auth/first-login-password",
        {"new_password": NEW_PASSWORD, "new_password_confirmation": "different password"},
        current_token,
    )
    assert mismatch.status_code == 422
    assert "new_password_confirmation" in mismatch.json()["fields"]

    weak = post_json(
        client,
        "/api/v1/auth/first-login-password",
        {"new_password": "123", "new_password_confirmation": "123"},
        current_token,
    )
    assert weak.status_code == 422
    assert "new_password" in weak.json()["fields"]

    User.objects.filter(pk=user.pk).update(
        temporary_password_expires_at=timezone.now() - timedelta(seconds=1)
    )
    expired = post_json(
        client,
        "/api/v1/auth/first-login-password",
        {"new_password": NEW_PASSWORD, "new_password_confirmation": NEW_PASSWORD},
        current_token,
    )
    assert expired.status_code == 409
    assert expired.json()["code"] == "temporary_password_expired"


@pytest.mark.django_db
def test_own_password_change_checks_current_password_and_revokes_other_sessions():
    user = User.objects.create_user(
        email="reception@example.test",
        password=CURRENT_PASSWORD,
        role=UserRole.RECEPTION,
    )
    current_client, current_token = csrf_client()
    other_client, other_token = csrf_client()
    assert login(current_client, user.email, CURRENT_PASSWORD, current_token).status_code == 200
    assert login(other_client, user.email, CURRENT_PASSWORD, other_token).status_code == 200
    other_key = other_client.cookies[settings.SESSION_COOKIE_NAME].value
    current_token = current_client.cookies[settings.CSRF_COOKIE_NAME].value

    rejected = post_json(
        current_client,
        "/api/v1/auth/change-password",
        {
            "current_password": "wrong password",
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
        current_token,
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "invalid_current_password"

    changed = post_json(
        current_client,
        "/api/v1/auth/change-password",
        {
            "current_password": CURRENT_PASSWORD,
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
        current_token,
    )
    assert changed.status_code == 200
    assert current_client.get("/api/v1/session").status_code == 200
    assert other_client.get("/api/v1/session").status_code == 401
    assert not Session.objects.filter(session_key=other_key).exists()


@pytest.mark.django_db
def test_reset_request_response_does_not_enumerate_accounts_and_deduplicates_queue():
    user = User.objects.create_user(
        email="known@example.test",
        password=CURRENT_PASSWORD,
        role=UserRole.PODOLOGIST,
    )
    client, token = csrf_client()

    known = post_json(
        client,
        "/api/v1/password-reset-requests",
        {"email": user.email},
        token,
    )
    repeated = post_json(
        client,
        "/api/v1/password-reset-requests",
        {"email": user.email.upper()},
        token,
    )
    unknown = post_json(
        client,
        "/api/v1/password-reset-requests",
        {"email": "unknown@example.test"},
        token,
    )

    assert known.status_code == repeated.status_code == unknown.status_code == 202
    assert known.json() == repeated.json() == unknown.json()
    assert PasswordResetRequest.objects.filter(user=user, resolved_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_admin_queue_and_temporary_password_resolve_request_and_revoke_sessions():
    admin = User.objects.create_user(
        email="admin@example.test",
        password=CURRENT_PASSWORD,
        role=UserRole.ADMIN,
    )
    target = User.objects.create_user(
        email="employee@example.test",
        password=CURRENT_PASSWORD,
        role=UserRole.PODOLOGIST,
        first_name="Олена",
        last_name="Мельник",
    )
    reset_request = PasswordResetRequest.objects.create(user=target)
    target_client, target_token = csrf_client()
    assert login(target_client, target.email, CURRENT_PASSWORD, target_token).status_code == 200
    target_key = target_client.cookies[settings.SESSION_COOKIE_NAME].value
    admin_client, admin_token = csrf_client()
    assert login(admin_client, admin.email, CURRENT_PASSWORD, admin_token).status_code == 200

    queue = admin_client.get("/api/v1/password-reset-requests")
    assert queue.status_code == 200
    queued_request = queue.json()["requests"][0]
    assert queued_request["id"] == reset_request.pk
    assert queued_request["requested_at"]
    assert queued_request["user"] == {
        "id": target.pk,
        "email": target.email,
        "display_name": "Олена Мельник",
        "role": UserRole.PODOLOGIST,
    }

    result = post_json(
        admin_client,
        f"/api/v1/users/{target.pk}/temporary-password",
        {
            "temporary_password": TEMPORARY_PASSWORD,
            "temporary_password_confirmation": TEMPORARY_PASSWORD,
        },
        admin_client.cookies[settings.CSRF_COOKIE_NAME].value,
    )
    assert result.status_code == 200
    assert result.json()["must_change_password"] is True
    assert not Session.objects.filter(session_key=target_key).exists()
    target.refresh_from_db()
    reset_request.refresh_from_db()
    assert target.check_password(TEMPORARY_PASSWORD)
    assert target.must_change_password is True
    assert target.temporary_password_expires_at is not None
    assert reset_request.resolved_by == admin
    assert reset_request.resolved_at is not None

    forced_client, forced_token = csrf_client()
    forced_login = login(forced_client, target.email, TEMPORARY_PASSWORD, forced_token)
    assert forced_login.status_code == 200
    assert forced_login.json()["must_change_password"] is True
    assert forced_login.json()["route_ids"] == []


@pytest.mark.django_db
def test_non_admin_cannot_read_reset_queue_or_set_temporary_password():
    user = User.objects.create_user(
        email="reception@example.test",
        password=CURRENT_PASSWORD,
        role=UserRole.RECEPTION,
    )
    target = User.objects.create_user(
        email="target@example.test",
        password=CURRENT_PASSWORD,
        role=UserRole.PODOLOGIST,
    )
    client, token = csrf_client()
    assert login(client, user.email, CURRENT_PASSWORD, token).status_code == 200

    assert client.get("/api/v1/password-reset-requests").status_code == 403
    response = post_json(
        client,
        f"/api/v1/users/{target.pk}/temporary-password",
        {
            "temporary_password": TEMPORARY_PASSWORD,
            "temporary_password_confirmation": TEMPORARY_PASSWORD,
        },
        client.cookies[settings.CSRF_COOKIE_NAME].value,
    )
    assert response.status_code == 403
