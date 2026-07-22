import uuid
from typing import Any

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models import Q
from django.db.models.functions import Upper

from apps.clinic.models import Service
from apps.inventory.models import Material, MaterialLot
from apps.patients.models import Patient
from apps.scheduling.models import Appointment


class VisitStatus(models.TextChoices):
    DRAFT = "DRAFT", "Чернетка"
    COMPLETED = "COMPLETED", "Завершено"


class VisitPhotoKind(models.TextChoices):
    BEFORE = "BEFORE", "До процедури"
    AFTER = "AFTER", "Після процедури"


class VisitPhotoPreviewStatus(models.TextChoices):
    PROCESSING = "PROCESSING", "Обробляється"
    READY = "READY", "Готове"
    FAILED = "FAILED", "Помилка"


class VisitPhotoIntentStatus(models.TextChoices):
    PENDING = "PENDING", "Очікує файл"
    FINALIZED = "FINALIZED", "Завершено"


class DetectedCondition(models.TextChoices):
    HYPERKERATOSIS = "HYPERKERATOSIS", "Гіперкератоз"
    FISSURES = "FISSURES", "Тріщини"
    NAIL_DEFORMATION = "NAIL_DEFORMATION", "Деформація нігтя"
    REDNESS = "REDNESS", "Почервоніння"
    EDEMA = "EDEMA", "Набряк"
    TENDERNESS = "TENDERNESS", "Болісність"


def visit_public_number(visit_id: uuid.UUID) -> str:
    return f"V-{visit_id.hex[:12].upper()}"


class Visit(models.Model):
    """Versioned clinical workspace created once for an appointment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_number = models.CharField(max_length=24, unique=True, editable=False)
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.PROTECT,
        related_name="visit",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="visits",
    )
    specialist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clinical_visits",
    )
    status = models.CharField(
        max_length=16,
        choices=VisitStatus.choices,
        default=VisitStatus.DRAFT,
    )
    complaints = models.TextField(blank=True, max_length=4000)
    has_no_complaints = models.BooleanField(default=False)
    objective_examination = models.TextField(blank=True, max_length=10000)
    detected_conditions = models.JSONField(default=list, blank=True)
    podologist_notes = models.TextField(blank=True, max_length=10000)
    total_minor = models.PositiveBigIntegerField(blank=True, null=True, editable=False)
    payment_handoff_requested = models.BooleanField(default=False, editable=False)
    version = models.PositiveIntegerField(default=1)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="started_visits",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-started_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(has_no_complaints=True) & Q(complaints=""))
                    | (Q(has_no_complaints=False) & ~Q(complaints=""))
                ),
                name="visits_complaints_xor",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="visits_version_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("specialist", "status"), name="visits_specialist_status_idx"),
            models.Index(fields=("patient", "started_at"), name="visits_patient_started_idx"),
            models.Index(
                fields=("patient", "status", "-completed_at", "-id"),
                name="visits_patient_history_idx",
            ),
            GinIndex(
                OpClass(Upper("public_number"), name="gin_trgm_ops"),
                name="visits_number_search_gin",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_number} · {self.patient.display_name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.public_number:
            self.public_number = visit_public_number(self.id)
        self.complaints = self.complaints.strip()
        self.objective_examination = self.objective_examination.strip()
        self.podologist_notes = self.podologist_notes.strip()
        super().save(*args, **kwargs)


class VisitServiceLine(models.Model):
    """Service draft line with stable billing snapshots for later completion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="service_lines")
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="visit_draft_lines",
    )
    service_code = models.CharField(max_length=32, editable=False)
    service_name = models.CharField(max_length=160, editable=False)
    duration_minutes = models.PositiveSmallIntegerField(editable=False)
    price_minor = models.PositiveBigIntegerField(editable=False)
    quantity = models.PositiveSmallIntegerField(default=1)
    is_primary = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_primary", "service_name", "service_code", "id")
        indexes = [
            GinIndex(
                OpClass(Upper("service_code"), name="gin_trgm_ops"),
                OpClass(Upper("service_name"), name="gin_trgm_ops"),
                name="visits_service_search_gin",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("visit", "service"),
                name="visits_service_line_unique",
            ),
            models.UniqueConstraint(
                fields=("visit",),
                condition=Q(is_primary=True),
                name="visits_one_primary_service",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="visits_service_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · {self.service_code} × {self.quantity}"

    @property
    def line_total_minor(self) -> int:
        return self.price_minor * self.quantity


class VisitMaterialLine(models.Model):
    """Material draft selection; stock is only projected and never mutated here."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="material_lines")
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="visit_draft_lines",
    )
    lot = models.ForeignKey(
        MaterialLot,
        on_delete=models.PROTECT,
        related_name="visit_draft_lines",
    )
    material_sku = models.CharField(max_length=48, editable=False)
    material_name = models.CharField(max_length=180, editable=False)
    material_unit = models.CharField(max_length=24, editable=False)
    lot_number = models.CharField(max_length=80, editable=False)
    expires_on = models.DateField(null=True, blank=True, editable=False)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("material_name", "material_sku", "lot_number", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("visit", "lot"),
                name="visits_material_lot_line_unique",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="visits_material_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.visit.public_number} · {self.material_sku} · "
            f"{self.lot_number} × {self.quantity}"
        )


class VisitRecommendation(models.Model):
    """Clinical recommendation authored when a visit is completed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name="recommendations")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visit_recommendations",
    )
    text = models.TextField(max_length=10000)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~Q(text=""),
                name="visits_recommendation_text_nonempty",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="visits_recommendation_version_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · {self.author.display_name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.text = self.text.strip()
        super().save(*args, **kwargs)


