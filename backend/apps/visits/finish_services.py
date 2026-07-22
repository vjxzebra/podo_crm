import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User, UserRole
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.billing.models import Receivable, ReceivableStatus
from apps.clinic.models import AppointmentStatusConfig
from apps.inventory.models import (
    InventoryOperation,
    InventoryOperationKind,
    MaterialLot,
    StockMovement,
)
from apps.inventory.services import operation_snapshot
from apps.scheduling.models import Appointment
from apps.scheduling.services import (
    _active_room,
    _active_service,
    _active_specialist,
    _validate_clinic_time,
    _validate_occupancy,
    appointment_snapshot,
)
from apps.visits.models import (
    Visit,
    VisitFinishResult,
    VisitMaterialLine,
    VisitPhotoPreviewStatus,
    VisitRecommendation,
    VisitServiceLine,
    VisitStatus,
)
from apps.visits.services import (
    _validate_medical_role,
    _visit_queryset,
    get_visit,
    visit_read_model,
    visit_snapshot,
)
from config.api.exceptions import ApiProblem


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime, Decimal, uuid.UUID)):
        return str(value)
    raise TypeError(f"Unsupported finish payload value: {type(value)!r}")


def _payload_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _visible_results(actor: User) -> QuerySet[VisitFinishResult]:
    results = VisitFinishResult.objects.select_related("visit")
    if actor.role == UserRole.PODOLOGIST:
        return results.filter(visit__specialist=actor)
    return results


