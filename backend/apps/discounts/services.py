import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.discounts.models import (
    Discount,
    LoyaltyPolicy,
    PatientLoyaltyState,
    VisitLoyaltyEvent,
)
from config.api.exceptions import ApiProblem


def discount_snapshot(discount: Discount) -> dict[str, Any]:
    return {
        "id": discount.pk,
        "name": discount.name,
        "percent": discount.percent,
        "is_active": discount.is_active,
        "version": discount.version,
    }


def loyalty_policy_snapshot(policy: LoyaltyPolicy) -> dict[str, Any]:
    return {
        "key": policy.pk,
        "is_active": policy.is_active,
        "every_n": policy.every_n,
        "discount_id": policy.discount_id,
        "version": policy.version,
        "started_at": policy.started_at,
    }


def visit_loyalty_preview(*, visit_id: uuid.UUID, patient_id: uuid.UUID) -> dict[str, Any]:
    """Read-only loyalty projection for one visit.

    A finished visit reports its immutable event; a draft reports the ordinal and
    automatic discount the finish transaction would apply right now. The preview
    never locks or advances the counter — `create_visit_pricing` stays authoritative.
    """
    event = VisitLoyaltyEvent.objects.filter(visit_id=visit_id).first()
    if event is not None:
        applied = None
        if event.eligible:
            applied = {
                "id": event.discount_id,
                "name": event.discount_name_snapshot,
                "percent": event.discount_percent_snapshot,
            }
        return {
            "is_active": True,
            "every_n": event.every_n_snapshot,
            "visit_number": event.sequence_number,
            "eligible": event.eligible,
            "discount": applied,
        }

    policy = LoyaltyPolicy.objects.select_related("discount").filter(key="default").first()
    if policy is None or not policy.is_active or policy.discount is None:
        return {
            "is_active": False,
            "every_n": policy.every_n if policy is not None else None,
            "visit_number": None,
            "eligible": False,
            "discount": None,
        }

    completed_count = (
        PatientLoyaltyState.objects.filter(patient_id=patient_id)
        .values_list("completed_count", flat=True)
        .first()
    )
    visit_number = (completed_count or 0) + 1
    eligible = visit_number % policy.every_n == 0
    forecast = None
    if eligible:
        forecast = {
            "id": policy.discount.pk,
            "name": policy.discount.name,
            "percent": policy.discount.percent,
        }
    return {
        "is_active": True,
        "every_n": policy.every_n,
        "visit_number": visit_number,
        "eligible": eligible,
        "discount": forecast,
    }


def _stale(resource: str) -> ApiProblem:
    return ApiProblem(
        code="stale_version",
        message=f"{resource} уже змінено. Оновіть дані та повторіть дію.",
        status_code=status.HTTP_409_CONFLICT,
    )


def get_active_discount_for_update(discount_id: uuid.UUID) -> Discount:
    discount = Discount.objects.select_for_update().filter(pk=discount_id, is_active=True).first()
    if discount is None:
        raise ApiProblem(
            code="discount_unavailable",
            message="Обрана знижка неактивна або не існує.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"discount_id": ["Оберіть активну знижку."]},
        )
    return discount


@transaction.atomic
def create_discount(*, actor: User, correlation_id: str, data: dict[str, Any]) -> Discount:
    discount = Discount.objects.create(
        name=data["name"],
        percent=data["percent"],
        is_active=data.get("is_active", True),
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.DISCOUNT_CREATED,
        object_type="discount",
        object_id=discount.pk,
        object_label=discount.name,
        correlation_id=correlation_id,
        before={},
        after=discount_snapshot(discount),
        description="Створено знижку.",
    )
    return discount


@transaction.atomic
def update_discount(
    *,
    actor: User,
    discount_id: uuid.UUID,
    correlation_id: str,
    changes: dict[str, Any],
) -> Discount:
    policy = LoyaltyPolicy.objects.select_for_update().get(key="default")
    discount = Discount.objects.select_for_update().filter(pk=discount_id).first()
    if discount is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    expected_version = changes.pop("version")
    if discount.version != expected_version:
        raise _stale("Знижку")
    if changes.get("is_active") is False and discount.is_active:
        if policy.is_active and policy.discount_id == discount.pk:
            raise ApiProblem(
                code="discount_used_by_active_loyalty",
                message="Спочатку змініть або вимкніть активну програму лояльності.",
                status_code=status.HTTP_409_CONFLICT,
            )
    before = discount_snapshot(discount)
    was_active = discount.is_active
    for field in ("name", "percent", "is_active"):
        if field in changes:
            setattr(discount, field, changes[field])
    discount.version += 1
    discount.save()
    if was_active and not discount.is_active:
        action = AuditAction.DISCOUNT_DEACTIVATED
        description = "Деактивовано знижку без зміни історичних snapshots."
    elif not was_active and discount.is_active:
        action = AuditAction.DISCOUNT_REACTIVATED
        description = "Повторно активовано знижку."
    else:
        action = AuditAction.DISCOUNT_UPDATED
        description = "Оновлено знижку."
    record_audit_event(
        actor=actor,
        action=action,
        object_type="discount",
        object_id=discount.pk,
        object_label=discount.name,
        correlation_id=correlation_id,
        before=before,
        after=discount_snapshot(discount),
        description=description,
    )
    return discount


@transaction.atomic
def update_loyalty_policy(
    *, actor: User, correlation_id: str, changes: dict[str, Any]
) -> LoyaltyPolicy:
    policy = LoyaltyPolicy.objects.select_for_update().get(key="default")
    expected_version = changes.pop("version")
    if policy.version != expected_version:
        raise _stale("Програму лояльності")
    before = loyalty_policy_snapshot(policy)
    discount = policy.discount
    if "discount_id" in changes:
        discount_id = changes.pop("discount_id")
        discount = get_active_discount_for_update(discount_id) if discount_id is not None else None
    is_active = changes.get("is_active", policy.is_active)
    if is_active and (discount is None or not discount.is_active):
        raise ApiProblem(
            code="loyalty_discount_required",
            message="Для активної програми лояльності оберіть активну знижку.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"discount_id": ["Оберіть активну знижку."]},
        )
    policy.discount = discount
    if "every_n" in changes:
        policy.every_n = changes["every_n"]
    policy.is_active = is_active
    if policy.is_active and policy.started_at is None:
        policy.started_at = timezone.now()
    policy.version += 1
    policy.save()
    record_audit_event(
        actor=actor,
        action=AuditAction.LOYALTY_POLICY_UPDATED,
        object_type="loyalty_policy",
        object_id=policy.pk,
        object_label="Програма лояльності",
        correlation_id=correlation_id,
        before=before,
        after=loyalty_policy_snapshot(policy),
        description="Оновлено правила програми лояльності.",
    )
    return policy
