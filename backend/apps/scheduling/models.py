import uuid
from typing import Any

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models import Q
from django.db.models.functions import Upper

from apps.clinic.models import AppointmentStatusConfig, Room, Service
from apps.patients.models import Patient


def appointment_public_number(appointment_id: uuid.UUID) -> str:
    return f"A-{appointment_id.hex[:12].upper()}"


class Appointment(models.Model):
    """Appointment aggregate protected by specialist and room occupancy constraints."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_number = models.CharField(max_length=24, unique=True, editable=False)
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    specialist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    time_range = DateTimeRangeField()
    duration_minutes = models.PositiveSmallIntegerField()
    service_name_snapshot = models.CharField(max_length=160)
    service_color_snapshot = models.CharField(max_length=7)
    room_label_snapshot = models.CharField(max_length=100)
    status = models.ForeignKey(
        AppointmentStatusConfig,
        db_column="status",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    complaints = models.TextField(blank=True, max_length=4000)
    has_no_complaints = models.BooleanField(default=False)
    comment = models.TextField(blank=True, max_length=4000)
    cancellation_reason = models.TextField(blank=True, max_length=1000)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("time_range", "specialist_id", "id")
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0),
                name="scheduling_appointment_duration_positive",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(has_no_complaints=True) & Q(complaints=""))
                    | (Q(has_no_complaints=False) & ~Q(complaints=""))
                ),
                name="scheduling_appointment_complaints_xor",
            ),
            ExclusionConstraint(
                name="scheduling_no_specialist_overlap",
                expressions=(
                    ("specialist", RangeOperators.EQUAL),
                    ("time_range", RangeOperators.OVERLAPS),
                ),
                condition=~Q(status="CANCELED"),
            ),
            ExclusionConstraint(
                name="scheduling_no_room_overlap",
                expressions=(
                    ("room", RangeOperators.EQUAL),
                    ("time_range", RangeOperators.OVERLAPS),
                ),
                condition=~Q(status="CANCELED"),
            ),
        ]
        indexes = [
            models.Index(fields=("specialist",), name="scheduling_specialist_idx"),
            models.Index(fields=("room",), name="scheduling_room_idx"),
            GinIndex(
                OpClass(Upper("public_number"), name="gin_trgm_ops"),
                OpClass(Upper("service_name_snapshot"), name="gin_trgm_ops"),
                name="scheduling_global_search_gin",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_number} · {self.patient.display_name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.public_number:
            self.public_number = appointment_public_number(self.id)
        self.complaints = self.complaints.strip()
        self.comment = self.comment.strip()
        self.cancellation_reason = self.cancellation_reason.strip()
        super().save(*args, **kwargs)

    @property
    def starts_at(self) -> Any:
        return self.time_range.lower

    @property
    def ends_at(self) -> Any:
        return self.time_range.upper


class AppointmentServiceLine(models.Model):
    """Ordered, immutable service snapshot selected for an appointment."""

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="service_lines",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="appointment_service_lines",
    )
    position = models.PositiveSmallIntegerField()
    duration_minutes = models.PositiveSmallIntegerField()
    service_name_snapshot = models.CharField(max_length=160)
    service_color_snapshot = models.CharField(max_length=7)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("appointment", "service"),
                name="scheduling_appointment_service_unique",
            ),
            models.UniqueConstraint(
                fields=("appointment", "position"),
                name="scheduling_appointment_service_position_unique",
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0),
                name="scheduling_appointment_service_duration_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.appointment.public_number} · {self.service_name_snapshot}"
