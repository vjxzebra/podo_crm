from datetime import timedelta
from uuid import UUID, uuid4

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.visits.models import (
    VisitPhoto,
    VisitPhotoIntentStatus,
    VisitPhotoPreviewStatus,
    VisitPhotoUploadIntent,
)
from apps.visits.photo_services import build_photo_preview
from config import object_storage


def _delete_object_safely(object_key: str) -> None:
    try:
        object_storage.delete_private_object(object_key=object_key)
    except Exception:
        return


@shared_task(name="apps.visits.tasks.generate_visit_photo_preview")
def generate_visit_photo_preview(photo_id: str) -> None:
    photo = VisitPhoto.objects.filter(pk=UUID(photo_id)).first()
    if photo is None:
        return
    preview_key = f"visits/{photo.visit_id}/previews/{uuid4().hex}.jpg"
    preview_uploaded = False
    try:
        content = object_storage.get_private_object(object_key=photo.object_key)
        preview = build_photo_preview(content)
        object_storage.put_private_object(
            object_key=preview_key,
            content=preview,
            content_type="image/jpeg",
        )
        preview_uploaded = True
        previous_key = ""
        with transaction.atomic():
            locked = VisitPhoto.objects.select_for_update().filter(pk=photo.pk).first()
            if locked is None:
                _delete_object_safely(preview_key)
                return
            previous_key = locked.preview_object_key
            locked.preview_object_key = preview_key
            locked.preview_content_type = "image/jpeg"
            locked.preview_status = VisitPhotoPreviewStatus.READY
            locked.save(
                update_fields=(
                    "preview_object_key",
                    "preview_content_type",
                    "preview_status",
                )
            )
        if previous_key:
            _delete_object_safely(previous_key)
    except Exception:
        if preview_uploaded:
            _delete_object_safely(preview_key)
        VisitPhoto.objects.filter(pk=photo.pk).update(preview_status=VisitPhotoPreviewStatus.FAILED)
        raise


@shared_task(name="apps.visits.tasks.delete_visit_photo_objects")
def delete_visit_photo_objects(object_keys: list[str]) -> None:
    for object_key in object_keys:
        if object_key:
            _delete_object_safely(object_key)


@shared_task(name="apps.visits.tasks.cleanup_expired_visit_photo_intents")
def cleanup_expired_visit_photo_intents() -> int:
    cutoff = timezone.now() - timedelta(seconds=settings.VISIT_PHOTO_INTENT_CLEANUP_SECONDS)
    deleted, _ = VisitPhotoUploadIntent.objects.filter(
        status=VisitPhotoIntentStatus.PENDING,
        created_at__lt=cutoff,
    ).delete()
    return deleted
