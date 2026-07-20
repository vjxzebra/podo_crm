from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.clinic.models import ClinicProfile, Room

PASSWORD = "correct horse battery staple"  # noqa: S105


def create_user(*, email: str, role: str) -> User:
    return User.objects.create_user(email=email, password=PASSWORD, role=role)


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_migration_seeds_singleton_profile_and_initial_room():
    profile = ClinicProfile.objects.get(key="clinic")

    assert profile.name == "Podoria Clinic"
    assert ClinicProfile.objects.count() == 1
    assert Room.objects.filter(name="Кабінет 1", is_active=True).exists()
    with pytest.raises(IntegrityError), transaction.atomic():
        ClinicProfile.objects.create(
            key="branch",
            name="Заборонена філія",
            phone="+380000000000",
            email="branch@example.test",
            address="Адреса",
        )


@pytest.mark.django_db
def test_admin_reads_and_updates_full_profile_with_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    profile = ClinicProfile.objects.get()

    retrieved = client.get("/api/v1/clinic-profile")
    updated = client.patch(
        "/api/v1/clinic-profile",
        {
            "name": " Podoria Подологія ",
            "phone": "+380 67 111 22 33",
            "email": "clinic@podoria.test",
            "address": "Київ, вул. Прикладна, 10",
            "description": "Турботливий простір.",
            "version": profile.version,
        },
        format="json",
    )

    assert retrieved.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["name"] == "Podoria Подологія"
    assert updated.json()["phone"] == "+380 67 111 22 33"
    assert updated.json()["address"] == "Київ, вул. Прикладна, 10"
    assert updated.json()["version"] == profile.version + 1
    event = AuditEvent.objects.get(action=AuditAction.CLINIC_PROFILE_UPDATED)
    assert event.actor_id == admin.pk
    assert event.before["name"] == "Podoria Clinic"
    assert event.after["email"] == "clinic@podoria.test"


@pytest.mark.django_db
def test_profile_requires_complete_valid_values_and_rejects_stale_version():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    profile = ClinicProfile.objects.get()

    invalid = client.patch(
        "/api/v1/clinic-profile",
        {"phone": "", "email": "not-an-email", "address": "", "version": profile.version},
        format="json",
    )
    current = client.patch(
        "/api/v1/clinic-profile",
        {"name": "Нова назва", "version": profile.version},
        format="json",
    )
    stale = client.patch(
        "/api/v1/clinic-profile",
        {"name": "Втрачена зміна", "version": profile.version},
        format="json",
    )

    assert invalid.status_code == 422
    assert set(invalid.json()["fields"]) >= {"phone", "email", "address"}
    assert current.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_version"
    assert AuditEvent.objects.count() == 1


@pytest.mark.django_db
def test_admin_creates_renames_deactivates_and_reactivates_room():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)

    created = client.post("/api/v1/rooms", {"name": "Кабінет 2"}, format="json")
    room_id = created.json()["id"]
    renamed = client.patch(
        f"/api/v1/rooms/{room_id}",
        {"name": "Процедурна", "version": created.json()["version"]},
        format="json",
    )
    deactivated = client.patch(
        f"/api/v1/rooms/{room_id}",
        {"is_active": False, "version": renamed.json()["version"]},
        format="json",
    )
    reactivated = client.patch(
        f"/api/v1/rooms/{room_id}",
        {"is_active": True, "version": deactivated.json()["version"]},
        format="json",
    )
    listed = client.get("/api/v1/rooms")

    assert created.status_code == 201
    assert renamed.json()["name"] == "Процедурна"
    assert deactivated.json()["is_active"] is False
    assert reactivated.json()["is_active"] is True
    assert any(item["id"] == room_id for item in listed.json()["rooms"])
    assert list(AuditEvent.objects.order_by("occurred_at").values_list("action", flat=True)) == [
        AuditAction.ROOM_CREATED,
        AuditAction.ROOM_UPDATED,
        AuditAction.ROOM_DEACTIVATED,
        AuditAction.ROOM_REACTIVATED,
    ]


