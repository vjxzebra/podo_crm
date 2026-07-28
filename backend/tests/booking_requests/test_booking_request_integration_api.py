from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.cache import cache
from django.db import close_old_connections, connections
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.booking_requests.authentication import booking_request_api_token_digest
from apps.booking_requests.models import (
    BookingRequest,
    BookingRequestApiCredential,
    BookingRequestSubmission,
)

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


def rotate_token(actor: User, *, version: int = 0) -> str:
    response = authenticated_client(actor).post(
        "/api/v1/booking-request-integration/token/rotate",
        {"version": version, "confirm": True},
        format="json",
    )
    assert response.status_code == 200
    return str(response.json()["token"])


def integration_client(token: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.django_db
def test_admin_reads_unconfigured_metadata_and_reception_is_forbidden() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)

    response = authenticated_client(admin).get("/api/v1/booking-request-integration")
    forbidden = authenticated_client(reception).get("/api/v1/booking-request-integration")

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response.json() == {
        "is_configured": False,
        "token_hint": "",
        "rotated_at": None,
        "rotated_by_display_name": "",
        "version": 0,
    }
    assert "token" not in response.json()
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_rotation_is_digest_only_versioned_no_store_and_pii_safe_audited() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    BookingRequestApiCredential.objects.all().delete()

    response = client.post(
        "/api/v1/booking-request-integration/token/rotate",
        {"version": 0, "confirm": True},
        format="json",
    )

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    body = response.json()
    token = body["token"]
    assert token.startswith("podo_br_")
    assert body["token_hint"] == token[-6:]
    assert body["version"] == 1
    credential = BookingRequestApiCredential.objects.get()
    assert credential.token_digest == booking_request_api_token_digest(token)
    assert token not in credential.token_digest
    event = AuditEvent.objects.get(action=AuditAction.BOOKING_REQUEST_API_TOKEN_ROTATED)
    assert event.actor == admin
    assert event.object_type == "booking_request_api_credential"
    assert "digest" not in str(event.before).lower()
    assert token not in str(event.before)
    assert token not in str(event.after)

    stale = client.post(
        "/api/v1/booking-request-integration/token/rotate",
        {"version": 0, "confirm": True},
        format="json",
    )
    unconfirmed = client.post(
        "/api/v1/booking-request-integration/token/rotate",
        {"version": 1, "confirm": False},
        format="json",
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"
    assert unconfirmed.status_code == 422
    assert unconfirmed.json()["fields"]["confirm"]


@pytest.mark.django_db
def test_external_create_accepts_optional_form_fields_and_exact_replay() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    token = rotate_token(admin)
    client = integration_client(token)

    first = client.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="website-form-1",
    )
    replay = client.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="website-form-1",
    )

    assert first.status_code == 201
    assert first["Cache-Control"] == "no-store"
    assert replay.status_code == 200
    assert replay["Idempotent-Replayed"] == "true"
    assert replay.json() == first.json()
    assert set(first.json()) == {"id", "public_number", "status", "created_at"}
    item = BookingRequest.objects.get(pk=first.json()["id"])
    assert item.client_name == ""
    assert item.phone == ""
    assert item.service == ""
    assert item.message == ""
    assert BookingRequest.objects.count() == 1
    assert BookingRequestSubmission.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.BOOKING_REQUEST_CREATED).count() == 1


