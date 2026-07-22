from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from PIL import Image

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction
from apps.visits.models import (
    Visit,
    VisitPhoto,
    VisitPhotoIntentStatus,
    VisitPhotoKind,
    VisitPhotoUploadIntent,
    VisitStatus,
)
from apps.visits.tasks import cleanup_expired_visit_photo_intents
from tests.scheduling.test_create_appointment import authenticated_client, create_user
from tests.visits.test_visit_start_and_draft import arrived_appointment, start


def started_visit(*, actor: User) -> Visit:
    appointment = arrived_appointment(actor=actor)
    response = start(authenticated_client(actor), appointment)
    assert response.status_code == 201, response.json()
    return Visit.objects.get(pk=response.json()["id"])


def image_upload(
    *,
    name: str = "clinical-before.jpg",
    content_type: str = "image/jpeg",
    image_format: str = "JPEG",
    include_exif: bool = False,
) -> SimpleUploadedFile:
    image = Image.new("RGB", (48, 32), color=(118, 75, 162))
    output = BytesIO()
    exif = Image.Exif()
    if include_exif:
        exif[270] = "private camera metadata"
    image.save(output, format=image_format, exif=exif)
    return SimpleUploadedFile(name, output.getvalue(), content_type=content_type)


def create_intent(*, actor: User, visit: Visit, kind: str = VisitPhotoKind.BEFORE):
    return authenticated_client(actor).post(
        f"/api/v1/visits/{visit.pk}/photos/upload-intents",
        {"kind": kind},
        format="json",
    )


def finalize(*, actor: User, visit: Visit, intent_id: str, upload: SimpleUploadedFile):
    return authenticated_client(actor).post(
        f"/api/v1/visits/{visit.pk}/photos",
        {"intent_id": intent_id, "photo": upload},
        format="multipart",
    )


@pytest.mark.django_db
def test_photo_intent_finalize_is_private_canonical_audited_and_replay_safe(
    django_capture_on_commit_callbacks,
) -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    visit = started_visit(actor=admin)
    intent = create_intent(actor=admin, visit=visit)

    with (
        patch("apps.visits.photo_services.object_storage.put_private_object") as put_object,
        patch("apps.visits.photo_services._queue_preview") as queue_preview,
        django_capture_on_commit_callbacks(execute=True),
    ):
        created = finalize(
            actor=admin,
            visit=visit,
            intent_id=intent.json()["id"],
            upload=image_upload(include_exif=True),
        )

    assert intent.status_code == 201
    assert intent.json()["kind"] == VisitPhotoKind.BEFORE
    assert intent.json()["max_bytes"] == 10 * 1024 * 1024
    assert intent.json()["allowed_content_types"] == [
        "image/jpeg",
        "image/png",
        "image/webp",
    ]
    assert created.status_code == 201
    assert created.json()["kind"] == VisitPhotoKind.BEFORE
    assert created.json()["preview_status"] == "PROCESSING"
    assert created.json()["image_url"].startswith("/api/v1/visit-photo-content?token=")
    assert "object_key" not in created.json()
    stored = put_object.call_args.kwargs["content"]
    with Image.open(BytesIO(stored)) as canonical:
        assert canonical.size == (48, 32)
        assert len(canonical.getexif()) == 0
    photo = VisitPhoto.objects.get()
    queue_preview.assert_called_once_with(photo.pk)
    event = AuditEvent.objects.get(action=AuditAction.VISIT_PHOTO_ADDED)
    assert event.after["kind"] == VisitPhotoKind.BEFORE
    assert "object_key" not in event.after

    with patch("apps.visits.photo_services.object_storage.put_private_object") as replay_put:
        replay = finalize(
            actor=admin,
            visit=visit,
            intent_id=intent.json()["id"],
            upload=SimpleUploadedFile("ignored.heic", b"ignored", content_type="image/heic"),
        )
    assert replay.status_code == 200
    assert replay.json()["id"] == created.json()["id"]
    replay_put.assert_not_called()
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_PHOTO_ADDED).count() == 1


