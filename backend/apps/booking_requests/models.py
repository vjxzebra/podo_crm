import secrets
from collections.abc import Collection, Iterable
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.patients.normalization import normalize_phone


def generate_booking_request_public_number() -> str:
    return f"REQ-{secrets.token_hex(5).upper()}"


class BookingRequestSource(models.TextChoices):
    INSTAGRAM = "INSTAGRAM", "Instagram"
    FACEBOOK = "FACEBOOK", "Facebook"
    WEBSITE = "WEBSITE", "Сайт"


class BookingRequestStatus(models.TextChoices):
    NEW = "NEW", "Нова"
    PROCESSED = "PROCESSED", "Оброблена"


class BookingRequestImmutableError(RuntimeError):
    pass


IMMUTABLE_BOOKING_REQUEST_FIELDS = frozenset(
    {
        "public_number",
        "source",
        "client_name",
        "phone",
        "phone_normalized",
        "service",
        "contact_handle",
        "message",
        "preferred_at",
        "external_reference",
        "created_at",
    }
)

TERMINAL_BOOKING_REQUEST_FIELDS = frozenset(
    {
        "status",
        "processed_by_id",
        "processed_by_display_name",
        "processed_at",
    }
)


class BookingRequestQuerySet(models.QuerySet["BookingRequest"]):
    def update(self, **kwargs: Any) -> int:
        if IMMUTABLE_BOOKING_REQUEST_FIELDS.intersection(kwargs):
            raise BookingRequestImmutableError("Booking request contact data is immutable.")
        return super().update(**kwargs)

    def bulk_update(
        self,
        objs: Iterable["BookingRequest"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        field_names = frozenset(fields)
        if IMMUTABLE_BOOKING_REQUEST_FIELDS.intersection(field_names):
            raise BookingRequestImmutableError("Booking request contact data is immutable.")
        return super().bulk_update(objs, field_names, batch_size=batch_size)


class BookingRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    public_number = models.CharField(
        max_length=14,
        unique=True,
        editable=False,
        default=generate_booking_request_public_number,
    )
    source = models.CharField(max_length=16, choices=BookingRequestSource.choices)
    status = models.CharField(
        max_length=16,
        choices=BookingRequestStatus.choices,
        default=BookingRequestStatus.NEW,
    )
    client_name = models.CharField(max_length=160, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    phone_normalized = models.CharField(
        max_length=16,
        blank=True,
        default="",
        db_index=True,
        editable=False,
    )
    service = models.CharField(max_length=160, blank=True, default="")
    contact_handle = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True, max_length=2000)
    preferred_at = models.DateTimeField(blank=True, null=True)
    external_reference = models.CharField(max_length=160, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="processed_booking_requests",
    )
    processed_by_display_name = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BookingRequestQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(
                fields=("status", "-created_at", "-id"),
                name="booking_req_status_time_idx",
            ),
            models.Index(
                fields=("source", "-created_at", "-id"),
                name="booking_req_source_time_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(public_number=""),
                name="booking_req_public_number_not_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1),
                name="booking_req_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=BookingRequestStatus.NEW,
                        processed_by__isnull=True,
                        processed_at__isnull=True,
                        processed_by_display_name="",
                    )
                    | (
                        models.Q(
                            status=BookingRequestStatus.PROCESSED,
                            processed_by__isnull=False,
                            processed_at__isnull=False,
                        )
                        & ~models.Q(processed_by_display_name="")
                    )
                ),
                name="booking_req_processing_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_number} · {self.client_name or 'Без імені'}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        adding = self._state.adding
        self.normalize_contact_fields()
        if not adding:
            original = getattr(self, "_immutable_values", None)
            if original is None:
                original = (
                    type(self)
                    .objects.only(*self._current_immutable_values().keys())
                    .get(pk=self.pk)
                    ._current_immutable_values()
                )
            if original != self._current_immutable_values():
                raise BookingRequestImmutableError("Booking request contact data is immutable.")
            terminal = getattr(self, "_terminal_values", None)
            if terminal is None:
                terminal = (
                    type(self)
                    .objects.only(
                        "status",
                        "processed_by",
                        "processed_by_display_name",
                        "processed_at",
                    )
                    .get(pk=self.pk)
                    ._current_terminal_values()
                )
            if (
                terminal["status"] == BookingRequestStatus.PROCESSED
                and terminal != self._current_terminal_values()
            ):
                raise BookingRequestImmutableError("Processed booking request state is terminal.")
        super().save(*args, **kwargs)
        self._immutable_values = self._current_immutable_values()
        self._terminal_values = self._current_terminal_values()

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[Any],
    ) -> "BookingRequest":
        instance = super().from_db(db, field_names, values)
        loaded_values = dict(zip(field_names, values, strict=True))
        if IMMUTABLE_BOOKING_REQUEST_FIELDS <= loaded_values.keys():
            instance._immutable_values = {
                field: loaded_values[field] for field in IMMUTABLE_BOOKING_REQUEST_FIELDS
            }
        if TERMINAL_BOOKING_REQUEST_FIELDS <= loaded_values.keys():
            instance._terminal_values = {
                field: loaded_values[field] for field in TERMINAL_BOOKING_REQUEST_FIELDS
            }
        return instance

    def _current_immutable_values(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in IMMUTABLE_BOOKING_REQUEST_FIELDS}

    def _current_terminal_values(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "processed_by_id": self.processed_by_id,
            "processed_by_display_name": self.processed_by_display_name,
            "processed_at": self.processed_at,
        }

    def normalize_contact_fields(self) -> None:
        self.client_name = self.client_name.strip()
        self.phone = self.phone.strip()
        self.phone_normalized = normalize_phone(self.phone) if self.phone else ""
        self.service = self.service.strip()
        self.contact_handle = self.contact_handle.strip()
        self.message = self.message.strip()
        self.external_reference = self.external_reference.strip()


