import uuid
from collections.abc import Collection, Iterable
from typing import Any

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models.functions import Upper


class ImmutableReceivableError(RuntimeError):
    pass


class ImmutableCashShiftError(RuntimeError):
    pass


class ImmutableCashLedgerEntryError(RuntimeError):
    pass


class ImmutablePaymentError(RuntimeError):
    pass


class ImmutableRefundError(RuntimeError):
    pass


class ImmutableCashAdjustmentError(RuntimeError):
    pass


def cash_shift_public_number(shift_id: uuid.UUID) -> str:
    return f"CSH-{shift_id.hex[:12].upper()}"


def cash_ledger_entry_public_number(entry_id: uuid.UUID) -> str:
    return f"TXN-{entry_id.hex[:12].upper()}"


class ReceivableStatus(models.TextChoices):
    OPEN = "OPEN", "Очікує оплати"
    PAID = "PAID", "Оплачено"
    REFUNDED = "REFUNDED", "Повернено"


class CashShiftStatus(models.TextChoices):
    OPEN = "OPEN", "Відкрита"
    CLOSED = "CLOSED", "Закрита"


class CashShiftOpeningBasis(models.TextChoices):
    LEGACY = "LEGACY", "Історична"
    INITIAL = "INITIAL", "Перша зміна"
    CARRY_FORWARD = "CARRY_FORWARD", "Перенесення залишку"


class CashLedgerEntryKind(models.TextChoices):
    PAYMENT = "PAYMENT", "Оплата"
    REFUND = "REFUND", "Повернення"
    DEPOSIT = "DEPOSIT", "Внесення"
    WITHDRAWAL = "WITHDRAWAL", "Вилучення"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Готівка"
    CARD = "CARD", "Картка"
    TRANSFER = "TRANSFER", "Переказ"