@pytest.mark.django_db
def test_photo_validation_rejects_spoofed_type_oversize_and_eleventh_photo() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    visit = started_visit(actor=admin)
    spoof_intent = create_intent(actor=admin, visit=visit)
    spoofed = finalize(
        actor=admin,
        visit=visit,
        intent_id=spoof_intent.json()["id"],
        upload=image_upload(
            name="spoofed.jpg",
            content_type="image/jpeg",
            image_format="PNG",
        ),
    )
    heic_intent = create_intent(actor=admin, visit=visit, kind=VisitPhotoKind.AFTER)
    heic = finalize(
        actor=admin,
        visit=visit,
        intent_id=heic_intent.json()["id"],
        upload=SimpleUploadedFile("photo.heic", b"not-heic", content_type="image/heic"),
    )
    oversize_intent = create_intent(actor=admin, visit=visit, kind=VisitPhotoKind.AFTER)
    with override_settings(VISIT_PHOTO_MAX_BYTES=8):
        oversize = finalize(
            actor=admin,
            visit=visit,
            intent_id=oversize_intent.json()["id"],
            upload=SimpleUploadedFile("large.png", b"123456789", content_type="image/png"),
        )

    for index in range(10):
        VisitPhoto.objects.create(
            visit=visit,
            kind=VisitPhotoKind.BEFORE,
            object_key=f"visits/{visit.pk}/photos/{index}.jpg",
            content_type="image/jpeg",
            size=100,
            width=10,
            height=10,
            original_name=f"before-{index}.jpg",
            created_by=admin,
        )
    eleventh = create_intent(actor=admin, visit=visit)

    assert spoofed.status_code == 422
    assert spoofed.json()["code"] == "invalid_visit_photo_content"
    assert heic.status_code == 422
    assert heic.json()["code"] == "invalid_visit_photo_type"
    assert oversize.status_code == 422
    assert oversize.json()["code"] == "visit_photo_too_large"
    assert eleventh.status_code == 422
    assert eleventh.json()["code"] == "visit_photo_limit_reached"


@pytest.mark.django_db
def test_photo_metadata_and_signed_content_enforce_role_and_visit_scope() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    foreign = create_user(email="foreign@example.test", role=UserRole.PODOLOGIST)
    visit = started_visit(actor=admin)
    intent = create_intent(actor=admin, visit=visit)
    with patch("apps.visits.photo_services.object_storage.put_private_object"):
        created = finalize(
            actor=admin,
            visit=visit,
            intent_id=intent.json()["id"],
            upload=image_upload(),
        )
    detail_url = f"/api/v1/visits/{visit.pk}/photos/{created.json()['id']}"
    content_url = created.json()["image_url"]

    assert authenticated_client(reception).get(detail_url).status_code == 403
    assert authenticated_client(foreign).get(detail_url).status_code == 404
    assert authenticated_client(visit.specialist).get(detail_url).status_code == 200
    assert authenticated_client(reception).get(content_url).status_code == 403
    assert authenticated_client(foreign).get(content_url).status_code == 404

    with patch(
        "apps.visits.photo_services.object_storage.get_private_object",
        return_value=b"private-photo-bytes",
    ):
        allowed = authenticated_client(visit.specialist).get(content_url)
    assert allowed.status_code == 200
    assert allowed.content == b"private-photo-bytes"
    assert allowed["Cache-Control"] == "private, no-store"