@pytest.mark.django_db
def test_room_name_conflict_and_stale_update_preserve_current_room():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    first = Room.objects.get(name="Кабінет 1")
    other = Room.objects.create(name="Кабінет 2")

    duplicate = client.post("/api/v1/rooms", {"name": "кабінет 1"}, format="json")
    updated = client.patch(
        f"/api/v1/rooms/{other.pk}",
        {"name": "Кабінет 3", "version": other.version},
        format="json",
    )
    stale = client.patch(
        f"/api/v1/rooms/{other.pk}",
        {"is_active": False, "version": other.version},
        format="json",
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "room_name_already_exists"
    assert updated.status_code == 200
    assert stale.status_code == 409
    other.refresh_from_db()
    assert other.name == "Кабінет 3"
    assert other.is_active is True
    assert Room.objects.filter(pk=first.pk).exists()


@pytest.mark.django_db
def test_rooms_are_never_deleted_through_api():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    room = Room.objects.get()
    response = authenticated_client(admin).delete(f"/api/v1/rooms/{room.pk}")

    assert response.status_code == 405
    assert Room.objects.filter(pk=room.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.PODOLOGIST, UserRole.RECEPTION])
def test_non_admin_cannot_access_settings_mutations(role):
    user = create_user(email=f"{role}@example.test", role=role)
    client = authenticated_client(user)
    profile = ClinicProfile.objects.get()
    room = Room.objects.get()

    assert client.get("/api/v1/clinic-profile").status_code == 403
    assert (
        client.patch(
            "/api/v1/clinic-profile",
            {"name": "Nope", "version": profile.version},
            format="json",
        ).status_code
        == 403
    )
    logo = SimpleUploadedFile(
        "logo.png",
        b"\x89PNG\r\n\x1a\nprivate-logo-bytes",
        content_type="image/png",
    )
    assert (
        client.put(
            "/api/v1/clinic-profile/logo",
            {"logo": logo, "version": profile.version},
            format="multipart",
        ).status_code
        == 403
    )
    assert client.get("/api/v1/rooms").status_code == 403
    assert client.post("/api/v1/rooms", {"name": "Nope"}, format="json").status_code == 403
    assert (
        client.patch(
            f"/api/v1/rooms/{room.pk}",
            {"is_active": False, "version": room.version},
            format="json",
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_logo_upload_validates_magic_bytes_and_writes_private_metadata_audit():
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    client = authenticated_client(admin)
    profile = ClinicProfile.objects.get()
    invalid = SimpleUploadedFile("logo.png", b"not a png", content_type="image/png")

    with patch("apps.clinic.storage.put_private_object") as put_object:
        rejected = client.put(
            "/api/v1/clinic-profile/logo",
            {"logo": invalid, "version": profile.version},
            format="multipart",
        )
        valid = SimpleUploadedFile(
            "logo.png",
            b"\x89PNG\r\n\x1a\nprivate-logo-bytes",
            content_type="image/png",
        )
        accepted = client.put(
            "/api/v1/clinic-profile/logo",
            {"logo": valid, "version": profile.version},
            format="multipart",
        )

    assert rejected.status_code == 422
    assert rejected.json()["code"] == "invalid_logo_content"
    assert accepted.status_code == 200
    assert accepted.json()["has_logo"] is True
    assert accepted.json()["logo_url"].startswith("/api/v1/clinic-profile/logo")
    put_object.assert_called_once()
    event = AuditEvent.objects.get(action=AuditAction.CLINIC_LOGO_UPDATED)
    assert "object_key" not in event.after
    assert event.after["logo_content_type"] == "image/png"


@pytest.mark.django_db
def test_private_logo_read_requires_authentication_but_is_available_to_employee():
    profile = ClinicProfile.objects.get()
    profile.logo_object_key = "clinic/logo/private.png"
    profile.logo_content_type = "image/png"
    profile.logo_size = 12
    profile.save()
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)

    anonymous = APIClient().get("/api/v1/clinic-profile/logo")
    with patch("apps.clinic.storage.get_private_object", return_value=b"private-logo"):
        authenticated = authenticated_client(reception).get("/api/v1/clinic-profile/logo")

    assert anonymous.status_code == 401
    assert authenticated.status_code == 200
    assert authenticated.content == b"private-logo"
    assert authenticated["Cache-Control"].startswith("private")


@pytest.mark.django_db
def test_unauthenticated_settings_endpoints_return_401():
    client = APIClient()

    assert client.get("/api/v1/clinic-profile").status_code == 401
    assert client.get("/api/v1/rooms").status_code == 401
