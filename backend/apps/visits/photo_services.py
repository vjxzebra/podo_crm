import logging
import uuid
import warnings
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import status

from apps.accounts.models import User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.visits.models import (
    Visit,
    VisitPhoto,
    VisitPhotoIntentStatus,
    VisitPhotoPreviewStatus,
    VisitPhotoUploadIntent,
    VisitStatus,
)
from apps.visits.services import get_visit
from config import object_storage
from config.api.exceptions import ApiProblem

logger = logging.getLogger("podoria")

PHOTO_CONTENT_SALT = "podoria.visit-photo-content.v1"
ALLOWED_PHOTO_TYPES = {
    "image/jpeg": ("JPEG", ".jpg"),
    "image/png": ("PNG", ".png"),
    "image/webp": ("WEBP", ".webp"),
}


@dataclass(frozen=True)
class CanonicalPhoto:
    content: bytes
    content_type: str
    extension: str
    width: int
    height: int
    original_name: str


def photo_snapshot(photo: VisitPhoto) -> dict[str, Any]:
    return {
        "id": photo.pk,
        "visit_id": photo.visit_id,
        "kind": photo.kind,
        "content_type": photo.content_type,
        "size": photo.size,
        "width": photo.width,
        "height": photo.height,
        "original_name": photo.original_name,
        "preview_status": photo.preview_status,
        "created_by_id": photo.created_by_id,
        "created_at": photo.created_at,
    }


def _signed_content_url(photo: VisitPhoto, *, variant: str) -> str:
    token = signing.dumps(
        {
            "photo_id": str(photo.pk),
            "visit_id": str(photo.visit_id),
            "variant": variant,
        },
        salt=PHOTO_CONTENT_SALT,
        compress=True,
    )
    return f"/api/v1/visit-photo-content?{urlencode({'token': token})}"


def photo_read_model(photo: VisitPhoto) -> dict[str, Any]:
    preview_url = (
        _signed_content_url(photo, variant="preview")
        if photo.preview_status == VisitPhotoPreviewStatus.READY and photo.preview_object_key
        else None
    )
    return {
        **photo_snapshot(photo),
        "created_by_name": photo.created_by.display_name,
        "image_url": _signed_content_url(photo, variant="original"),
        "preview_url": preview_url,
    }


def intent_read_model(intent: VisitPhotoUploadIntent) -> dict[str, Any]:
    return {
        "id": intent.pk,
        "visit_id": intent.visit_id,
        "kind": intent.kind,
        "expires_at": intent.expires_at,
        "max_bytes": settings.VISIT_PHOTO_MAX_BYTES,
        "allowed_content_types": list(ALLOWED_PHOTO_TYPES),
        "finalize_url": f"/api/v1/visits/{intent.visit_id}/photos",
    }


def _editable_locked_visit(*, actor: User, visit_id: UUID) -> Visit:
    visible = get_visit(actor=actor, visit_id=visit_id)
    visit = Visit.objects.select_for_update().get(pk=visible.pk)
    if visit.status != VisitStatus.DRAFT:
        raise ApiProblem(
            code="visit_not_editable",
            message="Фото завершеного прийому не можна змінювати.",
            status_code=status.HTTP_409_CONFLICT,
        )
    return visit


@transaction.atomic
def create_photo_upload_intent(*, actor: User, visit_id: UUID, kind: str) -> VisitPhotoUploadIntent:
    visit = _editable_locked_visit(actor=actor, visit_id=visit_id)
    now = timezone.now()
    reserved = VisitPhoto.objects.filter(visit=visit, kind=kind).count()
    reserved += VisitPhotoUploadIntent.objects.filter(
        visit=visit,
        kind=kind,
        status=VisitPhotoIntentStatus.PENDING,
        expires_at__gt=now,
    ).count()
    if reserved >= settings.VISIT_PHOTO_MAX_PER_KIND:
        raise ApiProblem(
            code="visit_photo_limit_reached",
            message="Для цього блоку вже використано максимальну кількість фото.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"kind": ["Дозволено не більше 10 фото ДО і 10 фото ПІСЛЯ."]},
        )
    return VisitPhotoUploadIntent.objects.create(
        visit=visit,
        kind=kind,
        created_by=actor,
        expires_at=now + timedelta(seconds=settings.VISIT_PHOTO_INTENT_TTL_SECONDS),
    )


def _invalid_photo(*, code: str, message: str, field_message: str) -> ApiProblem:
    return ApiProblem(
        code=code,
        message=message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        fields={"photo": [field_message]},
    )


