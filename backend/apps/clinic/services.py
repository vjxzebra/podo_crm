import uuid
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from apps.accounts.models import User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.clinic import storage
from apps.clinic.models import ClinicProfile, Room, Service
from config.api.exceptions import ApiProblem

ALLOWED_LOGO_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
}


def clinic_snapshot(profile: ClinicProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "phone": profile.phone,
        "email": profile.email,
        "address": profile.address,
        "description": profile.description,
        "has_logo": bool(profile.logo_object_key),
        "logo_content_type": profile.logo_content_type,
        "logo_size": profile.logo_size,
        "version": profile.version,
    }


def room_snapshot(room: Room) -> dict[str, Any]:
    return {
        "name": room.name,
        "is_active": room.is_active,
        "version": room.version,
    }


def service_snapshot(service: Service) -> dict[str, Any]:
    return {
        "code": service.code,
        "name": service.name,
        "duration_minutes": service.duration_minutes,
        "price_minor": service.price_minor,
        "color": service.color,
        "is_active": service.is_active,
        "version": service.version,
    }


def get_clinic_profile() -> ClinicProfile:
    profile, _ = ClinicProfile.objects.get_or_create(
        key="clinic",
        defaults={
            "name": "Podoria Clinic",
            "phone": "+380 00 000 00 00",
            "email": "clinic@example.com",
            "address": "Укажіть адресу кабінету",
        },
    )
    return profile


def _check_version(*, actual: int, expected: int, resource: str) -> None:
    if actual != expected:
        raise ApiProblem(
            code="stale_version",
            message=f"{resource} уже змінено в іншій сесії. Оновіть дані та повторіть дію.",
            status_code=409,
        )


@transaction.atomic
def update_clinic_profile(
    *, actor: User, correlation_id: str, changes: dict[str, Any]
) -> ClinicProfile:
    profile = ClinicProfile.objects.select_for_update().get(key="clinic")
    expected_version = changes.pop("version")
    _check_version(actual=profile.version, expected=expected_version, resource="Профіль кабінету")
    before = clinic_snapshot(profile)
    for field in ("name", "phone", "email", "address", "description"):
        if field in changes:
            setattr(profile, field, changes[field].strip())
    profile.version += 1
    profile.save()
    record_audit_event(
        actor=actor,
        action=AuditAction.CLINIC_PROFILE_UPDATED,
        object_type="clinic_profile",
        object_id=profile.pk,
        object_label=profile.name,
        correlation_id=correlation_id,
        before=before,
        after=clinic_snapshot(profile),
        description="Оновлено профіль кабінету.",
    )
    return profile


def _validated_logo(upload: UploadedFile) -> tuple[bytes, str, str]:
    content_type = upload.content_type or ""
    signature_and_extension = ALLOWED_LOGO_TYPES.get(content_type)
    if signature_and_extension is None:
        raise ApiProblem(
            code="invalid_logo_type",
            message="Логотип має бути у форматі PNG або JPEG.",
            status_code=422,
            fields={"logo": ["Дозволено лише PNG або JPEG."]},
        )
    content = upload.read(settings.CLINIC_LOGO_MAX_BYTES + 1)
    if len(content) > settings.CLINIC_LOGO_MAX_BYTES:
        raise ApiProblem(
            code="logo_too_large",
            message="Розмір логотипа перевищує 5 МБ.",
            status_code=422,
            fields={"logo": ["Максимальний розмір — 5 МБ."]},
        )
    signature, extension = signature_and_extension
    if not content.startswith(signature):
        raise ApiProblem(
            code="invalid_logo_content",
            message="Вміст файла не відповідає заявленому формату.",
            status_code=422,
            fields={"logo": ["Файл пошкоджений або має неправильний формат."]},
        )
    return content, content_type, extension


