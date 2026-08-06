from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User, UserRole
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.clinic.models import AppointmentStatusConfig, Service
from apps.discounts.services import visit_loyalty_preview
from apps.inventory.models import Material, MaterialLot
from apps.scheduling.models import Appointment
from apps.visits.models import (
    DetectedCondition,
    Visit,
    VisitMaterialLine,
    VisitRecommendation,
    VisitServiceLine,
    VisitStatus,
)
from config.api.exceptions import ApiProblem

MEDICAL_ROLES = {UserRole.ADMIN, UserRole.PODOLOGIST}


def _service_line_snapshot(line: VisitServiceLine) -> dict[str, Any]:
    return {
        "service_id": line.service_id,
        "service_code": line.service_code,
        "service_name": line.service_name,
        "duration_minutes": line.duration_minutes,
        "price_minor": line.price_minor,
        "quantity": line.quantity,
        "is_primary": line.is_primary,
        "line_total_minor": line.line_total_minor,
    }


def _material_line_snapshot(line: VisitMaterialLine) -> dict[str, Any]:
    return {
        "material_id": line.material_id,
        "lot_id": line.lot_id,
        "material_sku": line.material_sku,
        "material_name": line.material_name,
        "material_unit": line.material_unit,
        "lot_number": line.lot_number,
        "expires_on": line.expires_on,
        "quantity": str(line.quantity),
    }


def _recommendation_snapshot(recommendation: VisitRecommendation) -> dict[str, Any]:
    return {
        "id": recommendation.pk,
        "author_id": recommendation.author_id,
        "author_name": recommendation.author.display_name,
        "text": recommendation.text,
        "version": recommendation.version,
        "created_at": recommendation.created_at,
        "updated_at": recommendation.updated_at,
    }


def visit_snapshot(visit: Visit) -> dict[str, Any]:
    from apps.visits.photo_services import photo_snapshot

    return {
        "public_number": visit.public_number,
        "appointment_id": visit.appointment_id,
        "appointment_status": visit.appointment.status_id,
        "patient_id": visit.patient_id,
        "specialist_id": visit.specialist_id,
        "status": visit.status,
        "complaints": visit.complaints,
        "has_no_complaints": visit.has_no_complaints,
        "objective_examination": visit.objective_examination,
        "detected_conditions": list(visit.detected_conditions),
        "podologist_notes": visit.podologist_notes,
        "total_minor": visit.total_minor,
        "payment_handoff_requested": visit.payment_handoff_requested,
        "service_lines": [_service_line_snapshot(line) for line in visit.service_lines.all()],
        "material_lines": [_material_line_snapshot(line) for line in visit.material_lines.all()],
        "photos": [photo_snapshot(photo) for photo in visit.photos.all()],
        "recommendations": [
            _recommendation_snapshot(recommendation)
            for recommendation in visit.recommendations.all()
        ],
        "version": visit.version,
        "completed_at": visit.completed_at,
    }


def visit_read_model(visit: Visit) -> dict[str, Any]:
    from apps.visits.photo_services import photo_read_model

    appointment = visit.appointment
    service_lines = list(visit.service_lines.all())
    material_lines = list(visit.material_lines.all())
    return {
        "id": visit.pk,
        "public_number": visit.public_number,
        "status": visit.status,
        "version": visit.version,
        "appointment": {
            "id": appointment.pk,
            "public_number": appointment.public_number,
            "starts_at": appointment.starts_at,
            "ends_at": appointment.ends_at,
            "service_name": appointment.service_name_snapshot,
            "room_name": appointment.room_label_snapshot,
            "status_code": appointment.status_id,
            "status_label": appointment.status.label,
        },
        "patient": {
            "id": visit.patient_id,
            "public_number": visit.patient.public_number,
            "display_name": visit.patient.display_name,
        },
        "specialist": {
            "id": visit.specialist_id,
            "display_name": visit.specialist.display_name,
        },
        "complaints": visit.complaints,
        "has_no_complaints": visit.has_no_complaints,
        "objective_examination": visit.objective_examination,
        "detected_conditions": list(visit.detected_conditions),
        "podologist_notes": visit.podologist_notes,
        "total_minor": visit.total_minor,
        "payment_handoff_requested": visit.payment_handoff_requested,
        "service_lines": [
            {"id": line.pk, **_service_line_snapshot(line)} for line in service_lines
        ],
        "material_lines": [
            {
                "id": line.pk,
                **_material_line_snapshot(line),
                "available_quantity": line.lot.current_quantity,
                "is_available": (
                    line.material.is_active
                    and line.lot.is_usable
                    and line.quantity <= line.lot.current_quantity
                ),
            }
            for line in material_lines
        ],
        "services_total_minor": sum(line.line_total_minor for line in service_lines),
        "photos": [photo_read_model(photo) for photo in visit.photos.all()],
        "recommendations": [
            _recommendation_snapshot(recommendation)
            for recommendation in visit.recommendations.all()
        ],
        "editable": visit.status == VisitStatus.DRAFT,
        "loyalty": visit_loyalty_preview(visit_id=visit.pk, patient_id=visit.patient_id),
        "started_at": visit.started_at,
        "updated_at": visit.updated_at,
        "completed_at": visit.completed_at,
    }


def _validate_medical_role(actor: User) -> None:
    if actor.role not in MEDICAL_ROLES:
        raise ApiProblem(
            code="visit_forbidden",
            message="Медичний прийом доступний лише подологу або адміністратору.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _visit_queryset(actor: User) -> QuerySet[Visit]:
    queryset = Visit.objects.select_related(
        "appointment",
        "appointment__status",
        "patient",
        "specialist",
        "started_by",
    ).prefetch_related(
        "service_lines__service",
        "material_lines__material",
        "material_lines__lot",
        "photos__created_by",
        "recommendations__author",
    )
    if actor.role == UserRole.PODOLOGIST:
        return queryset.filter(specialist=actor)
    return queryset


def get_visit(*, actor: User, visit_id: UUID) -> Visit:
    _validate_medical_role(actor)
    visit = _visit_queryset(actor).filter(pk=visit_id).first()
    if visit is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return visit


def _validate_complaints(*, complaints: str, has_no_complaints: bool) -> None:
    if has_no_complaints == bool(complaints):
        raise ApiProblem(
            code="complaints_required",
            message="Укажіть скарги або явно позначте, що скарг немає.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={
                "complaints": ["Заповніть причину звернення або виберіть «Скарг немає»."],
                "has_no_complaints": ["Оберіть лише один із двох варіантів."],
            },
        )


@transaction.atomic
def start_visit(
    *,
    actor: User,
    appointment_id: UUID,
    requested_version: int,
    correlation_id: str,
) -> tuple[Visit, bool]:
    _validate_medical_role(actor)
    appointments = Appointment.objects.select_for_update(of=("self",))
    if actor.role == UserRole.PODOLOGIST:
        appointments = appointments.filter(specialist=actor)
    appointment = appointments.filter(pk=appointment_id).first()
    if appointment is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    existing = (
        Visit.objects.select_related(
            "appointment",
            "appointment__status",
            "patient",
            "specialist",
            "started_by",
        )
        .select_for_update(of=("self",))
        .filter(appointment=appointment)
        .first()
    )
    if existing is not None and appointment.status_id == "IN_PROGRESS":
        return existing, False
    if existing is not None:
        raise ApiProblem(
            code="visit_already_exists",
            message="Для цього запису вже існує прийом.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if appointment.version != requested_version:
        raise ApiProblem(
            code="appointment_version_conflict",
            message="Запис уже змінив інший користувач. Завантажте актуальну версію.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія запису застаріла."]},
        )
    if appointment.status_id != "ARRIVED":
        raise ApiProblem(
            code="appointment_not_ready_for_visit",
            message="Прийом можна почати лише після відмітки про прибуття пацієнта.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"status": ["Спочатку встановіть статус «Пацієнт прийшов»."]},
        )

    in_progress = AppointmentStatusConfig.objects.select_for_update().get(pk="IN_PROGRESS")
    previous_status = appointment.status_id
    appointment.status = in_progress
    appointment.version += 1
    appointment.updated_at = timezone.now()
    appointment.save(update_fields=("status", "version", "updated_at"))
    visit = Visit.objects.create(
        appointment=appointment,
        patient=appointment.patient,
        specialist=appointment.specialist,
        complaints=appointment.complaints,
        has_no_complaints=appointment.has_no_complaints,
        started_by=actor,
    )
    appointment_service_lines = list(appointment.service_lines.select_related("service").all())
    if appointment_service_lines:
        VisitServiceLine.objects.bulk_create(
            [
                VisitServiceLine(
                    visit=visit,
                    service=line.service,
                    service_code=line.service.code,
                    service_name=line.service_name_snapshot,
                    duration_minutes=line.duration_minutes,
                    price_minor=line.service.price_minor,
                    quantity=1,
                    is_primary=line.position == 0,
                )
                for line in appointment_service_lines
            ]
        )
    else:
        VisitServiceLine.objects.create(
            visit=visit,
            service=appointment.service,
            service_code=appointment.service.code,
            service_name=appointment.service_name_snapshot,
            duration_minutes=appointment.duration_minutes,
            price_minor=appointment.service.price_minor,
            quantity=1,
            is_primary=True,
        )
    record_audit_event(
        actor=actor,
        action=AuditAction.VISIT_STARTED,
        object_type="visit",
        object_id=visit.pk,
        object_label=visit.public_number,
        correlation_id=correlation_id,
        before={
            "appointment_id": appointment.pk,
            "appointment_status": previous_status,
            "visit": None,
        },
        after=visit_snapshot(visit),
        description="Розпочато медичний прийом і створено чернетку огляду.",
    )
    return visit, True


def _replace_service_lines(
    *,
    visit: Visit,
    raw_lines: list[Mapping[str, Any]],
) -> None:
    service_ids = [line["service_id"] for line in raw_lines]
    if len(service_ids) != len(set(service_ids)):
        raise ApiProblem(
            code="visit_service_duplicate",
            message="Однакова послуга не може дублюватися у чернетці.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"service_lines": ["Додайте кількість до наявної послуги."]},
        )

    existing = {line.service_id: line for line in visit.service_lines.all()}
    services = Service.objects.in_bulk(service_ids)
    if len(services) != len(service_ids):
        raise ApiProblem(
            code="visit_service_not_found",
            message="Одну з послуг не знайдено.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"service_lines": ["Оновіть результати пошуку й повторіть вибір."]},
        )
    unavailable = [
        service_id
        for service_id, service in services.items()
        if not service.is_active and service_id not in existing
    ]
    if unavailable:
        raise ApiProblem(
            code="visit_service_inactive",
            message="Неактивну послугу не можна додати до прийому.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"service_lines": ["Оберіть активну послугу."]},
        )

    requested = set(service_ids)
    visit.service_lines.exclude(service_id__in=requested).delete()
    for raw_line in raw_lines:
        service_id = raw_line["service_id"]
        quantity = int(raw_line["quantity"])
        line = existing.get(service_id)
        if line is not None:
            if line.quantity != quantity:
                line.quantity = quantity
                line.save(update_fields=("quantity", "updated_at"))
            continue
        service = services[service_id]
        VisitServiceLine.objects.create(
            visit=visit,
            service=service,
            service_code=service.code,
            service_name=service.name,
            duration_minutes=service.duration_minutes,
            price_minor=service.price_minor,
            quantity=quantity,
            is_primary=service_id == visit.appointment.service_id,
        )


def _replace_material_lines(
    *,
    visit: Visit,
    raw_lines: list[Mapping[str, Any]],
) -> None:
    lot_ids = [line["lot_id"] for line in raw_lines]
    if len(lot_ids) != len(set(lot_ids)):
        raise ApiProblem(
            code="visit_material_lot_duplicate",
            message="Однакова партія матеріалу не може дублюватися у чернетці.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"material_lines": ["Об’єднайте кількість для однакової партії."]},
        )

    lots = MaterialLot.objects.select_related("material").in_bulk(lot_ids)
    if len(lots) != len(lot_ids):
        raise ApiProblem(
            code="visit_material_lot_not_found",
            message="Одну з партій матеріалу не знайдено.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"material_lines": ["Оновіть результати пошуку й повторіть вибір."]},
        )
    normalized: list[tuple[MaterialLot, Decimal]] = []
    for raw_line in raw_lines:
        lot = lots[raw_line["lot_id"]]
        quantity = Decimal(str(raw_line["quantity"]))
        if not lot.material.is_active or not lot.is_usable:
            raise ApiProblem(
                code="visit_material_lot_unusable",
                message="Для прийому можна вибрати лише активну непрострочену партію.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    "material_lines": [f"Партія {lot.lot_number} недоступна для використання."]
                },
            )
        if quantity > lot.current_quantity:
            raise ApiProblem(
                code="visit_material_quantity_insufficient",
                message="Кількість матеріалу перевищує доступний залишок партії.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                fields={
                    "material_lines": [
                        f"Для партії {lot.lot_number} доступно {lot.current_quantity}."
                    ]
                },
            )
        normalized.append((lot, quantity))

    existing = {line.lot_id: line for line in visit.material_lines.all()}
    requested = set(lot_ids)
    visit.material_lines.exclude(lot_id__in=requested).delete()
    for lot, quantity in normalized:
        line = existing.get(lot.pk)
        if line is not None:
            if line.quantity != quantity:
                line.quantity = quantity
                line.save(update_fields=("quantity", "updated_at"))
            continue
        VisitMaterialLine.objects.create(
            visit=visit,
            material=lot.material,
            lot=lot,
            material_sku=lot.material.sku,
            material_name=lot.material.name,
            material_unit=lot.material.unit,
            lot_number=lot.lot_number,
            expires_on=lot.expires_on,
            quantity=quantity,
        )


