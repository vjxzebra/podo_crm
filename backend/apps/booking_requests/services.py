from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.booking_requests.models import BookingRequest, BookingRequestStatus
from apps.booking_requests.selectors import booking_requests_visible_to
from config.api.exceptions import ApiProblem


def booking_request_audit_snapshot(item: BookingRequest) -> dict[str, Any]:
    return {
        "public_number": item.public_number,
        "source": item.source,
        "status": item.status,
        "processed_by_display_name": item.processed_by_display_name,
        "processed_at": item.processed_at,
        "version": item.version,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@transaction.atomic
def create_booking_request(
    *,
    data: dict[str, Any],
    correlation_id: str,
    actor: User | None = None,
) -> BookingRequest:
    item = BookingRequest(**dict(data))
    item.normalize_contact_fields()
    item.full_clean()
    item.save()
    record_audit_event(
        actor=actor,
        actor_display_name="Зовнішня інтеграція",
        actor_role="integration",
        action=AuditAction.BOOKING_REQUEST_CREATED,
        object_type="booking_request",
        object_id=item.pk,
        object_label=item.public_number,
        correlation_id=correlation_id,
        after=booking_request_audit_snapshot(item),
        description="Створено заявку на запис.",
    )
    return item


@transaction.atomic
def process_booking_request(
    *,
    actor: User,
    booking_request_id: UUID,
    requested_version: int,
    correlation_id: str,
) -> BookingRequest:
    item = (
        booking_requests_visible_to(actor)
        .select_for_update(of=("self",))
        .filter(pk=booking_request_id)
        .first()
    )
    if item is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if item.status == BookingRequestStatus.PROCESSED:
        return item
    if item.version != requested_version:
        raise ApiProblem(
            code="version_conflict",
            message="Заявку вже змінив інший користувач. Оновіть дані й повторіть дію.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія заявки застаріла."]},
        )

    before = booking_request_audit_snapshot(item)
    item.status = BookingRequestStatus.PROCESSED
    item.processed_by = actor
    item.processed_by_display_name = actor.display_name
    item.processed_at = timezone.now()
    item.version += 1
    item.save(
        update_fields=(
            "status",
            "processed_by",
            "processed_by_display_name",
            "processed_at",
            "version",
            "updated_at",
        )
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.BOOKING_REQUEST_PROCESSED,
        object_type="booking_request",
        object_id=item.pk,
        object_label=item.public_number,
        correlation_id=correlation_id,
        before=before,
        after=booking_request_audit_snapshot(item),
        description="Заявку на запис позначено обробленою.",
    )
    return item