def validate_and_canonicalize_photo(upload: UploadedFile) -> CanonicalPhoto:
    content_type = (upload.content_type or "").lower()
    expected = ALLOWED_PHOTO_TYPES.get(content_type)
    if expected is None:
        raise _invalid_photo(
            code="invalid_visit_photo_type",
            message="Фото має бути у форматі JPEG, PNG або WebP.",
            field_message="HEIC/HEIF та інші формати не підтримуються.",
        )
    content = upload.read(settings.VISIT_PHOTO_MAX_BYTES + 1)
    if len(content) > settings.VISIT_PHOTO_MAX_BYTES:
        raise _invalid_photo(
            code="visit_photo_too_large",
            message="Розмір фото перевищує 10 МБ.",
            field_message="Максимальний розмір одного фото — 10 МБ.",
        )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                source.load()
                actual_format = source.format
                if actual_format != expected[0]:
                    raise ValueError("Declared content type does not match the decoded format.")
                normalized = ImageOps.exif_transpose(source)
                if normalized.width <= 0 or normalized.height <= 0:
                    raise ValueError("Image dimensions are invalid.")
                if normalized.width > 12000 or normalized.height > 12000:
                    raise ValueError("Image dimensions are too large.")
                image = normalized.copy()
                image.info.clear()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise _invalid_photo(
            code="invalid_visit_photo_content",
            message="Вміст файла не відповідає заявленому формату.",
            field_message="Файл пошкоджений, підроблений або має завеликі розміри.",
        ) from exc

    output = BytesIO()
    image_format, extension = expected
    if image_format == "JPEG":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(output, format="JPEG", quality=90, optimize=True)
    elif image_format == "PNG":
        image.save(output, format="PNG", optimize=True)
    else:
        image.save(output, format="WEBP", quality=90, method=4)
    canonical = output.getvalue()
    if len(canonical) > settings.VISIT_PHOTO_MAX_BYTES:
        raise _invalid_photo(
            code="visit_photo_too_large",
            message="Канонічне фото перевищує 10 МБ.",
            field_message="Зменште роздільну здатність або якість фото.",
        )
    return CanonicalPhoto(
        content=canonical,
        content_type=content_type,
        extension=extension,
        width=image.width,
        height=image.height,
        original_name=Path(upload.name or "photo").name[:255],
    )


def build_photo_preview(content: bytes) -> bytes:
    with Image.open(BytesIO(content)) as source:
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((640, 640), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=84, optimize=True)
        return output.getvalue()


def _delete_object_safely(object_key: str) -> None:
    try:
        object_storage.delete_private_object(object_key=object_key)
    except Exception:
        logger.exception("visit_photo_object_cleanup_failed", extra={"object_key": object_key})


def _queue_preview(photo_id: UUID) -> None:
    try:
        from apps.visits.tasks import generate_visit_photo_preview

        generate_visit_photo_preview.delay(str(photo_id))
    except Exception:
        VisitPhoto.objects.filter(pk=photo_id).update(preview_status=VisitPhotoPreviewStatus.FAILED)
        logger.exception("visit_photo_preview_enqueue_failed", extra={"photo_id": photo_id})


def _queue_object_cleanup(object_keys: tuple[str, ...]) -> None:
    try:
        from apps.visits.tasks import delete_visit_photo_objects

        delete_visit_photo_objects.delay([key for key in object_keys if key])
    except Exception:
        for object_key in object_keys:
            _delete_object_safely(object_key)