class BookingRequestApiCredential(models.Model):
    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=SINGLETON_ID,
        editable=False,
    )
    token_digest = models.CharField(max_length=64, blank=True, editable=False)
    token_hint = models.CharField(max_length=6, blank=True, editable=False)
    rotated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="rotated_booking_request_api_credentials",
    )
    rotated_by_display_name = models.CharField(max_length=255, blank=True, editable=False)
    rotated_at = models.DateTimeField(blank=True, null=True, editable=False)
    version = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Booking request API credential"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="booking_req_api_credential_singleton",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        token_digest="",
                        token_hint="",
                        rotated_by__isnull=True,
                        rotated_by_display_name="",
                        rotated_at__isnull=True,
                        version=0,
                    )
                    | (
                        ~models.Q(token_digest="")
                        & ~models.Q(token_hint="")
                        & models.Q(rotated_by__isnull=False)
                        & ~models.Q(rotated_by_display_name="")
                        & models.Q(rotated_at__isnull=False)
                        & models.Q(version__gte=1)
                    )
                ),
                name="booking_req_api_credential_consistent",
            ),
        ]

    def __str__(self) -> str:
        return "Booking request API"

    @property
    def is_configured(self) -> bool:
        return bool(self.token_digest)


class BookingRequestSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    credential = models.ForeignKey(
        BookingRequestApiCredential,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    idempotency_key = models.CharField(max_length=128)
    payload_hash = models.CharField(max_length=64, editable=False)
    booking_request = models.OneToOneField(
        BookingRequest,
        on_delete=models.PROTECT,
        related_name="submission",
    )
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("credential", "idempotency_key"),
                name="booking_req_submission_idempotency_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(idempotency_key=""),
                name="booking_req_submission_key_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(payload_hash=""),
                name="booking_req_submission_hash_not_empty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.booking_request.public_number} · {self.idempotency_key}"