class VisitFinishResult(models.Model):
    """Replay-safe completion result stored once per visit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.OneToOneField(
        Visit,
        on_delete=models.PROTECT,
        related_name="finish_result",
    )
    idempotency_key = models.CharField(max_length=128)
    payload_hash = models.CharField(max_length=64, editable=False)
    result = models.JSONField(default=dict, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("visit", "idempotency_key"),
                name="visits_finish_visit_key_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · {self.idempotency_key}"


class VisitPhoto(models.Model):
    """Finalized private medical photo attached to exactly one visit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="photos")
    kind = models.CharField(max_length=8, choices=VisitPhotoKind.choices)
    object_key = models.CharField(max_length=255, unique=True, editable=False)
    content_type = models.CharField(max_length=32, editable=False)
    size = models.PositiveIntegerField(editable=False)
    width = models.PositiveIntegerField(editable=False)
    height = models.PositiveIntegerField(editable=False)
    original_name = models.CharField(max_length=255, editable=False)
    preview_object_key = models.CharField(max_length=255, blank=True, editable=False)
    preview_content_type = models.CharField(max_length=32, blank=True, editable=False)
    preview_status = models.CharField(
        max_length=16,
        choices=VisitPhotoPreviewStatus.choices,
        default=VisitPhotoPreviewStatus.PROCESSING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_visit_photos",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("kind", "created_at", "id")
        indexes = [
            models.Index(fields=("visit", "kind", "created_at"), name="visits_photo_kind_idx")
        ]
        constraints = [
            models.CheckConstraint(condition=Q(size__gt=0), name="visits_photo_size_positive"),
            models.CheckConstraint(condition=Q(width__gt=0), name="visits_photo_width_positive"),
            models.CheckConstraint(condition=Q(height__gt=0), name="visits_photo_height_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · {self.kind} · {self.pk}"


class VisitPhotoUploadIntent(models.Model):
    """Short-lived reservation that binds one upload to visit, kind and actor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="photo_upload_intents")
    kind = models.CharField(max_length=8, choices=VisitPhotoKind.choices)
    status = models.CharField(
        max_length=16,
        choices=VisitPhotoIntentStatus.choices,
        default=VisitPhotoIntentStatus.PENDING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visit_photo_upload_intents",
    )
    finalized_photo = models.OneToOneField(
        VisitPhoto,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="upload_intent",
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [
            models.Index(
                fields=("status", "expires_at"),
                name="visits_photo_intent_exp_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · {self.kind} · {self.status}"
