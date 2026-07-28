import re
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction, AuditSection
from apps.booking_requests.models import (
    BookingRequest,
    BookingRequestImmutableError,
    BookingRequestSource,
)
from apps.booking_requests.services import create_booking_request

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


def create_request(
    *,
    source: str = BookingRequestSource.INSTAGRAM,
    client_name: str = "Марія Бондар",
    phone: str = "067 123 45 67",
    service: str = "Консультація подолога",
    contact_handle: str = "@maria",
    message: str = "Хочу записатися після обіду.",
) -> BookingRequest:
    return create_booking_request(
        data={
            "source": source,
            "client_name": client_name,
            "phone": phone,
            "service": service,
            "contact_handle": contact_handle,
            "message": message,
        },
        correlation_id="booking-request-test",
    )


@pytest.mark.django_db
def test_create_service_normalizes_fields_and_records_pii_safe_audit() -> None:
    item = create_booking_request(
        data={
            "source": BookingRequestSource.WEBSITE,
            "client_name": "  Олена Коваль  ",
            "phone": "  +38 (067) 222-33-44  ",
            "service": "  Медичний педикюр  ",
            "contact_handle": "  @olena  ",
            "message": "  Потрібен запис у п'ятницю.  ",
            "external_reference": "  lead-17  ",
        },
        correlation_id="create-safe-audit",
    )

    assert re.fullmatch(r"REQ-[0-9A-F]{10}", item.public_number)
    assert item.client_name == "Олена Коваль"
    assert item.phone == "+38 (067) 222-33-44"
    assert item.phone_normalized == "+380672223344"
    assert item.service == "Медичний педикюр"
    assert item.contact_handle == "@olena"
    assert item.message == "Потрібен запис у п'ятницю."
    assert item.external_reference == "lead-17"
    event = AuditEvent.objects.get(action=AuditAction.BOOKING_REQUEST_CREATED)
    assert event.section == AuditSection.BOOKING_REQUESTS
    assert event.actor is None
    assert event.actor_role == "integration"
    assert event.object_label == item.public_number
    assert "phone" not in event.after
    assert "service" not in event.after
    assert "client_name" not in event.after
    assert "contact_handle" not in event.after
    assert "message" not in event.after


@pytest.mark.django_db
def test_all_customer_form_fields_are_optional() -> None:
    item = create_booking_request(
        data={"source": BookingRequestSource.WEBSITE},
        correlation_id="optional-form-fields",
    )

    assert item.client_name == ""
    assert item.phone == ""
    assert item.phone_normalized == ""
    assert item.service == ""
    assert item.message == ""


@pytest.mark.django_db
def test_contact_payload_is_immutable_after_create() -> None:
    item = create_request()
    item.client_name = "Інше ім'я"

    with pytest.raises(BookingRequestImmutableError):
        item.save()
    with pytest.raises(BookingRequestImmutableError):
        BookingRequest.objects.filter(pk=item.pk).update(phone="+380501112233")


@pytest.mark.django_db
def test_deferred_field_load_does_not_recurse_and_keeps_immutable_guard() -> None:
    item = create_request()

    deferred = BookingRequest.objects.only("status").get(pk=item.pk)

    assert deferred.status == "NEW"
    assert "client_name" in deferred.get_deferred_fields()
    deferred.client_name = "Інше ім'я"
    with pytest.raises(BookingRequestImmutableError):
        deferred.save()


@pytest.mark.django_db
def test_admin_and_reception_list_filter_search_and_counts() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    instagram = create_request()
    website = create_request(
        source=BookingRequestSource.WEBSITE,
        client_name="Олена Коваль",
        phone="+380 50 111 22 33",
        contact_handle="",
    )
    processed = authenticated_client(admin).post(
        f"/api/v1/booking-requests/{website.pk}/process",
        {"version": 1},
        format="json",
    )
    assert processed.status_code == 200

    default_response = authenticated_client(reception).get("/api/v1/booking-requests")
    filtered_response = authenticated_client(admin).get(
        "/api/v1/booking-requests",
        {"status": "ALL", "source": "WEBSITE", "search": "0501112233"},
    )

    assert default_response.status_code == 200
    default_body = default_response.json()
    assert [item["id"] for item in default_body["booking_requests"]] == [str(instagram.pk)]
    assert default_body["counts"] == {"new": 1, "processed": 1, "total": 2}
    assert default_body["next_cursor"] is None
    assert filtered_response.status_code == 200
    filtered_body = filtered_response.json()
    assert [item["id"] for item in filtered_body["booking_requests"]] == [str(website.pk)]
    assert filtered_body["counts"] == {"new": 1, "processed": 1, "total": 2}


