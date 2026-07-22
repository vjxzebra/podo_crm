from typing import Any

from django.db.models import Prefetch, QuerySet

from apps.accounts.models import User, UserRole
from apps.patients.models import Patient
from apps.visits.models import (
    Visit,
    VisitPhoto,
    VisitPhotoKind,
    VisitRecommendation,
    VisitServiceLine,
    VisitStatus,
)
from apps.visits.photo_services import photo_read_model

CLINICAL_SUMMARY_MAX_CHARS = 400


def completed_visits_for_patient(
    patient: Patient,
    *,
    medical: bool,
    actor: User | None = None,
) -> QuerySet[Visit]:
    prefetches: list[Prefetch | str] = [
        Prefetch("service_lines", queryset=VisitServiceLine.objects.order_by("-is_primary", "id")),
    ]
    if medical:
        prefetches.extend(
            [
                Prefetch(
                    "photos",
                    queryset=VisitPhoto.objects.select_related("created_by").order_by(
                        "kind", "created_at", "id"
                    ),
                ),
                Prefetch(
                    "recommendations",
                    queryset=VisitRecommendation.objects.select_related("author").order_by(
                        "created_at", "id"
                    ),
                ),
            ]
        )
    queryset = (
        Visit.objects.filter(patient=patient, status=VisitStatus.COMPLETED)
        .filter(completed_at__isnull=False, total_minor__isnull=False)
        .select_related("appointment", "specialist")
        .prefetch_related(*prefetches)
        .order_by("-completed_at", "-id")
    )
    if actor is not None and actor.role == UserRole.PODOLOGIST:
        return queryset.filter(specialist=actor)
    return queryset


def _service_rows(visit: Visit) -> list[dict[str, Any]]:
    return [
        {
            "service_name": line.service_name,
            "quantity": line.quantity,
            "line_total_minor": line.line_total_minor,
        }
        for line in visit.service_lines.all()
    ]


def _base_history_row(visit: Visit) -> dict[str, Any]:
    return {
        "id": visit.pk,
        "public_number": visit.public_number,
        "occurred_at": visit.appointment.starts_at,
        "completed_at": visit.completed_at,
        "status": visit.status,
        "status_label": visit.get_status_display(),
        "services": _service_rows(visit),
        "specialist": {
            "id": visit.specialist_id,
            "display_name": visit.specialist.display_name,
        },
        "total_minor": visit.total_minor or 0,
    }


def visit_history_row(visit: Visit, *, medical: bool) -> dict[str, Any]:
    row = _base_history_row(visit)
    if not medical:
        return row
    photos = list(visit.photos.all())
    recommendations = list(visit.recommendations.all())
    before_count = sum(photo.kind == VisitPhotoKind.BEFORE for photo in photos)
    after_count = sum(photo.kind == VisitPhotoKind.AFTER for photo in photos)
    clinical_summary = visit.podologist_notes or visit.objective_examination or visit.complaints
    if len(clinical_summary) > CLINICAL_SUMMARY_MAX_CHARS:
        clinical_summary = f"{clinical_summary[: CLINICAL_SUMMARY_MAX_CHARS - 1].rstrip()}…"
    row.update(
        {
            "clinical_summary": clinical_summary,
            "has_photos": bool(photos),
            "before_photo_count": before_count,
            "after_photo_count": after_count,
            "recommendations_count": len(recommendations),
        }
    )
    return row


def photo_archive_visit_row(visit: Visit) -> dict[str, Any]:
    photos = sorted(
        visit.photos.all(),
        key=lambda photo: (
            photo.kind != VisitPhotoKind.BEFORE,
            photo.created_at,
            photo.pk,
        ),
    )
    return {
        **_base_history_row(visit),
        "photos": [photo_read_model(photo) for photo in photos],
    }


def recommendation_row(recommendation: VisitRecommendation, *, actor: User) -> dict[str, Any]:
    visit = recommendation.visit
    return {
        "id": recommendation.pk,
        "visit": {
            "id": visit.pk,
            "public_number": visit.public_number,
            "occurred_at": visit.appointment.starts_at,
            "services": [line.service_name for line in visit.service_lines.all()],
        },
        "author": {
            "id": recommendation.author_id,
            "display_name": recommendation.author.display_name,
        },
        "text": recommendation.text,
        "version": recommendation.version,
        "created_at": recommendation.created_at,
        "updated_at": recommendation.updated_at,
        "can_edit": actor.role == UserRole.ADMIN
        or (
            actor.role == UserRole.PODOLOGIST
            and visit.specialist_id == actor.pk
            and recommendation.author_id == actor.pk
        ),
    }


def recommendation_visit_option(visit: Visit) -> dict[str, Any]:
    return {
        "id": visit.pk,
        "public_number": visit.public_number,
        "occurred_at": visit.appointment.starts_at,
        "services": [line.service_name for line in visit.service_lines.all()],
    }


def photo_archive_metadata(
    patient: Patient,
    *,
    actor: User,
    limit: int = 3,
) -> list[dict[str, Any]]:
    visits = completed_visits_for_patient(patient, medical=True, actor=actor).filter(
        photos__isnull=False
    )
    rows: list[dict[str, Any]] = []
    for visit in visits.distinct()[:limit]:
        photos = list(visit.photos.all())
        rows.append(
            {
                "visit_id": visit.pk,
                "occurred_at": visit.appointment.starts_at,
                "caption": next(
                    (line.service_name for line in visit.service_lines.all() if line.is_primary),
                    visit.public_number,
                ),
                "before_count": sum(photo.kind == VisitPhotoKind.BEFORE for photo in photos),
                "after_count": sum(photo.kind == VisitPhotoKind.AFTER for photo in photos),
            }
        )
    return rows