def _existing_result(
    *,
    actor: User,
    visit_id: UUID,
    idempotency_key: str,
    payload_hash: str,
) -> VisitFinishResult | None:
    existing = _visible_results(actor).filter(visit_id=visit_id).first()
    if existing is None:
        return None
    if existing.payload_hash == payload_hash:
        return existing
    if existing.idempotency_key == idempotency_key:
        raise ApiProblem(
            code="idempotency_payload_mismatch",
            message="Цей ключ повтору вже використано для іншого завершення прийому.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"idempotency_key": ["Створіть новий ключ для зміненого запиту."]},
        )
    raise ApiProblem(
        code="visit_already_completed",
        message="Прийом уже завершено з іншим набором параметрів.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _slot_conflict(exc: IntegrityError) -> ApiProblem:
    cause = getattr(exc, "__cause__", None)
    constraint = getattr(getattr(cause, "diag", None), "constraint_name", "")
    room_conflict = constraint == "scheduling_no_room_overlap"
    return ApiProblem(
        code="appointment_slot_conflict",
        message=(
            "Кабінет уже зайнятий у цей час. Оберіть інший кабінет або час."
            if room_conflict
            else "Спеціаліст уже має запис у цей час. Оберіть інше вікно."
        ),
        status_code=status.HTTP_409_CONFLICT,
        fields=(
            {"follow_up.room_id": ["Кабінет уже зайнятий."]}
            if room_conflict
            else {"follow_up.starts_at": ["Час спеціаліста вже зайнятий."]}
        ),
    )


def _validate_follow_up(
    *,
    actor: User,
    data: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if data is None:
        return None
    specialist = _active_specialist(actor=actor, specialist_id=data["specialist_id"])
    service = _active_service(data["service_id"])
    room = _active_room(data["room_id"])
    starts_at = data["starts_at"]
    ends_at = starts_at + timedelta(minutes=service.duration_minutes)
    _validate_clinic_time(starts_at=starts_at, ends_at=ends_at)
    _validate_occupancy(
        specialist=specialist,
        room=room,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    status_config = AppointmentStatusConfig.objects.select_for_update().get(pk="NEW")
    return {
        "specialist": specialist,
        "service": service,
        "room": room,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "status": status_config,
    }


def _create_follow_up(
    *,
    actor: User,
    visit: Visit,
    validated: Mapping[str, Any],
    correlation_id: str,
) -> Appointment:
    try:
        with transaction.atomic():
            service = validated["service"]
            room = validated["room"]
            appointment = Appointment.objects.create(
                patient=visit.patient,
                specialist=validated["specialist"],
                service=service,
                room=room,
                time_range=(validated["starts_at"], validated["ends_at"]),
                duration_minutes=service.duration_minutes,
                service_name_snapshot=service.name,
                service_color_snapshot=service.color,
                room_label_snapshot=room.name,
                status=validated["status"],
                complaints="",
                has_no_complaints=True,
                comment=f"Наступний прийом після {visit.public_number}",
            )
            appointment.refresh_from_db()
            record_audit_event(
                actor=actor,
                action=AuditAction.APPOINTMENT_CREATED,
                object_type="appointment",
                object_id=appointment.pk,
                object_label=appointment.public_number,
                correlation_id=correlation_id,
                after=appointment_snapshot(appointment),
                description="Створено наступний запис під час завершення прийому.",
            )
            return appointment
    except IntegrityError as exc:
        raise _slot_conflict(exc) from exc


def _validate_finish_draft(
    visit: Visit,
) -> tuple[list[VisitServiceLine], list[VisitMaterialLine]]:
    service_lines = list(visit.service_lines.all())
    material_lines = list(visit.material_lines.all())
    if not service_lines:
        raise ApiProblem(
            code="visit_services_required",
            message="Додайте щонайменше одну послугу перед завершенням прийому.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"service_lines": ["Додайте послугу."]},
        )
    if any(photo.preview_status == VisitPhotoPreviewStatus.FAILED for photo in visit.photos.all()):
        raise ApiProblem(
            code="visit_photo_processing_failed",
            message="Одне з фото не вдалося обробити. Видаліть його або повторіть завантаження.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"photos": ["Є фото з помилкою обробки."]},
        )
    return service_lines, material_lines


def _lock_and_validate_lots(
    material_lines: list[VisitMaterialLine],
) -> dict[UUID, MaterialLot]:
    lot_ids = sorted({line.lot_id for line in material_lines}, key=str)
    locked_lots = list(
        MaterialLot.objects.select_for_update()
        .select_related("material")
        .filter(pk__in=lot_ids)
        .order_by("pk")
    )
    lots = {lot.pk: lot for lot in locked_lots}
    for line in material_lines:
        lot = lots.get(line.lot_id)
        if lot is None or not lot.material.is_active or lot.is_expired:
            raise ApiProblem(
                code="visit_material_lot_unusable",
                message="Одна з вибраних партій більше не доступна для використання.",
                status_code=status.HTTP_409_CONFLICT,
                fields={"material_lines": [f"Оновіть партію {line.lot_number}."]},
            )
        if line.quantity > lot.current_quantity:
            raise ApiProblem(
                code="insufficient_stock",
                message="Матеріалу недостатньо для завершення прийому.",
                status_code=status.HTTP_409_CONFLICT,
                fields={
                    "material_lines": [
                        f"Для партії {lot.lot_number} доступно {lot.current_quantity} "
                        f"{lot.material.unit}."
                    ]
                },
            )
    return lots


def finish_result_read_model(
    *,
    actor: User,
    result: VisitFinishResult,
    replayed: bool,
) -> dict[str, Any]:
    visit = get_visit(actor=actor, visit_id=result.visit_id)
    receivable = Receivable.objects.get(pk=result.result["receivable_id"])
    return {
        "replayed": replayed,
        "visit": visit_read_model(visit),
        "receivable": {
            "id": receivable.pk,
            "amount_minor": receivable.amount_minor,
            "status": receivable.status,
            "created_at": receivable.created_at,
        },
        "inventory_operation_id": result.result["inventory_operation_id"],
        "movement_ids": result.result["movement_ids"],
        "follow_up_appointment_id": result.result["follow_up_appointment_id"],
    }


@transaction.atomic
def finish_visit(
    *,
    actor: User,
    visit_id: UUID,
    idempotency_key: str,
    data: dict[str, Any],
    correlation_id: str,
) -> tuple[VisitFinishResult, bool]:
    _validate_medical_role(actor)
    request_hash = _payload_hash(data)
    existing = _existing_result(
        actor=actor,
        visit_id=visit_id,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    appointments = Appointment.objects.select_for_update(of=("self",))
    if actor.role == UserRole.PODOLOGIST:
        appointments = appointments.filter(specialist=actor)
    appointment = appointments.filter(visit__pk=visit_id).first()
    if appointment is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    visit = (
        _visit_queryset(actor)
        .select_for_update(of=("self",))
        .filter(pk=visit_id, appointment=appointment)
        .first()
    )
    if visit is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    existing = _existing_result(
        actor=actor,
        visit_id=visit_id,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True
    if visit.status != VisitStatus.DRAFT or appointment.status_id != "IN_PROGRESS":
        raise ApiProblem(
            code="visit_not_finishable",
            message="Завершити можна лише активну чернетку прийому.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if visit.version != data["version"]:
        raise ApiProblem(
            code="visit_version_conflict",
            message="Чернетка вже змінилася. Завантажте актуальну версію.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія чернетки застаріла."]},
        )

    before = visit_snapshot(visit)
    service_lines, material_lines = _validate_finish_draft(visit)
    lots = _lock_and_validate_lots(material_lines)
    before_balances = {line.lot_id: lots[line.lot_id].current_quantity for line in material_lines}
    validated_follow_up = _validate_follow_up(
        actor=actor,
        data=data.get("follow_up"),
    )
    total_minor = sum(line.line_total_minor for line in service_lines)

    operation = None
    movement_ids: list[str] = []
    if material_lines:
        operation_key = hashlib.sha256(f"{visit.pk}:{idempotency_key}".encode()).hexdigest()
        operation = InventoryOperation.objects.create(
            kind=InventoryOperationKind.VISIT_USAGE,
            created_by=actor,
            source_visit=visit,
            idempotency_key=operation_key,
            payload_hash=request_hash,
            reason=f"Використання матеріалів у {visit.public_number}",
        )
        for line in material_lines:
            lot = lots[line.lot_id]
            lot.current_quantity -= line.quantity
            lot.save(update_fields=("current_quantity",))
            movement = StockMovement.objects.create(
                operation=operation,
                lot=lot,
                quantity_delta=-line.quantity,
                balance_after=lot.current_quantity,
            )
            movement_ids.append(str(movement.pk))
        operation = InventoryOperation.objects.prefetch_related("movements__lot__material").get(
            pk=operation.pk
        )
        record_audit_event(
            actor=actor,
            action=AuditAction.STOCK_MOVEMENT_POSTED,
            object_type="inventory_operation",
            object_id=operation.pk,
            object_label=operation.public_number,
            correlation_id=correlation_id,
            before={
                "visit_id": visit.pk,
                "balances": [
                    {
                        "lot_id": line.lot_id,
                        "balance": str(before_balances[line.lot_id]),
                    }
                    for line in material_lines
                ],
            },
            after=operation_snapshot(operation),
            description="Автоматично списано матеріали завершеного прийому.",
        )

    receivable = Receivable.objects.create(
        visit=visit,
        amount_minor=total_minor,
        status=(ReceivableStatus.PAID if total_minor == 0 else ReceivableStatus.OPEN),
    )
    recommendation_text = str(data.get("recommendations", "")).strip()
    if recommendation_text:
        VisitRecommendation.objects.create(
            visit=visit,
            author=actor,
            text=recommendation_text,
        )
    follow_up = None
    if validated_follow_up is not None:
        follow_up = _create_follow_up(
            actor=actor,
            visit=visit,
            validated=validated_follow_up,
            correlation_id=correlation_id,
        )

    completed_status = AppointmentStatusConfig.objects.select_for_update().get(pk="COMPLETED")
    appointment.status = completed_status
    appointment.version += 1
    appointment.updated_at = timezone.now()
    appointment.save(update_fields=("status", "version", "updated_at"))
    visit.status = VisitStatus.COMPLETED
    visit.total_minor = total_minor
    visit.payment_handoff_requested = data["payment_handoff_requested"]
    visit.completed_at = timezone.now()
    visit.version += 1
    visit.save(
        update_fields=(
            "status",
            "total_minor",
            "payment_handoff_requested",
            "completed_at",
            "version",
            "updated_at",
        )
    )
    completed_visit = _visit_queryset(actor).get(pk=visit.pk)
    record_audit_event(
        actor=actor,
        action=AuditAction.VISIT_COMPLETED,
        object_type="visit",
        object_id=visit.pk,
        object_label=visit.public_number,
        correlation_id=correlation_id,
        before=before,
        after={
            **visit_snapshot(completed_visit),
            "receivable_id": receivable.pk,
            "inventory_operation_id": operation.pk if operation is not None else None,
            "follow_up_appointment_id": follow_up.pk if follow_up is not None else None,
        },
        description="Завершено прийом, сформовано суму до оплати та проведено матеріали.",
    )
    result = VisitFinishResult.objects.create(
        visit=visit,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
        result={
            "receivable_id": str(receivable.pk),
            "inventory_operation_id": str(operation.pk) if operation is not None else None,
            "movement_ids": movement_ids,
            "follow_up_appointment_id": str(follow_up.pk) if follow_up is not None else None,
        },
    )
    if receivable.status == ReceivableStatus.OPEN and visit.payment_handoff_requested:
        from apps.notifications.services import notify_domain_event_on_commit

        notify_domain_event_on_commit(
            event="visit_payment_ready",
            object_id=str(visit.pk),
            event_version=visit.version,
            actor_id=actor.pk,
        )
    return result, False
