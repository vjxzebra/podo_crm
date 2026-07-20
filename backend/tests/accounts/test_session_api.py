import json

import pytest
from django.conf import settings
from django.test import Client

from apps.accounts.access import ROLE_ROUTE_IDS
from apps.accounts.models import User, UserRole

TEST_PASSWORD = "correct horse battery staple"  # noqa: S105


def csrf_client() -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    response = client.get("/api/v1/session")
    assert response.status_code == 401
    return client, client.cookies[settings.CSRF_COOKIE_NAME].value


def post_json(client: Client, path: str, body: dict[str, str], token: str):
    return client.post(
        path,
        data=json.dumps(body),
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role", list(UserRole.values))
def test_login_and_session_return_server_role_scope(role):
    user = User.objects.create_user(
        email=f"{role}@example.test",
        password=TEST_PASSWORD,
        role=role,
        first_name="Тест",
        last_name="Користувач",
    )
    client, token = csrf_client()

    login_response = post_json(
        client,
        "/api/v1/auth/login",
        {"email": user.email.upper(), "password": TEST_PASSWORD},
        token,
    )

    assert login_response.status_code == 200
    assert login_response.json() == {
        "user": {
            "id": user.pk,
            "email": user.email,
            "display_name": "Тест Користувач",
            "role": role,
        },
        "route_ids": list(ROLE_ROUTE_IDS[role]),
        "must_change_password": False,
        "temporary_password_expires_at": None,
        "temporary_password_expired": False,
    }
    session_cookie = login_response.cookies[settings.SESSION_COOKIE_NAME]
    assert session_cookie["httponly"] is True
    assert session_cookie["samesite"] == "Lax"
    assert bool(session_cookie["secure"]) is settings.SESSION_COOKIE_SECURE
    session_response = client.get("/api/v1/session")
    assert session_response.status_code == 200
    assert session_response.json() == login_response.json()


@pytest.mark.django_db
def test_login_rotates_anonymous_session_key():
    User.objects.create_user(
        email="admin@example.test",
        password=TEST_PASSWORD,
        role=UserRole.ADMIN,
    )
    client, token = csrf_client()
    anonymous_session = client.session
    anonymous_session["pre_auth_marker"] = True
    anonymous_session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = anonymous_session.session_key
    previous_key = anonymous_session.session_key

    response = post_json(
        client,
        "/api/v1/auth/login",
        {"email": "admin@example.test", "password": TEST_PASSWORD},
        token,
    )

    assert response.status_code == 200
    assert client.cookies[settings.SESSION_COOKIE_NAME].value != previous_key


@pytest.mark.django_db
def test_login_rejects_missing_csrf_token():
    User.objects.create_user(
        email="admin@example.test",
        password=TEST_PASSWORD,
        role=UserRole.ADMIN,
    )
    client = Client(enforce_csrf_checks=True)

    response = client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": "admin@example.test", "password": TEST_PASSWORD}),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert response.json()["fields"] == {}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("inactive", "email"), [(False, "not-an-email"), (True, "admin@example.test")]
)
def test_login_uses_one_generic_error_for_invalid_credentials(inactive, email):
    User.objects.create_user(
        email="admin@example.test",
        password=TEST_PASSWORD,
        role=UserRole.ADMIN,
        is_active=not inactive,
    )
    client, token = csrf_client()

    response = post_json(
        client,
        "/api/v1/auth/login",
        {
            "email": email,
            "password": "wrong password",
        },
        token,
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert response.json()["message"] == "Неправильний email або пароль."
    assert response.json()["fields"] == {}


@pytest.mark.django_db
def test_logout_requires_csrf_and_flushes_session():
    User.objects.create_user(
        email="admin@example.test",
        password=TEST_PASSWORD,
        role=UserRole.ADMIN,
    )
    client, token = csrf_client()
    assert (
        post_json(
            client,
            "/api/v1/auth/login",
            {"email": "admin@example.test", "password": TEST_PASSWORD},
            token,
        ).status_code
        == 200
    )

    without_csrf = client.post("/api/v1/auth/logout")
    assert without_csrf.status_code == 403
    current_token = client.cookies[settings.CSRF_COOKIE_NAME].value
    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRFToken": current_token},
    )

    assert logout_response.status_code == 204
    session_response = client.get("/api/v1/session")
    assert session_response.status_code == 401
    assert session_response.headers["WWW-Authenticate"] == "Session"