def finalize_visit_photo(
    *,
    actor: User,
    visit_id: UUID,
    intent_id: UUID,
    upload: UploadedFile,
    correlation_id: str,
) -> tuple[VisitPhoto, bool]:
    object_key = ""
    uploaded = False
    try:
        with transaction.atomic():
            visit = _editable_locked_visit(actor=actor, visit_id=visit_id)
            intent = (
                VisitPhotoUploadIntent.objects.select_for_update()
                .filter(pk=intent_id, visit=visit)
                .first()
            )
            if intent is None or intent.created_by_id != actor.pk:
                raise ApiProblem(
                    code="not_found",
                    message="Ресурс не знайдено.",
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            if (
                intent.status == VisitPhotoIntentStatus.FINALIZED
                and intent.finalized_photo_id is not None
            ):
                photo = VisitPhoto.objects.filter(pk=intent.finalized_photo_id).first()
                if photo is not None:
                    return photo, False
            if intent.status != VisitPhotoIntentStatus.PENDING:
                raise ApiProblem(
                    code="visit_photo_intent_used",
                    message="Цей upload intent уже використано.",
                    status_code=status.HTTP_409_CONFLICT,
                )
            if intent.expires_at <= timezone.now():
                raise ApiProblem(
                    code="visit_photo_intent_expired",
                    message="Час upload intent минув. Створіть новий і повторіть спробу.",
                    status_code=status.HTTP_409_CONFLICT,
                )
            if (
                VisitPhoto.objects.filter(visit=visit, kind=intent.kind).count()
                >= settings.VISIT_PHOTO_MAX_PER_KIND
            ):
                raise ApiProblem(
                    code="visit_photo_limit_reached",
                    message="Для цього блоку вже використано максимальну кількість фото.",
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            canonical = validate_and_canonicalize_photo(upload)
            photo_id = uuid.uuid4()
            object_key = f"visits/{visit_id}/photos/{photo_id.hex}{canonical.extension}"
            try:
                object_storage.put_private_object(
                    object_key=object_key,
                    content=canonical.content,
                    content_type=canonical.content_type,
                )
                uploaded = True
            except Exception as exc:
                raise ApiProblem(
                    code="visit_photo_storage_unavailable",
                    message="Не вдалося зберегти фото. Спробуйте ще раз.",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                ) from exc
            photo = VisitPhoto.objects.create(
                id=photo_id,
                visit=visit,
                kind=intent.kind,
                object_key=object_key,
                content_type=canonical.content_type,
                size=len(canonical.content),
                width=canonical.width,
                height=canonical.height,
                original_name=canonical.original_name,
                created_by=actor,
            )
            intent.status = VisitPhotoIntentStatus.FINALIZED
            intent.finalized_photo = photo
            intent.save(update_fields=("status", "finalized_photo"))
            record_audit_event(
                actor=actor,
                action=AuditAction.VISIT_PHOTO_ADDED,
                object_type="visit_photo",
                object_id=photo.pk,
                object_label=f"{visit.public_number} · {photo.get_kind_display()}",
                correlation_id=correlation_id,
                before=None,
                after=photo_snapshot(photo),
                description="Додано приватне фото до чернетки прийому.",
            )
            transaction.on_commit(lambda: _queue_preview(photo.pk))
            return photo, True
    except Exception:
        if uploaded:
            _delete_object_safely(object_key)
        raise


def get_visit_photo(*, actor: User, visit_id: UUID, photo_id: UUID) -> VisitPhoto:
    visit = get_visit(actor=actor, visit_id=visit_id)
    photo = VisitPhoto.objects.select_related("created_by").filter(pk=photo_id, visit=visit).first()
    if photo is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return photo


@transaction.atomic
def delete_visit_photo(*, actor: User, visit_id: UUID, photo_id: UUID, correlation_id: str) -> None:
    visit = _editable_locked_visit(actor=actor, visit_id=visit_id)
    photo = (
        VisitPhoto.objects.select_for_update()
        .select_related("created_by")
        .filter(pk=photo_id, visit=visit)
        .first()
    )
    if photo is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    before = photo_snapshot(photo)
    object_keys = (photo.object_key, photo.preview_object_key)
    label = f"{visit.public_number} · {photo.get_kind_display()}"
    photo.delete()
    record_audit_event(
        actor=actor,
        action=AuditAction.VISIT_PHOTO_DELETED,
        object_type="visit_photo",
        object_id=photo_id,
        object_label=label,
        correlation_id=correlation_id,
        before=before,
        after=None,
        description="Видалено приватне фото з чернетки прийому.",
    )
    transaction.on_commit(lambda: _queue_object_cleanup(object_keys))


def resolve_signed_photo_content(*, actor: User, token: str) -> tuple[bytes, str]:
    try:
        payload = signing.loads(
            token,
            salt=PHOTO_CONTENT_SALT,
            max_age=settings.VISIT_PHOTO_SIGNED_URL_SECONDS,
        )
        photo_id = UUID(str(payload["photo_id"]))
        visit_id = UUID(str(payload["visit_id"]))
        variant = str(payload["variant"])
    except (KeyError, TypeError, ValueError, signing.BadSignature) as exc:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
    if variant not in {"original", "preview"}:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    photo = get_visit_photo(actor=actor, visit_id=visit_id, photo_id=photo_id)
    if variant == "preview" and photo.preview_status == VisitPhotoPreviewStatus.READY:
        object_key = photo.preview_object_key
        content_type = photo.preview_content_type
    else:
        object_key = photo.object_key
        content_type = photo.content_type
    try:
        return object_storage.get_private_object(object_key=object_key), content_type
    except Exception as exc:
        raise ApiProblem(
            code="visit_photo_storage_unavailable",
            message="Не вдалося отримати фото. Спробуйте ще раз.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc
