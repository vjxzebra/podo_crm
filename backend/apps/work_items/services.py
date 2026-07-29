from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User, UserRole
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.booking_requests.telegram_services import enqueue_work_item_telegram_delivery_on_commit
from apps.patients.models import Patient
from apps.patients.selectors import patients_visible_to
from apps.work_items.models import WorkItem, WorkItemKind
from apps.work_items.selectors import work_items_visible_to
from config.api.exceptions import ApiProblem


def work_item_snapshot(item: WorkItem) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "title": item.title,
        "due_at": item.due_at,
        "assignee_id": item.assignee_id,
        "patient_id": item.patient_id,
        "comment": item.comment,
        "is_important": item.is_important,
        "is_completed": item.is_completed,
        "completed_at": item.completed_at,
        "completed_by_id": item.completed_by_id,
        "version": item.version,
    }


def _active_assignee(assignee_id: int) -> User:
    assignee = User.objects.filter(pk=assignee_id, is_active=True).first()
    if assignee is None:
        raise ApiProblem(
            code="work_item_assignee_invalid",
            message="Відповідальний працівник недоступний.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"assignee_id": ["Оберіть активного працівника."]},
        )
    return assignee


def _visible_patient(actor: User, patient_id: UUID) -> Patient:
    patient = patients_visible_to(actor).filter(pk=patient_id).first()
    if patient is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return patient


def _validate_relationship(
    *,
    kind: str,
    assignee: User,
    patient: Patient | None,
) -> None:
    if kind == WorkItemKind.CALLBACK and patient is None:
        raise ApiProblem(
            code="work_item_patient_required",
            message="Для справи «Перетелефонувати» потрібен пацієнт.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"patient_id": ["Оберіть пацієнта."]},
        )
    if (
        patient is not None
        and assignee.role == UserRole.PODOLOGIST
        and patient.primary_podologist_id != assignee.pk
    ):
        raise ApiProblem(
            code="work_item_assignee_patient_scope_violation",
            message="Подологу можна призначити справу лише щодо його пацієнта.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"assignee_id": ["Оберіть відповідального з доступом до пацієнта."]},
        )


@transaction.atomic
def create_work_item(
    *,
    actor: User,
    correlation_id: str,
    data: dict[str, Any],
) -> WorkItem:
    assignee = _active_assignee(data.pop("assignee_id"))
    patient_id = data.pop("patient_id", None)
    patient = _visible_patient(actor, patient_id) if patient_id is not None else None
    _validate_relationship(kind=data["kind"], assignee=assignee, patient=patient)
    item = WorkItem.objects.create(
        **data,
        assignee=assignee,
        patient=patient,
        created_by=actor,
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.WORK_ITEM_CREATED,
        object_type="work_item",
        object_id=item.pk,
        object_label=item.title,
        correlation_id=correlation_id,
        after=work_item_snapshot(item),
        description="Створено внутрішню справу.",
    )
    enqueue_work_item_telegram_delivery_on_commit(item)
    return item


@transaction.atomic
def update_work_item(
    *,
    actor: User,
    work_item_id: UUID,
    correlation_id: str,
    data: dict[str, Any],
) -> WorkItem:
    requested_version = data.pop("version")
    item = (
        work_items_visible_to(actor).select_for_update(of=("self",)).filter(pk=work_item_id).first()
    )
    if item is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if item.version != requested_version:
        raise ApiProblem(
            code="work_item_version_conflict",
            message="Справу вже змінив інший користувач. Оновіть список і повторіть дію.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія справи застаріла."]},
        )
    reopening = item.is_completed and data.get("is_completed") is False
    detail_fields = {
        "kind",
        "title",
        "due_at",
        "assignee_id",
        "patient_id",
        "comment",
        "is_important",
    }
    if item.is_completed and detail_fields.intersection(data) and not reopening:
        raise ApiProblem(
            code="work_item_completed",
            message="Спершу поверніть завершену справу в роботу.",
            status_code=status.HTTP_409_CONFLICT,
        )

    assignee = item.assignee
    if "assignee_id" in data:
        assignee = _active_assignee(data["assignee_id"])
    patient = item.patient
    if "patient_id" in data:
        patient_id = data["patient_id"]
        patient = _visible_patient(actor, patient_id) if patient_id is not None else None
    kind = data.get("kind", item.kind)
    _validate_relationship(kind=kind, assignee=assignee, patient=patient)

    before = work_item_snapshot(item)
    candidate = {
        "kind": kind,
        "title": data.get("title", item.title),
        "due_at": data.get("due_at", item.due_at),
        "assignee_id": assignee.pk,
        "patient_id": patient.pk if patient is not None else None,
        "comment": data.get("comment", item.comment),
        "is_important": data.get("is_important", item.is_important),
        "is_completed": data.get("is_completed", item.is_completed),
    }
    unchanged = all(before[key] == value for key, value in candidate.items())
    if unchanged:
        raise ApiProblem(
            code="work_item_no_changes",
            message="У справі немає нових змін.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"non_field_errors": ["Змініть хоча б одне поле."]},
        )

    item.kind = candidate["kind"]
    item.title = candidate["title"]
    item.due_at = candidate["due_at"]
    item.assignee = assignee
    item.patient = patient
    item.comment = candidate["comment"]
    item.is_important = candidate["is_important"]
    completing = not item.is_completed and candidate["is_completed"]
    reopening = item.is_completed and not candidate["is_completed"]
    item.is_completed = candidate["is_completed"]
    if completing:
        item.completed_at = timezone.now()
        item.completed_by = actor
    elif reopening:
        item.completed_at = None
        item.completed_by = None
    item.version += 1
    item.save()

    if completing:
        action = AuditAction.WORK_ITEM_COMPLETED
        description = "Внутрішню справу виконано."
    elif reopening:
        action = AuditAction.WORK_ITEM_REOPENED
        description = "Внутрішню справу повернуто в роботу."
    else:
        action = AuditAction.WORK_ITEM_UPDATED
        description = "Оновлено внутрішню справу."
    record_audit_event(
        actor=actor,
        action=action,
        object_type="work_item",
        object_id=item.pk,
        object_label=item.title,
        correlation_id=correlation_id,
        before=before,
        after=work_item_snapshot(item),
        description=description,
    )
    enqueue_work_item_telegram_delivery_on_commit(item)
    return item
