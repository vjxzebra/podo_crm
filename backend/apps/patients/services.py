from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.accounts.models import User, UserRole
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.patients.models import Patient, PatientMedicalProfile
from apps.patients.normalization import normalize_phone
from apps.patients.selectors import patients_visible_to
from config.api.exceptions import ApiProblem


@dataclass(frozen=True)
class PatientCreateResult:
    patient: Patient
    possible_duplicates: tuple[Patient, ...]


@transaction.atomic
def create_patient(
    *,
    actor: User,
    correlation_id: str,
    data: dict[str, Any],
) -> PatientCreateResult:
    requested_podologist = data.pop("primary_podologist", None)
    if actor.role == UserRole.PODOLOGIST:
        if requested_podologist is not None and requested_podologist.pk != actor.pk:
            raise ApiProblem(
                code="patient_podologist_scope_violation",
                message="Подолог може призначити пацієнта лише собі.",
                status_code=422,
                fields={"primary_podologist_id": ["Оберіть власний профіль подолога."]},
            )
        primary_podologist: User | None = actor
    else:
        primary_podologist = requested_podologist

    normalized_phone = normalize_phone(str(data["phone"]))
    duplicate_ids = tuple(
        patients_visible_to(actor)
        .filter(normalized_phone=normalized_phone)
        .values_list("pk", flat=True)[:5]
    )
    patient = Patient.objects.create(
        **data,
        primary_podologist=primary_podologist,
        created_by=actor,
    )
    PatientMedicalProfile.objects.create(patient=patient)
    record_audit_event(
        actor=actor,
        action=AuditAction.PATIENT_CREATED,
        object_type="patient",
        object_id=patient.pk,
        object_label=patient.display_name,
        correlation_id=correlation_id,
        after={
            "public_number": patient.public_number,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "phone": patient.phone,
            "primary_podologist_id": patient.primary_podologist_id,
        },
        description="Створено картку пацієнта.",
    )
    duplicates = tuple(
        patients_visible_to(actor).filter(pk__in=duplicate_ids).order_by("-created_at", "-id")
    )
    return PatientCreateResult(patient=patient, possible_duplicates=duplicates)


def _profile_snapshot(patient: Patient) -> dict[str, Any]:
    profile = getattr(patient, "medical_profile", None)
    if profile is None:
        return {"allergies": [], "chronic_conditions": [], "notes": ""}
    return {
        "allergies": profile.allergies,
        "chronic_conditions": profile.chronic_conditions,
        "notes": profile.notes,
    }


def _patient_snapshot(patient: Patient, *, include_medical: bool) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "public_number": patient.public_number,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "phone": patient.phone,
        "birth_date": patient.birth_date,
        "email": patient.email,
        "note": patient.note,
        "primary_podologist_id": patient.primary_podologist_id,
    }
    if include_medical:
        snapshot["medical_profile"] = _profile_snapshot(patient)
    return snapshot


@transaction.atomic
def update_patient(
    *,
    actor: User,
    patient_id: UUID,
    correlation_id: str,
    data: dict[str, Any],
) -> Patient:
    try:
        patient = patients_visible_to(actor).select_for_update(of=("self",)).get(pk=patient_id)
    except Patient.DoesNotExist as exc:
        raise ApiProblem(
            code="not_found",
            message="Ресурс не знайдено.",
            status_code=404,
        ) from exc

    include_medical = actor.role in {UserRole.ADMIN, UserRole.PODOLOGIST}
    before = _patient_snapshot(patient, include_medical=include_medical)
    medical_data = data.pop("medical_profile", None)

    if "primary_podologist" in data:
        requested_podologist = data["primary_podologist"]
        if actor.role == UserRole.PODOLOGIST and (
            requested_podologist is None or requested_podologist.pk != actor.pk
        ):
            raise ApiProblem(
                code="patient_podologist_scope_violation",
                message="Подолог не може передати або зняти власного пацієнта.",
                status_code=422,
                fields={"primary_podologist_id": ["Оберіть власний профіль подолога."]},
            )

    for field, value in data.items():
        setattr(patient, field, value)
    patient.save()

    if medical_data is not None:
        if not include_medical:
            raise ApiProblem(
                code="patient_medical_access_denied",
                message="Медичні дані недоступні для цієї ролі.",
                status_code=403,
            )
        profile, _ = PatientMedicalProfile.objects.get_or_create(patient=patient)
        for field, value in medical_data.items():
            setattr(profile, field, value)
        profile.notes = profile.notes.strip()
        profile.save()

    patient.refresh_from_db()
    after = _patient_snapshot(patient, include_medical=include_medical)
    record_audit_event(
        actor=actor,
        action=AuditAction.PATIENT_UPDATED,
        object_type="patient",
        object_id=patient.pk,
        object_label=patient.display_name,
        correlation_id=correlation_id,
        before=before,
        after=after,
        description="Оновлено картку пацієнта.",
    )
    return patient
