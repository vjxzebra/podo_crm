import uuid
from collections.abc import Iterable
from typing import Any

from django.conf import settings
from django.db import models


class AuditEventImmutableError(RuntimeError):
    pass


class AuditEventQuerySet(models.QuerySet["AuditEvent"]):
    def update(self, **kwargs: Any) -> int:
        raise AuditEventImmutableError("Audit events are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise AuditEventImmutableError("Audit events are append-only.")

    def bulk_update(
        self,
        objs: Iterable["AuditEvent"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise AuditEventImmutableError("Audit events are append-only.")


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor_display_name = models.CharField(max_length=255)
    actor_email = models.EmailField(blank=True)
    actor_role = models.CharField(max_length=32)
    section = models.CharField(max_length=32)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=64)
    object_label = models.CharField(max_length=255)
    result = models.CharField(max_length=32, default="success")
    description = models.TextField(blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    note = models.TextField(blank=True)
    correlation_id = models.CharField(max_length=128)
    occurred_at = models.DateTimeField(auto_now_add=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ("-occurred_at", "-id")
        indexes = [
            models.Index(fields=("-occurred_at", "-id"), name="audit_occurred_id_idx"),
            models.Index(fields=("section", "-occurred_at"), name="audit_section_time_idx"),
            models.Index(fields=("actor", "-occurred_at"), name="audit_actor_time_idx"),
            models.Index(fields=("action", "-occurred_at"), name="audit_action_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} · {self.object_type}:{self.object_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise AuditEventImmutableError("Audit events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise AuditEventImmutableError("Audit events are append-only.")
