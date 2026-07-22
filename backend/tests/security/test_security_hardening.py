import json
import logging
import sys
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import Client, override_settings
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.accounts.session_security import SESSION_ISSUED_AT_KEY, SESSION_LAST_SEEN_AT_KEY
from apps.audit.services import REDACTED, redact_snapshot
from config.logging import JsonFormatter

PASSWORD = "correct horse battery staple"  # noqa: S105
WRONG_PASSWORD_ONE = "wrong-one"  # noqa: S105


def csrf_client() -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    response = client.get("/api/v1/session")
    assert response.status_code == 401
    return client, client.cookies[settings.CSRF_COOKIE_NAME].value


def login(client: Client, token: str, *, email: str, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )


@pytest.mark.django_db
@override_settings(
    LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS=2,
    LOGIN_RATE_LIMIT_IP_ATTEMPTS=20,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS=900,
)
def test_login_rate_limit_is_generic_sets_retry_after_and_recovers_after_success():
    cache.clear()
    user = User.objects.create_user(
        email="admin@example.test",
        password=PASSWORD,
        role=UserRole.ADMIN,
    )
    client, token = csrf_client()

    with patch("apps.accounts.login_security.cache.add", wraps=cache.add) as cache_add:
        first = login(client, token, email=user.email, password=WRONG_PASSWORD_ONE)
        success = login(client, token, email=user.email, password=PASSWORD)
    assert first.status_code == 401
    assert success.status_code == 200

    client, token = csrf_client()
    for password in ("wrong-two", "wrong-three"):
        rejected = login(client, token, email=user.email, password=password)
        assert rejected.status_code == 401
        assert rejected.json()["code"] == "invalid_credentials"

    with patch("apps.accounts.views.authenticate") as authenticate:
        blocked = login(client, token, email=user.email, password=PASSWORD)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "login_rate_limited"
    assert blocked.json()["fields"] == {}
    assert 1 <= int(blocked.headers["Retry-After"]) <= 900
    authenticate.assert_not_called()
    cache_key = cache_add.call_args.args[0]
    assert user.email not in cache_key
    cache.clear()


@pytest.mark.django_db
@pytest.mark.parametrize("expired_by", ["idle", "absolute"])
@override_settings(SESSION_IDLE_TIMEOUT_SECONDS=120, SESSION_ABSOLUTE_TIMEOUT_SECONDS=3600)
def test_session_expiry_flushes_server_state_and_returns_safe_401(expired_by):
    user = User.objects.create_user(
        email=f"{expired_by}@example.test",
        password=PASSWORD,
        role=UserRole.ADMIN,
    )
    client, token = csrf_client()
    assert login(client, token, email=user.email).status_code == 200
    session = client.session
    session_key = session.session_key
    now = timezone.now().timestamp()
    session[SESSION_ISSUED_AT_KEY] = now - (3601 if expired_by == "absolute" else 60)
    session[SESSION_LAST_SEEN_AT_KEY] = now - (121 if expired_by == "idle" else 60)
    session.save()

    response = client.get("/api/v1/session")

    assert response.status_code == 401
    assert response.json() == {
        "code": "session_expired",
        "message": "Сесію завершено. Увійдіть знову, щоб продовжити роботу.",
        "fields": {},
        "correlation_id": response.headers["X-Request-ID"],
    }
    assert response.headers["WWW-Authenticate"] == "Session"
    assert response.headers["Cache-Control"] == "no-store"
    assert session_key is not None
    assert not Session.objects.filter(session_key=session_key).exists()


@pytest.mark.django_db
@override_settings(SESSION_IDLE_TIMEOUT_SECONDS=120, SESSION_ABSOLUTE_TIMEOUT_SECONDS=3600)
def test_active_session_refreshes_idle_timestamp_without_moving_absolute_start():
    user = User.objects.create_user(
        email="active@example.test",
        password=PASSWORD,
        role=UserRole.RECEPTION,
    )
    client, token = csrf_client()
    assert login(client, token, email=user.email).status_code == 200
    session = client.session
    issued_at = session[SESSION_ISSUED_AT_KEY]
    old_last_seen = timezone.now().timestamp() - 60
    session[SESSION_LAST_SEEN_AT_KEY] = old_last_seen
    session.save()

    response = client.get("/api/v1/session")
    refreshed = client.session

    assert response.status_code == 200
    assert refreshed[SESSION_ISSUED_AT_KEY] == issued_at
    assert refreshed[SESSION_LAST_SEEN_AT_KEY] > old_last_seen


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SECURE_HSTS_SECONDS=31_536_000,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
)
def test_direct_backend_security_headers_and_private_api_cache_policy():
    response = Client().get("/api/v1/session", secure=True)

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["Strict-Transport-Security"] == ("max-age=31536000; includeSubDomains")
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Permissions-Policy"].startswith("camera=()")


def test_audit_and_json_logs_redact_sensitive_values():
    snapshot = redact_snapshot(
        {
            "password": "plain-password",
            "nested": {"signed_url": "https://storage.test/private?token=raw-token"},
            "safe": "visible",
        }
    )
    assert snapshot == {
        "password": REDACTED,
        "nested": {"signed_url": REDACTED},
        "safe": "visible",
    }

    try:
        raise RuntimeError("token=raw-token Authorization: Bearer raw-bearer")
    except RuntimeError:
        record = logging.LogRecord(
            name="podoria.security",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="password=plain-password cookie=session-cookie",
            args=(),
            exc_info=sys.exc_info(),
        )
    rendered = JsonFormatter().format(record)

    assert "plain-password" not in rendered
    assert "session-cookie" not in rendered
    assert "raw-token" not in rendered
    assert "raw-bearer" not in rendered
    assert rendered.count(REDACTED) >= 4