def update_clinic_logo(
    *, actor: User, correlation_id: str, upload: UploadedFile, expected_version: int
) -> ClinicProfile:
    content, content_type, extension = _validated_logo(upload)
    object_key = f"clinic/logo/{uuid.uuid4().hex}{extension}"
    try:
        storage.put_private_object(
            object_key=object_key,
            content=content,
            content_type=content_type,
        )
    except Exception as exc:
        raise ApiProblem(
            code="logo_storage_unavailable",
            message="Не вдалося зберегти логотип. Спробуйте ще раз.",
            status_code=503,
        ) from exc

    try:
        with transaction.atomic():
            profile = ClinicProfile.objects.select_for_update().get(key="clinic")
            _check_version(
                actual=profile.version,
                expected=expected_version,
                resource="Профіль кабінету",
            )
            before = clinic_snapshot(profile)
            old_object_key = profile.logo_object_key
            profile.logo_object_key = object_key
            profile.logo_content_type = content_type
            profile.logo_size = len(content)
            profile.version += 1
            profile.save()
            record_audit_event(
                actor=actor,
                action=AuditAction.CLINIC_LOGO_UPDATED,
                object_type="clinic_profile",
                object_id=profile.pk,
                object_label=profile.name,
                correlation_id=correlation_id,
                before=before,
                after=clinic_snapshot(profile),
                description="Оновлено приватний логотип кабінету.",
            )
            if old_object_key:
                transaction.on_commit(
                    lambda: storage.delete_private_object(object_key=old_object_key)
                )
            return profile
    except Exception:
        storage.delete_private_object(object_key=object_key)
        raise


@transaction.atomic
def create_room(*, actor: User, correlation_id: str, data: dict[str, Any]) -> Room:
    room = Room.objects.create(
        name=data["name"].strip(),
        is_active=data.get("is_active", True),
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.ROOM_CREATED,
        object_type="room",
        object_id=room.pk,
        object_label=room.name,
        correlation_id=correlation_id,
        before={},
        after=room_snapshot(room),
        description="Створено кімнату кабінету.",
    )
    return room


@transaction.atomic
def update_room(
    *, actor: User, room_id: uuid.UUID, correlation_id: str, changes: dict[str, Any]
) -> Room:
    room = Room.objects.select_for_update().get(pk=room_id)
    expected_version = changes.pop("version")
    _check_version(actual=room.version, expected=expected_version, resource="Кімнату")
    before = room_snapshot(room)
    was_active = room.is_active
    if "name" in changes:
        room.name = changes["name"].strip()
    if "is_active" in changes:
        room.is_active = changes["is_active"]
    room.version += 1
    room.save()
    if was_active and not room.is_active:
        action = AuditAction.ROOM_DEACTIVATED
        description = "Деактивовано кімнату кабінету."
    elif not was_active and room.is_active:
        action = AuditAction.ROOM_REACTIVATED
        description = "Активовано кімнату кабінету."
    else:
        action = AuditAction.ROOM_UPDATED
        description = "Оновлено кімнату кабінету."
    record_audit_event(
        actor=actor,
        action=action,
        object_type="room",
        object_id=room.pk,
        object_label=room.name,
        correlation_id=correlation_id,
        before=before,
        after=room_snapshot(room),
        description=description,
    )
    return room


@transaction.atomic
def create_service(*, actor: User, correlation_id: str, data: dict[str, Any]) -> Service:
    service = Service.objects.create(
        code=data["code"],
        name=data["name"],
        duration_minutes=data["duration_minutes"],
        price_minor=data["price_minor"],
        color=data["color"],
        is_active=data.get("is_active", True),
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.SERVICE_CREATED,
        object_type="service",
        object_id=service.pk,
        object_label=f"{service.code} · {service.name}",
        correlation_id=correlation_id,
        before={},
        after=service_snapshot(service),
        description="Створено послугу кабінету.",
    )
    return service


@transaction.atomic
def update_service(
    *, actor: User, service_id: uuid.UUID, correlation_id: str, changes: dict[str, Any]
) -> Service:
    service = Service.objects.select_for_update().get(pk=service_id)
    expected_version = changes.pop("version")
    _check_version(actual=service.version, expected=expected_version, resource="Послугу")
    before = service_snapshot(service)
    was_active = service.is_active
    for field in (
        "code",
        "name",
        "duration_minutes",
        "price_minor",
        "color",
        "is_active",
    ):
        if field in changes:
            setattr(service, field, changes[field])
    service.version += 1
    service.save()
    if was_active and not service.is_active:
        action = AuditAction.SERVICE_DEACTIVATED
        description = "Деактивовано послугу кабінету без видалення історії."
    elif not was_active and service.is_active:
        action = AuditAction.SERVICE_REACTIVATED
        description = "Активовано послугу кабінету."
    else:
        action = AuditAction.SERVICE_UPDATED
        description = "Оновлено послугу кабінету."
    record_audit_event(
        actor=actor,
        action=action,
        object_type="service",
        object_id=service.pk,
        object_label=f"{service.code} · {service.name}",
        correlation_id=correlation_id,
        before=before,
        after=service_snapshot(service),
        description=description,
    )
    return service