class CashShiftQuerySet(models.QuerySet["CashShift"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutableCashShiftError("Cash shifts must transition through the aggregate service.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableCashShiftError("Cash shifts cannot be deleted.")

    def bulk_update(
        self,
        objs: Iterable["CashShift"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise ImmutableCashShiftError("Cash shifts must transition through the aggregate service.")


class ReceivableQuerySet(models.QuerySet["Receivable"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutableReceivableError(
            "Receivables must transition through the billing aggregate service."
        )

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableReceivableError("Receivables cannot be deleted.")

    def bulk_update(
        self,
        objs: Iterable["Receivable"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise ImmutableReceivableError(
            "Receivables must transition through the billing aggregate service."
        )


class Receivable(models.Model):
    """Full visit obligation with a forward-only settlement lifecycle."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.OneToOneField(
        "visits.Visit",
        on_delete=models.PROTECT,
        related_name="receivable",
    )
    amount_minor = models.PositiveBigIntegerField(editable=False)
    status = models.CharField(
        max_length=16,
        choices=ReceivableStatus.choices,
        default=ReceivableStatus.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReceivableQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(amount_minor=0, status=ReceivableStatus.PAID)
                    | models.Q(
                        amount_minor__gt=0,
                        status__in=ReceivableStatus.values,
                    )
                ),
                name="billing_receivable_amount_status_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · {self.amount_minor} · {self.status}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding:
            valid_initial_state = (
                self.amount_minor == 0 and self.status == ReceivableStatus.PAID
            ) or (self.amount_minor > 0 and self.status == ReceivableStatus.OPEN)
            if not valid_initial_state:
                raise ImmutableReceivableError(
                    "Positive receivables start open; zero-total receivables start paid."
                )
        else:
            loaded = (
                type(self)
                .objects.only("visit_id", "amount_minor", "status", "created_at")
                .get(pk=self.pk)
            )
            if loaded.visit_id != self.visit_id or loaded.created_at != self.created_at:
                raise ImmutableReceivableError("Receivable identity is immutable.")
            amount_changed = loaded.amount_minor != self.amount_minor
            if amount_changed:
                can_reprice = (
                    loaded.status == ReceivableStatus.OPEN
                    and self.status == ReceivableStatus.OPEN
                    and self.amount_minor > 0
                    and not self.payment_records.exists()
                )
                if not can_reprice:
                    raise ImmutableReceivableError(
                        "Only an unpaid open receivable can be repriced."
                    )
                super().save(*args, **kwargs)
                return
            allowed_transition = (
                loaded.status == ReceivableStatus.OPEN and self.status == ReceivableStatus.PAID
            ) or (
                loaded.status == ReceivableStatus.PAID
                and self.status == ReceivableStatus.REFUNDED
                and self.payment_records.filter(refund_record__isnull=False).exists()
            )
            if not allowed_transition:
                raise ImmutableReceivableError(
                    "Receivables only transition OPEN to PAID to REFUNDED."
                )
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableReceivableError("Receivables cannot be deleted.")

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[Any],
    ) -> "Receivable":
        return super().from_db(db, field_names, values)


class PricingState(models.TextChoices):
    OPEN = "OPEN", "Очікує розрахунку"
    SETTLED = "SETTLED", "Зафіксовано"


class DiscountSource(models.TextChoices):
    LOYALTY = "LOYALTY", "Програма лояльності"
    PODOLOGIST = "PODOLOGIST", "Подолог"
    RECEPTION = "RECEPTION", "Рецепція"


class VisitPricingQuerySet(models.QuerySet["VisitPricing"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutablePaymentError("Visit pricing must change through the billing service.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutablePaymentError("Visit pricing cannot be deleted.")


class VisitPricing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit = models.OneToOneField(
        "visits.Visit",
        on_delete=models.PROTECT,
        related_name="pricing",
    )
    gross_minor = models.PositiveBigIntegerField(editable=False)
    discount = models.ForeignKey(
        "discounts.Discount",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="visit_pricings",
    )
    discount_name_snapshot = models.CharField(max_length=120, blank=True, editable=False)
    discount_percent_snapshot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    discount_source = models.CharField(
        max_length=16,
        choices=DiscountSource.choices,
        blank=True,
        editable=False,
    )
    applied_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="applied_visit_discounts",
        editable=False,
    )
    discount_amount_minor = models.PositiveBigIntegerField(default=0, editable=False)
    net_minor = models.PositiveBigIntegerField(editable=False)
    is_legacy_backfill = models.BooleanField(default=False, editable=False)
    version = models.PositiveIntegerField(default=1)
    state = models.CharField(max_length=16, choices=PricingState.choices)
    settled_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VisitPricingQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(version__gt=0),
                name="billing_pricing_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount_minor__lte=models.F("gross_minor")),
                name="billing_pricing_discount_lte_gross",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    net_minor=models.F("gross_minor") - models.F("discount_amount_minor")
                ),
                name="billing_pricing_net_formula",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        discount__isnull=True,
                        discount_name_snapshot="",
                        discount_percent_snapshot__isnull=True,
                        discount_source="",
                        discount_amount_minor=0,
                        applied_by__isnull=True,
                    )
                    | models.Q(
                        gross_minor__gt=0,
                        discount__isnull=False,
                        discount_percent_snapshot__gte=1,
                        discount_percent_snapshot__lte=99,
                        discount_source__in=DiscountSource.values,
                    )
                ),
                name="billing_pricing_discount_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(state=PricingState.OPEN, settled_at__isnull=True)
                    | models.Q(state=PricingState.SETTLED, settled_at__isnull=False)
                ),
                name="billing_pricing_state_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.visit.public_number} · {self.net_minor}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            loaded = type(self).objects.get(pk=self.pk)
            if (
                loaded.visit_id != self.visit_id
                or loaded.gross_minor != self.gross_minor
                or loaded.is_legacy_backfill != self.is_legacy_backfill
                or loaded.created_at != self.created_at
            ):
                raise ImmutablePaymentError(
                    "Visit pricing identity, gross and provenance are immutable."
                )
            if loaded.state == PricingState.SETTLED:
                raise ImmutablePaymentError("Settled visit pricing is immutable.")
            if self.state not in (PricingState.OPEN, PricingState.SETTLED):
                raise ImmutablePaymentError("Invalid visit pricing lifecycle transition.")
            if self.version != loaded.version + 1:
                raise ImmutablePaymentError("Visit pricing version must advance exactly once.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutablePaymentError("Visit pricing cannot be deleted.")


class CashDrawer(models.Model):
    """The clinic's one physical cash drawer."""

    MAIN_KEY = "main"

    key = models.CharField(primary_key=True, max_length=32, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(key="main"),
                name="billing_cash_drawer_is_main",
            ),
        ]

    def __str__(self) -> str:
        return self.key

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.key != self.MAIN_KEY:
            raise ImmutableCashShiftError("Only the main clinic cash drawer is supported.")
        if not self._state.adding:
            raise ImmutableCashShiftError("The clinic cash drawer is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableCashShiftError("The clinic cash drawer cannot be deleted.")


class CashShift(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_number = models.CharField(max_length=24, unique=True, editable=False)
    employee = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="cash_shifts",
    )
    employee_name_snapshot = models.CharField(max_length=255, default="", editable=False)
    employee_email_snapshot = models.EmailField(default="", editable=False)
    employee_role_snapshot = models.CharField(max_length=20, default="", editable=False)
    drawer = models.ForeignKey(
        CashDrawer,
        db_column="drawer_key",
        default=CashDrawer.MAIN_KEY,
        on_delete=models.PROTECT,
        related_name="shifts",
        editable=False,
    )
    opening_cash_minor = models.PositiveBigIntegerField(default=0, editable=False)
    opening_source_shift = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="carried_forward_to_shifts",
        editable=False,
    )
    opening_basis = models.CharField(
        max_length=16,
        choices=CashShiftOpeningBasis.choices,
        default=CashShiftOpeningBasis.INITIAL,
        editable=False,
    )
    status = models.CharField(
        max_length=16,
        choices=CashShiftStatus.choices,
        default=CashShiftStatus.OPEN,
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    expected_cash_at_close_minor = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    actual_cash_at_close_minor = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    discrepancy_minor = models.BigIntegerField(null=True, blank=True, editable=False)
    close_comment = models.TextField(blank=True, editable=False)
    closed_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="closed_cash_shifts",
        editable=False,
    )
    closed_by_name_snapshot = models.CharField(max_length=255, blank=True, editable=False)
    closed_by_email_snapshot = models.EmailField(blank=True, editable=False)
    closed_by_role_snapshot = models.CharField(max_length=20, blank=True, editable=False)
    close_idempotency_key = models.CharField(max_length=128, blank=True, editable=False)
    close_payload_hash = models.CharField(max_length=64, blank=True, editable=False)

    objects = CashShiftQuerySet.as_manager()

    class Meta:
        ordering = ("-opened_at", "-id")
        indexes = [
            models.Index(
                fields=("drawer", "status", "-closed_at", "-id"),
                name="billing_drawer_state_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("drawer",),
                condition=models.Q(status=CashShiftStatus.OPEN),
                name="billing_one_open_cash_shift_per_drawer",
            ),
            models.UniqueConstraint(
                fields=("opening_source_shift",),
                condition=models.Q(opening_source_shift__isnull=False),
                name="billing_cash_shift_source_used_once",
            ),
            models.UniqueConstraint(
                fields=("closed_by", "close_idempotency_key"),
                condition=models.Q(status=CashShiftStatus.CLOSED),
                name="billing_shift_close_actor_key_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=CashShiftStatus.OPEN,
                        closed_at__isnull=True,
                        expected_cash_at_close_minor__isnull=True,
                        actual_cash_at_close_minor__isnull=True,
                        discrepancy_minor__isnull=True,
                        close_comment="",
                        closed_by__isnull=True,
                        closed_by_name_snapshot="",
                        closed_by_email_snapshot="",
                        closed_by_role_snapshot="",
                        close_idempotency_key="",
                        close_payload_hash="",
                    )
                    | models.Q(
                        status=CashShiftStatus.CLOSED,
                        closed_at__isnull=False,
                        expected_cash_at_close_minor__isnull=False,
                        actual_cash_at_close_minor__isnull=False,
                        discrepancy_minor__isnull=False,
                        closed_by__isnull=False,
                    )
                    & ~models.Q(closed_by_name_snapshot="")
                    & ~models.Q(closed_by_email_snapshot="")
                    & ~models.Q(closed_by_role_snapshot="")
                    & ~models.Q(close_idempotency_key="")
                    & ~models.Q(close_payload_hash="")
                ),
                name="billing_cash_shift_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(employee_name_snapshot="")
                    & ~models.Q(employee_email_snapshot="")
                    & ~models.Q(employee_role_snapshot="")
                ),
                name="billing_cash_shift_opener_snapshot_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status=CashShiftStatus.OPEN)
                    | models.Q(
                        discrepancy_minor=(
                            models.F("actual_cash_at_close_minor")
                            - models.F("expected_cash_at_close_minor")
                        )
                    )
                ),
                name="billing_cash_shift_discrepancy_formula",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status=CashShiftStatus.OPEN)
                    | models.Q(discrepancy_minor=0)
                    | ~models.Q(close_comment="")
                ),
                name="billing_cash_shift_discrepancy_comment",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        opening_basis=CashShiftOpeningBasis.LEGACY,
                        opening_cash_minor=0,
                        opening_source_shift__isnull=True,
                    )
                    | models.Q(
                        opening_basis=CashShiftOpeningBasis.INITIAL,
                        opening_cash_minor=0,
                        opening_source_shift__isnull=True,
                    )
                    | models.Q(
                        opening_basis=CashShiftOpeningBasis.CARRY_FORWARD,
                        opening_source_shift__isnull=False,
                    )
                ),
                name="billing_cash_shift_opening_mode",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(opening_source_shift__isnull=True)
                    | ~models.Q(opening_source_shift=models.F("id"))
                ),
                name="billing_cash_shift_source_not_self",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_number} · {self.employee.display_name} · {self.status}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            loaded = type(self).objects.get(pk=self.pk)
            immutable_fields = (
                "public_number",
                "employee_id",
                "employee_name_snapshot",
                "employee_email_snapshot",
                "employee_role_snapshot",
                "drawer_id",
                "opening_cash_minor",
                "opening_source_shift_id",
                "opening_basis",
                "opened_at",
            )
            if any(getattr(loaded, field) != getattr(self, field) for field in immutable_fields):
                raise ImmutableCashShiftError("Cash shift identity and opening are immutable.")
            if loaded.status == CashShiftStatus.CLOSED:
                raise ImmutableCashShiftError("Closed cash shifts are immutable.")
            if self.status != CashShiftStatus.CLOSED:
                raise ImmutableCashShiftError("An open cash shift can only transition to closed.")
        else:
            CashDrawer.objects.get_or_create(key=CashDrawer.MAIN_KEY)
            if not self.employee_name_snapshot:
                self.employee_name_snapshot = self.employee.display_name
            if not self.employee_email_snapshot:
                self.employee_email_snapshot = self.employee.email
            if not self.employee_role_snapshot:
                self.employee_role_snapshot = self.employee.role
        if not self.public_number:
            self.public_number = cash_shift_public_number(self.id)
        self.close_comment = self.close_comment.strip()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableCashShiftError("Cash shifts cannot be deleted.")