@pytest.mark.django_db
def test_external_create_normalizes_payload_and_rejects_key_reuse_with_new_body() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    token = rotate_token(admin)
    client = integration_client(token)
    payload = {
        "source": "INSTAGRAM",
        "client_name": "  Олена Коваль  ",
        "phone": " 067 123 45 67 ",
        "service": "  Консультація  ",
        "contact_handle": "  @olena  ",
        "message": "  Після обіду  ",
        "external_reference": "  lead-15  ",
    }

    response = client.post(
        "/api/v1/integrations/booking-requests",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="instagram-lead-15",
    )
    mismatch = client.post(
        "/api/v1/integrations/booking-requests",
        {**payload, "message": "Інший коментар"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="instagram-lead-15",
    )

    assert response.status_code == 201
    item = BookingRequest.objects.get(pk=response.json()["id"])
    assert item.client_name == "Олена Коваль"
    assert item.phone_normalized == "+380671234567"
    assert item.service == "Консультація"
    assert item.contact_handle == "@olena"
    assert item.message == "Після обіду"
    assert item.external_reference == "lead-15"
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "idempotency_payload_mismatch"
    assert BookingRequest.objects.count() == 1


@pytest.mark.django_db
def test_external_create_has_generic_bearer_and_strict_validation_errors() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    token = rotate_token(admin)
    valid_client = integration_client(token)

    missing = APIClient().post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="missing-auth",
    )
    malformed = APIClient()
    malformed.credentials(HTTP_AUTHORIZATION="Basic credentials")
    malformed_response = malformed.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="malformed-auth",
    )
    missing_key = valid_client.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
    )
    unknown = valid_client.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE", "extra": "not-allowed"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="unknown-field",
    )
    invalid_phone = valid_client.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE", "phone": "123"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="invalid-phone",
    )

    for response in (missing, malformed_response):
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_bearer_token"
        assert response["WWW-Authenticate"] == "Bearer"
    assert missing_key.status_code == 422
    assert missing_key.json()["code"] == "idempotency_key_required"
    assert unknown.status_code == 422
    assert unknown.json()["fields"]["extra"] == ["Невідоме поле."]
    assert invalid_phone.status_code == 422
    assert invalid_phone.json()["fields"]["phone"]
    assert not BookingRequest.objects.exists()


@pytest.mark.django_db
def test_rotation_immediately_invalidates_old_token() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    old_token = rotate_token(admin)
    new_token = rotate_token(admin, version=1)

    old_response = integration_client(old_token).post(
        "/api/v1/integrations/booking-requests",
        {"source": "FACEBOOK"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="old-token",
    )
    new_response = integration_client(new_token).post(
        "/api/v1/integrations/booking-requests",
        {"source": "FACEBOOK"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="new-token",
    )

    assert old_response.status_code == 401
    assert old_response.json()["code"] == "invalid_bearer_token"
    assert new_response.status_code == 201


@pytest.mark.django_db
@override_settings(
    BOOKING_REQUEST_API_RATE_LIMIT_ATTEMPTS=1,
    BOOKING_REQUEST_API_RATE_LIMIT_WINDOW_SECONDS=60,
    BOOKING_REQUEST_API_INVALID_ATTEMPTS=1,
    BOOKING_REQUEST_API_INVALID_WINDOW_SECONDS=60,
)
def test_valid_and_invalid_rate_limits_include_retry_after() -> None:
    cache.clear()
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    token = rotate_token(admin)
    client = integration_client(token)

    allowed = client.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="rate-allowed",
    )
    throttled = client.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="rate-throttled",
    )
    invalid = integration_client("invalid-token")
    first_invalid = invalid.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="invalid-one",
        REMOTE_ADDR="198.51.100.20",
    )
    second_invalid = invalid.post(
        "/api/v1/integrations/booking-requests",
        {"source": "WEBSITE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="invalid-two",
        REMOTE_ADDR="198.51.100.20",
    )

    assert allowed.status_code == 201
    assert throttled.status_code == 429
    assert throttled.json()["code"] == "rate_limit_exceeded"
    assert int(throttled["Retry-After"]) > 0
    assert first_invalid.status_code == 401
    assert second_invalid.status_code == 429
    assert int(second_invalid["Retry-After"]) > 0
    cache.clear()


@pytest.mark.django_db(transaction=True)
def test_concurrent_exact_replay_creates_one_booking_request() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    token = rotate_token(admin)

    def submit() -> tuple[int, str]:
        close_old_connections()
        try:
            response = integration_client(token).post(
                "/api/v1/integrations/booking-requests",
                {"source": "WEBSITE", "external_reference": "concurrent-form"},
                format="json",
                HTTP_IDEMPOTENCY_KEY="concurrent-form",
            )
            return response.status_code, str(response.json()["id"])
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: submit(), range(2)))

    assert sorted(status_code for status_code, _ in results) == [200, 201]
    assert len({booking_request_id for _, booking_request_id in results}) == 1
    assert BookingRequest.objects.count() == 1
    assert BookingRequestSubmission.objects.count() == 1
