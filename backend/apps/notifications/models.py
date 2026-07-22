from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class NotificationKind(models.TextChoices):
    APPOINTMENT_ARRIVED = "appointment_arrived", "Пацієнт прибув"
    APPOINTMENT_UPCOMING = "appointment_upcoming", "Запис незабаром"
    APPOINTMENT_CANCELED = "appointment_canceled", "Запис скасовано"
    WORK_ITEM_OVERDUE = "work_item_overdue", "Справу прострочено"
    VISIT_PAYMENT_READY = "visit_payment_ready", "Прийом очікує оплати"
    PASSWORD_RESET_REQUESTED = "password_reset_requested", "Запит на скидання пароля"


class NotificationTone(models.TextChoices):
    SAGE = "sage", "Зелений"
    SAND = "sand", "Пісочний"
    BLUE = "blue", "Синій"
    LILAC = "lilac", "Ліловий"
    CORAL = "coral", "Кораловий"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    event_key = models.CharField(max_length=255, editable=False)
    kind = models.CharField(max_length=40, choices=NotificationKind.choices, editable=False)
    title = models.CharField(max_length=200, editable=False)
    message = models.CharField(max_length=500, editable=False)
    tone = models.CharField(
        max_length=16,
        choices=NotificationTone.choices,
        default=NotificationTone.SAGE,
        editable=False,
    )
    is_important = models.BooleanField(default=False, editable=False)
    deep_link = models.CharField(max_length=500, default="/", editable=False)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("recipient", "-created_at", "-id"),
                name="notif_recipient_created_idx",
            ),
            models.Index(
                fields=("recipient", "read_at", "-created_at"),
                name="notif_recipient_read_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("recipient", "event_key"),
                name="notif_recipient_event_unique",
            ),
            models.CheckConstraint(
                condition=~Q(event_key=""),
                name="notif_event_key_nonempty",
            ),
            models.CheckConstraint(
                condition=Q(deep_link__startswith="/") & ~Q(deep_link__startswith="//"),
                name="notif_deep_link_relative",
            ),
            models.CheckConstraint(
                condition=Q(read_at__isnull=True) | Q(read_at__gte=F("created_at")),
                name="notif_read_at_after_create",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recipient_id} · {self.title}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.event_key = self.event_key.strip()
        self.title = self.title.strip()
        self.message = self.message.strip()
        self.deep_link = self.deep_link.strip()
        super().save(*args, **kwargs)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
