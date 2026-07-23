from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import models


class WorkItemKind(models.TextChoices):
    CALLBACK = "callback", "Перетелефонувати"
    CONFIRM_APPOINTMENT = "confirm_appointment", "Підтвердити запис"
    MANUAL_MESSAGE = "manual_message", "Написати пацієнту вручну"
    OTHER = "other", "Інша внутрішня справа"


class WorkItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=WorkItemKind.choices)
    title = models.CharField(max_length=200)
    due_at = models.DateTimeField()
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_work_items",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="work_items",
    )
    comment = models.TextField(blank=True)
    is_important = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="completed_work_items",
    )
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_work_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("is_completed", "due_at", "-is_important", "id")
        indexes = [
            models.Index(
                fields=("assignee", "is_completed", "due_at"),
                name="workitem_owner_state_due_idx",
            ),
            models.Index(fields=("is_completed", "due_at"), name="workitem_state_due_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(title=""),
                name="workitem_title_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(kind=WorkItemKind.CALLBACK) | models.Q(patient__isnull=False),
                name="workitem_callback_has_patient",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        is_completed=False,
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                    )
                    | models.Q(
                        is_completed=True,
                        completed_at__isnull=False,
                        completed_by__isnull=False,
                    )
                ),
                name="workitem_completion_consistent",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.title = self.title.strip()
        self.comment = self.comment.strip()
        super().save(*args, **kwargs)
