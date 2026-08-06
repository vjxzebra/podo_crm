import uuid
from typing import Any

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower, Trim


class ProtectedDiscountError(RuntimeError):
    pass


class ImmutableLoyaltyError(RuntimeError):
    pass


class DiscountQuerySet(models.QuerySet["Discount"]):
    def delete(self) -> tuple[int, dict[str, int]]:
        raise ProtectedDiscountError("Discounts cannot be deleted; deactivate them instead.")


class Discount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    percent = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DiscountQuerySet.as_manager()

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=~Q(name="") & Q(name=Trim("name")),
                name="discounts_name_nonempty",
            ),
            models.CheckConstraint(
                condition=Q(percent__gte=1, percent__lte=99),
                name="discounts_percent_between_1_and_99",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="discounts_version_positive",
            ),
            models.UniqueConstraint(
                Lower("name"),
                name="discounts_name_ci_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} · {self.percent}%"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.name = self.name.strip()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ProtectedDiscountError("Discounts cannot be deleted; deactivate them instead.")


class LoyaltyPolicy(models.Model):
    key = models.CharField(primary_key=True, max_length=32, default="default", editable=False)
    is_active = models.BooleanField(default=False)
    every_n = models.PositiveIntegerField(default=5)
    discount = models.ForeignKey(
        Discount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="loyalty_policies",
    )
    version = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(key="default"),
                name="discounts_loyalty_policy_singleton_key",
            ),
            models.CheckConstraint(
                condition=Q(every_n__gt=0),
                name="discounts_loyalty_every_n_positive",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="discounts_loyalty_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(is_active=False)
                | (Q(discount__isnull=False) & Q(started_at__isnull=False)),
                name="discounts_active_loyalty_configured",
            ),
        ]

    def __str__(self) -> str:
        return f"Loyalty every {self.every_n} · {'active' if self.is_active else 'inactive'}"

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ProtectedDiscountError("The singleton loyalty policy cannot be deleted.")


class PatientLoyaltyStateQuerySet(models.QuerySet["PatientLoyaltyState"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutableLoyaltyError("Loyalty counters must advance through visit finish.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableLoyaltyError("Loyalty counters cannot be deleted.")


class PatientLoyaltyState(models.Model):
    patient = models.OneToOneField(
        "patients.Patient",
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="loyalty_state",
    )
    completed_count = models.PositiveBigIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PatientLoyaltyStateQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="discounts_loyalty_state_version_positive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.patient.public_number} · {self.completed_count}"

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableLoyaltyError("Loyalty counters cannot be deleted.")


class VisitLoyaltyEventQuerySet(models.QuerySet["VisitLoyaltyEvent"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutableLoyaltyError("Loyalty events are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableLoyaltyError("Loyalty events are append-only.")


class VisitLoyaltyEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.OneToOneField(
        "visits.Visit",
        on_delete=models.PROTECT,
        related_name="loyalty_event",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        related_name="loyalty_events",
    )
    sequence_number = models.PositiveBigIntegerField()
    eligible = models.BooleanField()
    every_n_snapshot = models.PositiveIntegerField()
    discount = models.ForeignKey(
        Discount,
        on_delete=models.PROTECT,
        related_name="loyalty_events",
    )
    discount_name_snapshot = models.CharField(max_length=120)
    discount_percent_snapshot = models.PositiveSmallIntegerField()
    policy_started_at_snapshot = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = VisitLoyaltyEventQuerySet.as_manager()

    class Meta:
        ordering = ("patient_id", "sequence_number")
        constraints = [
            models.UniqueConstraint(
                fields=("patient", "sequence_number"),
                name="discounts_patient_loyalty_sequence_unique",
            ),
            models.CheckConstraint(
                condition=Q(sequence_number__gt=0, every_n_snapshot__gt=0),
                name="discounts_loyalty_event_ordinals_positive",
            ),
            models.CheckConstraint(
                condition=Q(discount_percent_snapshot__gte=1, discount_percent_snapshot__lte=99),
                name="discounts_loyalty_event_percent_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · #{self.sequence_number}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableLoyaltyError("Loyalty events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableLoyaltyError("Loyalty events are append-only.")