@pytest.mark.django_db
def test_list_uses_stable_cursor_pagination() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    for index in range(31):
        create_request(
            client_name=f"Клієнт {index:02d}",
            phone=f"+38067123{index:04d}",
            contact_handle="",
            message="",
        )

    first = authenticated_client(admin).get(
        "/api/v1/booking-requests",
        {"status": "ALL"},
    )
    first_body = first.json()
    second = authenticated_client(admin).get(
        "/api/v1/booking-requests",
        {"status": "ALL", "cursor": first_body["next_cursor"]},
    )

    assert first.status_code == second.status_code == 200
    assert len(first_body["booking_requests"]) == 30
    assert first_body["counts"] == {"new": 31, "processed": 0, "total": 31}
    assert first_body["next_cursor"]
    assert len(second.json()["booking_requests"]) == 1
    assert second.json()["next_cursor"] is None
    first_ids = {item["id"] for item in first_body["booking_requests"]}
    second_ids = {item["id"] for item in second.json()["booking_requests"]}
    assert first_ids.isdisjoint(second_ids)


@pytest.mark.django_db
def test_detail_returns_full_projection_and_generic_not_found() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    item = create_request()
    client = authenticated_client(reception)

    response = client.get(f"/api/v1/booking-requests/{item.pk}")
    missing = client.get("/api/v1/booking-requests/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 200
    body = response.json()
    assert body["public_number"] == item.public_number
    assert body["source_label"] == "Instagram"
    assert body["status"] == "NEW"
    assert body["status_label"] == "Нова"
    assert body["client_name"] == "Марія Бондар"
    assert body["service"] == "Консультація подолога"
    assert body["processed_at"] is None
    assert body["version"] == 1
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


@pytest.mark.django_db
def test_process_is_versioned_audited_and_terminally_idempotent() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    item = create_request()
    client = authenticated_client(admin)

    first = client.post(
        f"/api/v1/booking-requests/{item.pk}/process",
        {"version": 1},
        format="json",
    )
    repeated_with_stale_version = client.post(
        f"/api/v1/booking-requests/{item.pk}/process",
        {"version": 1},
        format="json",
    )

    assert first.status_code == repeated_with_stale_version.status_code == 200
    first_body = first.json()
    repeated_body = repeated_with_stale_version.json()
    assert first_body["status"] == "PROCESSED"
    assert first_body["processed_by_display_name"] == admin.display_name
    assert first_body["processed_at"] is not None
    assert first_body["version"] == 2
    assert repeated_body == first_body
    events = AuditEvent.objects.filter(action=AuditAction.BOOKING_REQUEST_PROCESSED)
    assert events.count() == 1
    event = events.get()
    assert event.actor == admin
    assert event.before["status"] == "NEW"
    assert event.after["status"] == "PROCESSED"
    assert "phone" not in event.before
    assert "message" not in event.after


@pytest.mark.django_db
def test_process_rejects_stale_new_version_and_unknown_body_fields() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    item = create_request()
    client = authenticated_client(reception)

    stale = client.post(
        f"/api/v1/booking-requests/{item.pk}/process",
        {"version": 2},
        format="json",
    )
    unknown = client.post(
        f"/api/v1/booking-requests/{item.pk}/process",
        {"version": 1, "note": "extra"},
        format="json",
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"
    assert stale.json()["fields"]["version"]
    assert unknown.status_code == 422
    assert unknown.json()["fields"]["note"] == ["Невідоме поле."]
    item.refresh_from_db()
    assert item.status == "NEW"
    assert item.version == 1
    assert not AuditEvent.objects.filter(action=AuditAction.BOOKING_REQUEST_PROCESSED).exists()


@pytest.mark.django_db
def test_role_routes_and_backend_permissions_match_contract() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    item = create_request()

    admin_session = authenticated_client(admin).get("/api/v1/session").json()
    reception_session = authenticated_client(reception).get("/api/v1/session").json()
    podologist_client = authenticated_client(podologist)
    podologist_session = podologist_client.get("/api/v1/session").json()

    assert "booking-requests" in admin_session["route_ids"]
    assert "booking-requests" in reception_session["route_ids"]
    assert "booking-requests" not in podologist_session["route_ids"]
    assert podologist_client.get("/api/v1/booking-requests").status_code == 403
    assert (
        podologist_client.post(
            f"/api/v1/booking-requests/{item.pk}/process",
            {"version": 1},
            format="json",
        ).status_code
        == 403
    )
    assert APIClient().get("/api/v1/booking-requests").status_code == 401


@pytest.mark.django_db
def test_preferred_at_is_serialized_as_aware_datetime() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    preferred_at = timezone.now() + timedelta(days=2)
    item = create_booking_request(
        data={
            "source": BookingRequestSource.FACEBOOK,
            "client_name": "Ірина Шевченко",
            "phone": "+380931112233",
            "preferred_at": preferred_at,
        },
        correlation_id="preferred-at",
    )

    response = authenticated_client(admin).get(f"/api/v1/booking-requests/{item.pk}")

    assert response.status_code == 200
    assert response.json()["preferred_at"] is not None
