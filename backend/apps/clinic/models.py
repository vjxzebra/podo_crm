import uuid

from django.db import models
from django.db.models.functions import Lower


class ClinicProfile(models.Model):
    key = models.CharField(primary_key=True, default="clinic", editable=False, max_length=16)
    name = models.CharField(max_length=160)
    phone = models.CharField(max_length=32)
    email = models.EmailField()
    address = models.CharField(max_length=255)
    description = models.TextField(blank=True, max_length=1000)
    logo_object_key = models.CharField(blank=True, max_length=255)
    logo_content_type = models.CharField(blank=True, max_length=32)
    logo_size = models.PositiveIntegerField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(key="clinic"),
                name="clinic_profile_singleton_key",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_active", "name", "id")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="clinic_room_name_ci_unique"),
        ]

    def __str__(self) -> str:
        return self.name


class Service(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    duration_minutes = models.PositiveSmallIntegerField()
    price_minor = models.PositiveBigIntegerField()
    color = models.CharField(max_length=7, default="#4F46E5")
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_active", "name", "code", "id")
        constraints = [
            models.UniqueConstraint(Lower("code"), name="clinic_service_code_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0),
                name="clinic_service_duration_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price_minor__gte=0),
                name="clinic_service_price_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"
