from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User, UserRole
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.visits.models import Visit, VisitRecommendation, VisitStatus
from config.api.exceptions import ApiProblem


def recommendation_read_model(recommendation: VisitRecommendation) -> dict[str, Any]:
    return {
        "id": recommendation.pk,
        "author_id": recommendation.author_id,
        "author_name": recommendation.author.display_name,
        "text": recommendation.text,
        "version": recommendation.version,
        "created_at": recommendation.created_at,
        "updated_at": recommendation.updated_at,
    }


def _require_medical_role(actor: User) -> None:
    if actor.role not in {UserRole.ADMIN, UserRole.PODOLOGIST}:
        raise ApiProblem(
            code="patient_medical_access_denied",
            message="Медичні рекомендації недоступні для цієї ролі.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def get_visit_recommendation(
    *,
    actor: User,
    visit_id: UUID,
    recommendation_id: UUID,
) -> VisitRecommendation:
    _require_medical_role(actor)
    queryset = VisitRecommendation.objects.select_related("author").filter(
        pk=recommendation_id,
        visit_id=visit_id,
        visit__status=VisitStatus.COMPLETED,
        visit__completed_at__isnull=False,
        visit__total_minor__isnull=False,
    )
    if actor.role == UserRole.PODOLOGIST:
        queryset = queryset.filter(visit__specialist=actor)
    recommendation = queryset.first()
    if recommendation is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return recommendation


def _locked_writable_visit(*, actor: User, visit_id: UUID) -> Visit:
    _require_medical_role(actor)
    queryset = Visit.objects.select_related("patient", "specialist").select_for_update(of=("self",))
    if actor.role == UserRole.PODOLOGIST:
        queryset = queryset.filter(specialist=actor)
    visit = queryset.filter(pk=visit_id).first()
    if visit is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if (
        visit.status != VisitStatus.COMPLETED
        or visit.completed_at is None
        or visit.total_minor is None
    ):
        raise ApiProblem(
            code="recommendation_visit_not_completed",
            message="Рекомендацію можна додати лише до завершеного відвідування.",
            status_code=status.HTTP_409_CONFLICT,
        )
    return visit


@transaction.atomic
def create_visit_recommendation(
    *,
    actor: User,
    visit_id: UUID,
    text: str,
    correlation_id: str,
) -> VisitRecommendation:
    visit = _locked_writable_visit(actor=actor, visit_id=visit_id)
    recommendation = VisitRecommendation.objects.create(
        visit=visit,
        author=actor,
        text=text.strip(),
    )
    record_audit_event(
        actor=actor,
        action=AuditAction.VISIT_RECOMMENDATION_CREATED,
        object_type="visit_recommendation",
        object_id=recommendation.pk,
        object_label=f"{visit.public_number} · рекомендація",
        correlation_id=correlation_id,
        before={},
        after=recommendation_read_model(recommendation),
        description="Додано рекомендацію до завершеного відвідування.",
    )
    return recommendation


@transaction.atomic
def update_visit_recommendation(
    *,
    actor: User,
    visit_id: UUID,
    recommendation_id: UUID,
    requested_version: int,
    text: str,
    correlation_id: str,
) -> VisitRecommendation:
    visit = _locked_writable_visit(actor=actor, visit_id=visit_id)
    queryset = VisitRecommendation.objects.select_related("author").select_for_update(of=("self",))
    if actor.role == UserRole.PODOLOGIST:
        queryset = queryset.filter(author=actor)
    recommendation = queryset.filter(pk=recommendation_id, visit=visit).first()
    if recommendation is None:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if recommendation.version != requested_version:
        raise ApiProblem(
            code="recommendation_version_conflict",
            message="Рекомендацію вже змінив інший користувач. Оновіть дані.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"version": ["Версія рекомендації застаріла."]},
        )
    before = recommendation_read_model(recommendation)
    recommendation.text = text.strip()
    recommendation.version += 1
    recommendation.updated_at = timezone.now()
    recommendation.save(update_fields=("text", "version", "updated_at"))
    record_audit_event(
        actor=actor,
        action=AuditAction.VISIT_RECOMMENDATION_UPDATED,
        object_type="visit_recommendation",
        object_id=recommendation.pk,
        object_label=f"{visit.public_number} · рекомендація",
        correlation_id=correlation_id,
        before=before,
        after=recommendation_read_model(recommendation),
        description="Оновлено рекомендацію завершеного відвідування.",
    )
    return recommendation