@transaction.atomic
def save_visit_draft(
    *,
    actor: User,
    visit_id: UUID,
    requested_version: int,
    data: Mapping[str, Any],
    correlation_id: str,
) -> Visit:
    _validate_medical_role(actor)
    visits = _visit_queryset(actor).select_for_update(of=("self",))
    visit = visits.filter(pk=visit_id).first()
    if visit is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if visit.status != VisitStatus.DRAFT:
        raise ApiProblem(
            code="visit_not_editable",
            message="Завершений прийом не можна редагувати як чернетку.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if visit.version != requested_version:
        raise ApiProblem(
            code="visit_version_conflict",
            message="Чернетка вже змінилася. Завантажте актуальну версію.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія чернетки застаріла."]},
        )

    complaints = str(data.get("complaints", visit.complaints)).strip()
    has_no_complaints = bool(data.get("has_no_complaints", visit.has_no_complaints))
    _validate_complaints(
        complaints=complaints,
        has_no_complaints=has_no_complaints,
    )
    raw_conditions = data.get("detected_conditions", visit.detected_conditions)
    conditions = [str(value) for value in raw_conditions]
    if len(conditions) != len(set(conditions)):
        raise ApiProblem(
            code="visit_conditions_duplicate",
            message="Кожен виявлений стан можна вибрати лише один раз.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"detected_conditions": ["Приберіть дублікати зі списку станів."]},
        )
    allowed_conditions = set(DetectedCondition.values)
    if any(value not in allowed_conditions for value in conditions):
        raise ApiProblem(
            code="visit_condition_invalid",
            message="Вибрано невідомий стан огляду.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"detected_conditions": ["Оберіть стан зі списку."]},
        )

    before = visit_snapshot(visit)
    if "service_lines" in data:
        _replace_service_lines(visit=visit, raw_lines=list(data["service_lines"]))
    if "material_lines" in data:
        _replace_material_lines(visit=visit, raw_lines=list(data["material_lines"]))
    visit.complaints = complaints
    visit.has_no_complaints = has_no_complaints
    visit.objective_examination = str(
        data.get("objective_examination", visit.objective_examination)
    ).strip()
    visit.detected_conditions = conditions
    visit.podologist_notes = str(data.get("podologist_notes", visit.podologist_notes)).strip()
    visit.version += 1
    visit.updated_at = timezone.now()
    visit.save(
        update_fields=(
            "complaints",
            "has_no_complaints",
            "objective_examination",
            "detected_conditions",
            "podologist_notes",
            "version",
            "updated_at",
        )
    )
    if hasattr(visit, "_prefetched_objects_cache"):
        delattr(visit, "_prefetched_objects_cache")
    record_audit_event(
        actor=actor,
        action=AuditAction.VISIT_DRAFT_SAVED,
        object_type="visit",
        object_id=visit.pk,
        object_label=visit.public_number,
        correlation_id=correlation_id,
        before=before,
        after=visit_snapshot(visit),
        description="Збережено чернетку прийому.",
    )
    return visit


def list_visit_material_options(
    *,
    actor: User,
    visit_id: UUID,
    search: str,
) -> list[dict[str, Any]]:
    get_visit(actor=actor, visit_id=visit_id)
    today = timezone.localdate()
    usable_lots = MaterialLot.objects.filter(current_quantity__gt=0).filter(
        Q(expires_on__isnull=True) | Q(expires_on__gte=today)
    )
    materials = Material.objects.filter(is_active=True, lots__in=usable_lots)
    if search:
        materials = materials.filter(Q(sku__icontains=search) | Q(name__icontains=search))
    materials = materials.distinct().prefetch_related(
        Prefetch("lots", queryset=usable_lots, to_attr="usable_visit_lots")
    )[:30]

    result: list[dict[str, Any]] = []
    for material in materials:
        lots = sorted(
            material.usable_visit_lots,
            key=lambda item: (
                item.expires_on is None,
                item.expires_on,
                item.received_on,
                item.lot_number,
                item.pk,
            ),
        )
        result.append(
            {
                "id": material.pk,
                "sku": material.sku,
                "name": material.name,
                "unit": material.unit,
                "available_quantity": sum((lot.current_quantity for lot in lots), Decimal("0")),
                "lots": [
                    {
                        "id": lot.pk,
                        "lot_number": lot.lot_number,
                        "expires_on": lot.expires_on,
                        "current_quantity": lot.current_quantity,
                        "fefo_rank": index,
                    }
                    for index, lot in enumerate(lots, start=1)
                ],
            }
        )
    return result