@pytest.mark.django_db
def test_draft_delete_is_audited_and_completed_photo_is_immutable(
    django_capture_on_commit_callbacks,
) -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    visit = started_visit(actor=admin)
    photo = VisitPhoto.objects.create(
        visit=visit,
        kind=VisitPhotoKind.AFTER,
        object_key=f"visits/{visit.pk}/photos/after.jpg",
        preview_object_key=f"visits/{visit.pk}/previews/after.jpg",
        preview_content_type="image/jpeg",
        content_type="image/jpeg",
        size=100,
        width=10,
        height=10,
        original_name="after.jpg",
        created_by=admin,
    )
    with (
        patch("apps.visits.photo_services._queue_object_cleanup") as queue_cleanup,
        django_capture_on_commit_callbacks(execute=True),
    ):
        deleted = authenticated_client(admin).delete(f"/api/v1/visits/{visit.pk}/photos/{photo.pk}")

    assert deleted.status_code == 204
    assert not VisitPhoto.objects.filter(pk=photo.pk).exists()
    queue_cleanup.assert_called_once_with((photo.object_key, photo.preview_object_key))
    assert AuditEvent.objects.filter(action=AuditAction.VISIT_PHOTO_DELETED).count() == 1

    immutable = VisitPhoto.objects.create(
        visit=visit,
        kind=VisitPhotoKind.AFTER,
        object_key=f"visits/{visit.pk}/photos/immutable.jpg",
        content_type="image/jpeg",
        size=100,
        width=10,
        height=10,
        original_name="immutable.jpg",
        created_by=admin,
    )
    visit.status = VisitStatus.COMPLETED
    visit.save(update_fields=("status", "updated_at"))
    rejected = authenticated_client(admin).delete(
        f"/api/v1/visits/{visit.pk}/photos/{immutable.pk}"
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "visit_not_editable"
    assert VisitPhoto.objects.filter(pk=immutable.pk).exists()


@pytest.mark.django_db
def test_finalize_rolls_back_database_and_removes_object_when_audit_fails() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    visit = started_visit(actor=admin)
    intent = create_intent(actor=admin, visit=visit)

    with (
        patch("apps.visits.photo_services.object_storage.put_private_object"),
        patch("apps.visits.photo_services.object_storage.delete_private_object") as delete_object,
        patch(
            "apps.visits.photo_services.record_audit_event",
            side_effect=RuntimeError("audit down"),
        ),
    ):
        response = finalize(
            actor=admin,
            visit=visit,
            intent_id=intent.json()["id"],
            upload=image_upload(),
        )

    assert response.status_code == 500
    assert VisitPhoto.objects.count() == 0
    pending = VisitPhotoUploadIntent.objects.get(pk=intent.json()["id"])
    assert pending.status == VisitPhotoIntentStatus.PENDING
    delete_object.assert_called_once()
    assert not AuditEvent.objects.filter(action=AuditAction.VISIT_PHOTO_ADDED).exists()


@pytest.mark.django_db
def test_expired_intent_cleanup_keeps_recent_and_finalized_rows() -> None:
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)
    visit = started_visit(actor=admin)
    old = VisitPhotoUploadIntent.objects.create(
        visit=visit,
        kind=VisitPhotoKind.BEFORE,
        created_by=admin,
        expires_at=timezone.now() - timedelta(hours=25),
    )
    recent = VisitPhotoUploadIntent.objects.create(
        visit=visit,
        kind=VisitPhotoKind.AFTER,
        created_by=admin,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    finalized = VisitPhotoUploadIntent.objects.create(
        visit=visit,
        kind=VisitPhotoKind.AFTER,
        status=VisitPhotoIntentStatus.FINALIZED,
        created_by=admin,
        expires_at=timezone.now() - timedelta(hours=25),
    )
    VisitPhotoUploadIntent.objects.filter(pk__in=(old.pk, finalized.pk)).update(
        created_at=timezone.now() - timedelta(hours=25)
    )

    deleted = cleanup_expired_visit_photo_intents.run()

    assert deleted == 1
    assert not VisitPhotoUploadIntent.objects.filter(pk=old.pk).exists()
    assert VisitPhotoUploadIntent.objects.filter(pk=recent.pk).exists()
    assert VisitPhotoUploadIntent.objects.filter(pk=finalized.pk).exists()


@pytest.mark.django_db
def test_openapi_exposes_private_visit_photo_lifecycle() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    intent_path = schema["paths"]["/api/v1/visits/{visit_id}/photos/upload-intents"]
    finalize_path = schema["paths"]["/api/v1/visits/{visit_id}/photos"]
    detail_path = schema["paths"]["/api/v1/visits/{visit_id}/photos/{photo_id}"]
    response_schema = schema["components"]["schemas"]["VisitResponse"]

    assert intent_path["post"]["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisitPhotoUploadIntent"
    }
    assert "multipart/form-data" in finalize_path["post"]["requestBody"]["content"]
    assert finalize_path["post"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisitPhoto"
    }
    assert finalize_path["post"]["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VisitPhoto"
    }
    assert "delete" in detail_path
    assert response_schema["properties"]["photos"]["type"] == "array"