class CashLedgerEntryQuerySet(models.QuerySet["CashLedgerEntry"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutableCashLedgerEntryError("Cash ledger entries are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableCashLedgerEntryError("Cash ledger entries are append-only.")

    def bulk_update(
        self,
        objs: Iterable["CashLedgerEntry"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise ImmutableCashLedgerEntryError("Cash ledger entries are append-only.")


class CashLedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_number = models.CharField(max_length=24, unique=True, editable=False)
    cash_shift = models.ForeignKey(
        CashShift,
        on_delete=models.PROTECT,
        related_name="entries",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="cash_ledger_entries",
    )
    actor_name_snapshot = models.CharField(max_length=255, default="", editable=False)
    actor_email_snapshot = models.EmailField(default="", editable=False)
    actor_role_snapshot = models.CharField(max_length=20, default="", editable=False)
    kind = models.CharField(max_length=16, choices=CashLedgerEntryKind.choices)
    amount_minor = models.PositiveBigIntegerField(editable=False)
    payment_method = models.CharField(
        max_length=16,
        choices=PaymentMethod.choices,
        blank=True,
        editable=False,
    )
    idempotency_key = models.CharField(max_length=128, editable=False)
    payload_hash = models.CharField(max_length=64, editable=False)
    posted_at = models.DateTimeField(auto_now_add=True)

    objects = CashLedgerEntryQuerySet.as_manager()

    class Meta:
        ordering = ("-posted_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("created_by", "kind", "idempotency_key"),
                name="billing_ledger_actor_kind_idempotency_unique",
            ),
            models.UniqueConstraint(
                fields=("created_by", "idempotency_key"),
                condition=models.Q(
                    kind__in=(
                        CashLedgerEntryKind.DEPOSIT,
                        CashLedgerEntryKind.WITHDRAWAL,
                    )
                ),
                name="billing_cash_movement_actor_idempotency_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_minor__gt=0),
                name="billing_ledger_amount_positive",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(actor_name_snapshot="")
                    & ~models.Q(actor_email_snapshot="")
                    & ~models.Q(actor_role_snapshot="")
                ),
                name="billing_ledger_actor_snapshot_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind__in=(
                            CashLedgerEntryKind.PAYMENT,
                            CashLedgerEntryKind.REFUND,
                        ),
                        payment_method__isnull=False,
                        payment_method__in=PaymentMethod.values,
                    )
                    | models.Q(
                        kind__in=(
                            CashLedgerEntryKind.DEPOSIT,
                            CashLedgerEntryKind.WITHDRAWAL,
                        ),
                        payment_method="",
                    )
                ),
                name="billing_ledger_kind_method_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=("cash_shift", "-posted_at", "-id"),
                name="billing_ledger_shift_time_idx",
            ),
            GinIndex(
                OpClass(Upper("public_number"), name="gin_trgm_ops"),
                name="billing_ledger_search_gin",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.public_number} · {self.kind} · {self.amount_minor}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableCashLedgerEntryError("Cash ledger entries are append-only.")
        if not self.actor_name_snapshot:
            self.actor_name_snapshot = self.created_by.display_name
        if not self.actor_email_snapshot:
            self.actor_email_snapshot = self.created_by.email
        if not self.actor_role_snapshot:
            self.actor_role_snapshot = self.created_by.role
        self.payment_method = self.payment_method or ""
        if not self.public_number:
            self.public_number = cash_ledger_entry_public_number(self.id)
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableCashLedgerEntryError("Cash ledger entries are append-only.")


class PaymentQuerySet(models.QuerySet["Payment"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutablePaymentError("Payments are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutablePaymentError("Payments are append-only.")

    def bulk_update(
        self,
        objs: Iterable["Payment"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise ImmutablePaymentError("Payments are append-only.")


class Payment(models.Model):
    """Immutable typed extension for one full receivable payment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ledger_entry = models.ForeignKey(
        CashLedgerEntry,
        on_delete=models.PROTECT,
        related_name="payment_records",
        editable=False,
    )
    receivable = models.ForeignKey(
        Receivable,
        on_delete=models.PROTECT,
        related_name="payment_records",
        editable=False,
    )
    comment = models.TextField(blank=True, editable=False)
    patient_id_snapshot = models.UUIDField(editable=False)
    patient_public_number_snapshot = models.CharField(max_length=24, editable=False)
    patient_name_snapshot = models.CharField(max_length=255, editable=False)
    patient_phone_snapshot = models.CharField(max_length=32, editable=False)
    visit_public_number_snapshot = models.CharField(max_length=24, editable=False)
    visit_completed_at_snapshot = models.DateTimeField(editable=False)
    visit_payment_handoff_requested_snapshot = models.BooleanField(editable=False)
    visit_total_minor_snapshot = models.PositiveBigIntegerField(editable=False)
    gross_total_minor_snapshot = models.PositiveBigIntegerField(editable=False)
    discount_id_snapshot = models.UUIDField(null=True, blank=True, editable=False)
    discount_name_snapshot = models.CharField(max_length=120, blank=True, editable=False)
    discount_percent_snapshot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    discount_source_snapshot = models.CharField(
        max_length=16,
        choices=DiscountSource.choices,
        blank=True,
        editable=False,
    )
    discount_amount_minor_snapshot = models.PositiveBigIntegerField(editable=False)
    net_total_minor_snapshot = models.PositiveBigIntegerField(editable=False)
    pricing_snapshot_is_legacy = models.BooleanField(default=False, editable=False)
    specialist_id_snapshot = models.PositiveBigIntegerField(editable=False)
    specialist_name_snapshot = models.CharField(max_length=255, editable=False)
    employee_name_snapshot = models.CharField(max_length=255, editable=False)
    employee_email_snapshot = models.EmailField(editable=False)
    services_snapshot = models.JSONField(default=list, editable=False)
    services_search_snapshot = models.TextField(editable=False)

    objects = PaymentQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        indexes = [
            GinIndex(
                OpClass(Upper("patient_public_number_snapshot"), name="gin_trgm_ops"),
                OpClass(Upper("patient_name_snapshot"), name="gin_trgm_ops"),
                OpClass(Upper("visit_public_number_snapshot"), name="gin_trgm_ops"),
                OpClass(Upper("services_search_snapshot"), name="gin_trgm_ops"),
                name="billing_payment_search_gin",
            ),
            GinIndex(
                OpClass(
                    models.Func(
                        "patient_phone_snapshot",
                        models.Value("[^0-9]"),
                        models.Value(""),
                        models.Value("g"),
                        function="REGEXP_REPLACE",
                        output_field=models.CharField(),
                    ),
                    name="gin_trgm_ops",
                ),
                name="billing_phone_digits_gin",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("ledger_entry",),
                name="billing_payment_ledger_unique",
            ),
            models.UniqueConstraint(
                fields=("receivable",),
                name="billing_payment_receivable_unique",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(patient_public_number_snapshot="")
                    & ~models.Q(patient_name_snapshot="")
                    & ~models.Q(visit_public_number_snapshot="")
                    & ~models.Q(specialist_name_snapshot="")
                    & ~models.Q(employee_name_snapshot="")
                    & ~models.Q(employee_email_snapshot="")
                    & ~models.Q(services_search_snapshot="")
                ),
                name="billing_payment_snapshot_identity_nonempty",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    net_total_minor_snapshot=(
                        models.F("gross_total_minor_snapshot")
                        - models.F("discount_amount_minor_snapshot")
                    ),
                    visit_total_minor_snapshot=models.F("net_total_minor_snapshot"),
                    net_total_minor_snapshot__gt=0,
                ),
                name="billing_payment_pricing_formula",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        discount_id_snapshot__isnull=True,
                        discount_name_snapshot="",
                        discount_percent_snapshot__isnull=True,
                        discount_source_snapshot="",
                        discount_amount_minor_snapshot=0,
                    )
                    | models.Q(
                        discount_id_snapshot__isnull=False,
                        discount_percent_snapshot__gte=1,
                        discount_percent_snapshot__lte=99,
                        discount_source_snapshot__in=DiscountSource.values,
                    )
                    & ~models.Q(discount_name_snapshot="")
                ),
                name="billing_payment_discount_snapshot_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ledger_entry.public_number} · {self.receivable.visit.public_number}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutablePaymentError("Payments are append-only.")
        self.comment = self.comment.strip()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutablePaymentError("Payments are append-only.")


class RefundQuerySet(models.QuerySet["Refund"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutableRefundError("Refunds are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableRefundError("Refunds are append-only.")

    def bulk_update(
        self,
        objs: Iterable["Refund"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise ImmutableRefundError("Refunds are append-only.")


class Refund(models.Model):
    """Immutable typed extension for one complete payment reversal."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ledger_entry = models.ForeignKey(
        CashLedgerEntry,
        on_delete=models.PROTECT,
        related_name="refund_records",
        editable=False,
    )
    original_payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name="refund_record",
        editable=False,
    )
    reason = models.CharField(max_length=500, editable=False)
    employee_name_snapshot = models.CharField(max_length=255, editable=False)
    employee_email_snapshot = models.EmailField(editable=False)

    objects = RefundQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("ledger_entry",),
                name="billing_refund_ledger_unique",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(reason="")
                    & ~models.Q(employee_name_snapshot="")
                    & ~models.Q(employee_email_snapshot="")
                ),
                name="billing_refund_identity_nonempty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ledger_entry.public_number} · {self.original_payment_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableRefundError("Refunds are append-only.")
        self.reason = self.reason.strip()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableRefundError("Refunds are append-only.")


class CashAdjustmentQuerySet(models.QuerySet["CashAdjustment"]):
    def update(self, **kwargs: Any) -> int:
        raise ImmutableCashAdjustmentError("Cash adjustments are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ImmutableCashAdjustmentError("Cash adjustments are append-only.")

    def bulk_update(
        self,
        objs: Iterable["CashAdjustment"],
        fields: Iterable[str],
        batch_size: int | None = None,
    ) -> int:
        raise ImmutableCashAdjustmentError("Cash adjustments are append-only.")


class CashAdjustment(models.Model):
    """Immutable typed extension for a cash deposit or withdrawal."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ledger_entry = models.ForeignKey(
        CashLedgerEntry,
        on_delete=models.PROTECT,
        related_name="cash_adjustment_records",
        editable=False,
    )
    reason = models.CharField(max_length=500, editable=False)
    comment = models.TextField(blank=True, editable=False)
    employee_name_snapshot = models.CharField(max_length=255, editable=False)
    employee_email_snapshot = models.EmailField(editable=False)

    objects = CashAdjustmentQuerySet.as_manager()

    class Meta:
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(
                fields=("ledger_entry",),
                name="billing_cash_adjustment_ledger_unique",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(reason="")
                    & ~models.Q(employee_name_snapshot="")
                    & ~models.Q(employee_email_snapshot="")
                ),
                name="billing_cash_adjustment_identity_nonempty",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ledger_entry.public_number} · {self.reason}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ImmutableCashAdjustmentError("Cash adjustments are append-only.")
        self.reason = self.reason.strip()
        self.comment = self.comment.strip()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ImmutableCashAdjustmentError("Cash adjustments are append-only.")
