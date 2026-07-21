import uuid
from collections.abc import Collection, Iterable
from typing import Any

from django.db import models
from django.db.models import F
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


class SystemStatusProtectedError(RuntimeError):
    pass


class AppointmentStatusConfigQuerySet(models.QuerySet["AppointmentStatusConfig"]):
    def update(self, **kwargs: Any) -> int:
        if "code" in kwargs:
            raise SystemStatusProtectedError("System status codes are immutable.")
        return super().update(**kwargs)

    def delete(self) -> tuple[int, dict[str, int]]:
        raise SystemStatusProtectedError("System status configurations cannot be deleted.")

    def bulk_update(
        self,
        objs: Iterable["AppointmentStatusConfig"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        if "code" in fields:
            raise SystemStatusProtectedError("System status codes are immutable.")
        return super().bulk_update(objs, fields, batch_size)


class AppointmentStatusConfig(models.Model):
    code = models.CharField(primary_key=True, editable=False, max_length=32)
    label = models.CharField(max_length=80)
    color = models.CharField(max_length=7)
    manual_admin = models.BooleanField(default=True)
    manual_reception = models.BooleanField(default=False)
    manual_podologist = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AppointmentStatusConfigQuerySet.as_manager()

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return f"{self.code} · {self.label}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding and getattr(self, "_original_code", self.code) != self.code:
            raise SystemStatusProtectedError("System status codes are immutable.")
        super().save(*args, **kwargs)
        self._original_code = self.code

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise SystemStatusProtectedError("System status configurations cannot be deleted.")

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[Any],
    ) -> "AppointmentStatusConfig":
        instance = super().from_db(db, field_names, values)
        instance._original_code = instance.code
        return instance


class ClinicWorkday(models.Model):
    weekday = models.PositiveSmallIntegerField(primary_key=True)
    is_working = models.BooleanField(default=False)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("weekday",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekday__gte=0, weekday__lte=6),
                name="clinic_workday_weekday_range",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        is_working=False,
                        start_time__isnull=True,
                        end_time__isnull=True,
                    )
                    | models.Q(
                        is_working=True,
                        start_time__isnull=False,
                        end_time__isnull=False,
                        start_time__lt=F("end_time"),
                    )
                ),
                name="clinic_workday_valid_hours",
            ),
        ]

    def __str__(self) -> str:
        return f"Weekday {self.weekday}"


class ClinicBreak(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workday = models.ForeignKey(
        ClinicWorkday,
        on_delete=models.CASCADE,
        related_name="breaks",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ("start_time", "end_time", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=F("end_time")),
                name="clinic_break_valid_range",
            )
        ]

    def __str__(self) -> str:
        return f"{self.workday.weekday}: {self.start_time}–{self.end_time}"
