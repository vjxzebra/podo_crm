from typing import Any
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models.functions import Upper

from apps.patients.normalization import normalize_phone


def patient_public_number(patient_id: UUID) -> str:
    return f"P-{patient_id.hex[:12].upper()}"


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    public_number = models.CharField(max_length=24, unique=True, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=32)
    normalized_phone = models.CharField(max_length=16, db_index=True, editable=False)
    birth_date = models.DateField(blank=True, null=True)
    email = models.EmailField(blank=True)
    note = models.TextField(blank=True)
    primary_podologist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="primary_patients",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_patients",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            GinIndex(
                OpClass(Upper("first_name"), name="gin_trgm_ops"),
                OpClass(Upper("last_name"), name="gin_trgm_ops"),
                OpClass(Upper("public_number"), name="gin_trgm_ops"),
                OpClass(Upper("normalized_phone"), name="gin_trgm_ops"),
                name="patients_global_search_gin",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(public_number=""),
                name="patients_public_number_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(normalized_phone=""),
                name="patients_normalized_phone_not_empty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.public_number})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.phone = self.phone.strip()
        self.normalized_phone = normalize_phone(self.phone)
        self.email = self.email.strip().lower()
        self.note = self.note.strip()
        if not self.public_number:
            self.public_number = patient_public_number(self.id)
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class PatientMedicalProfile(models.Model):
    patient = models.OneToOneField(
        Patient,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="medical_profile",
    )
    allergies = models.JSONField(default=list, blank=True)
    chronic_conditions = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Медичний профіль: {self.patient.display_name}"
