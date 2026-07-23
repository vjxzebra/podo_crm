import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import (
    BigIntegerField,
    Case,
    CharField,
    Count,
    DateTimeField,
    F,
    Prefetch,
    Q,
    QuerySet,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone
from rest_framework import status

from apps.accounts.access import AccessScope, has_scope
from apps.accounts.models import User, UserRole
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event
from apps.billing.models import (
    CashAdjustment,
    CashLedgerEntry,
    CashLedgerEntryKind,
    CashShift,
    CashShiftStatus,
    Payment,
    PaymentMethod,
    Receivable,
    ReceivableStatus,
    Refund,
)
from apps.visits.models import VisitStatus
from config.api.exceptions import ApiProblem


def _cash_shift_access_required() -> ApiProblem:
    return ApiProblem(
        code="permission_denied",
        message="Недостатньо прав для роботи з касовою зміною.",
        status_code=status.HTTP_403_FORBIDDEN,
    )


def _cash_shift_already_open() -> ApiProblem:
    return ApiProblem(
        code="cash_shift_already_open",
        message="У вас уже є відкрита касова зміна.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _cash_shift_required() -> ApiProblem:
    return ApiProblem(
        code="cash_shift_required",
        message="Перед проведенням фінансової операції відкрийте власну касову зміну.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _receivable_already_paid() -> ApiProblem:
    return ApiProblem(
        code="receivable_already_paid",
        message="Цей прийом уже оплачено.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _visit_not_payable() -> ApiProblem:
    return ApiProblem(
        code="visit_not_payable",
        message="Фінансове зобов’язання не можна оплатити в поточному стані.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _receivable_already_refunded() -> ApiProblem:
    return ApiProblem(
        code="receivable_already_refunded",
        message="Оплату за цей прийом уже повністю повернено.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _payment_already_refunded() -> ApiProblem:
    return ApiProblem(
        code="payment_already_refunded",
        message="Цю оплату вже повністю повернено.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _payment_not_refundable() -> ApiProblem:
    return ApiProblem(
        code="payment_not_refundable",
        message="Оплату не можна повернути в поточному стані.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _insufficient_cash() -> ApiProblem:
    return ApiProblem(
        code="insufficient_cash",
        message="У поточній касовій зміні недостатньо готівки.",
        status_code=status.HTTP_409_CONFLICT,
        fields={"amount_minor": ["Сума перевищує доступну фізичну готівку."]},
    )


def _cash_shift_not_found() -> ApiProblem:
    return ApiProblem(
        code="not_found",
        message="Касову зміну не знайдено.",
        status_code=status.HTTP_404_NOT_FOUND,
    )


def _cash_shift_changed() -> ApiProblem:
    return ApiProblem(
        code="cash_shift_changed",
        message="Операції касової зміни змінилися. Оновіть звірку та підтвердьте її знову.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _cash_shift_already_closed() -> ApiProblem:
    return ApiProblem(
        code="cash_shift_already_closed",
        message="Касову зміну вже закрито.",
        status_code=status.HTTP_409_CONFLICT,
    )


def _close_idempotency_payload_mismatch() -> ApiProblem:
    return ApiProblem(
        code="idempotency_payload_mismatch",
        message="Цей ключ повтору вже використано для іншого закриття касової зміни.",
        status_code=status.HTTP_409_CONFLICT,
        fields={"idempotency_key": ["Створіть новий ключ для зміненого запиту."]},
    )


def _close_idempotency_key_conflict() -> ApiProblem:
    return ApiProblem(
        code="idempotency_key_conflict",
        message="Збережений результат для цього ключа закриття неконсистентний.",
        status_code=status.HTTP_409_CONFLICT,
        fields={"idempotency_key": ["Створіть новий ключ і перевірте історію зміни."]},
    )


def _validate_actor(actor: User) -> None:
    if not has_scope(actor, AccessScope.CASH_SHIFT):
        raise _cash_shift_access_required()


def _validate_finance_actor(actor: User) -> None:
    if not has_scope(actor, AccessScope.FINANCE):
        raise ApiProblem(
            code="permission_denied",
            message="Недостатньо прав для роботи з фінансовими операціями.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _cash_shift_queryset() -> QuerySet[CashShift]:
    return CashShift.objects.select_related("employee", "closed_by").prefetch_related(
        Prefetch(
            "entries",
            queryset=CashLedgerEntry.objects.select_related("created_by").order_by(
                "-posted_at", "-id"
            ),
        )
    )


def _constraint_name(exc: IntegrityError) -> str:
    cause = getattr(exc, "__cause__", None)
    return str(getattr(getattr(cause, "diag", None), "constraint_name", ""))


def _payload_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _payment_with_context() -> QuerySet[Payment]:
    return Payment.objects.select_related(
        "ledger_entry__cash_shift",
        "ledger_entry__created_by",
        "receivable__visit__patient",
        "receivable__visit__specialist",
        "refund_record__ledger_entry__cash_shift",
        "refund_record__ledger_entry__created_by",
    )


def _existing_payment(
    *,
    actor: User,
    idempotency_key: str,
    payload_hash: str,
) -> Payment | None:
    entry = (
        CashLedgerEntry.objects.filter(
            created_by=actor,
            kind=CashLedgerEntryKind.PAYMENT,
            idempotency_key=idempotency_key,
        )
        .only("id", "payload_hash")
        .first()
    )
    if entry is None:
        return None
    if entry.payload_hash != payload_hash:
        raise ApiProblem(
            code="idempotency_payload_mismatch",
            message="Цей ключ повтору вже використано для іншої оплати.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"idempotency_key": ["Створіть новий ключ для зміненого запиту."]},
        )
    payment = _payment_with_context().filter(ledger_entry_id=entry.pk).first()
    if payment is None:
        raise ApiProblem(
            code="idempotency_key_conflict",
            message="Цей ключ уже зайнятий іншою фінансовою операцією.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"idempotency_key": ["Створіть новий ключ для цієї оплати."]},
        )
    return payment


def _refund_with_context() -> QuerySet[Refund]:
    return Refund.objects.select_related(
        "ledger_entry__cash_shift",
        "ledger_entry__created_by",
        "original_payment__ledger_entry__cash_shift",
        "original_payment__ledger_entry__created_by",
        "original_payment__receivable__visit",
    )


def _existing_refund(
    *,
    actor: User,
    idempotency_key: str,
    payload_hash: str,
) -> Refund | None:
    entry = (
        CashLedgerEntry.objects.filter(
            created_by=actor,
            kind=CashLedgerEntryKind.REFUND,
            idempotency_key=idempotency_key,
        )
        .only("id", "payload_hash")
        .first()
    )
    if entry is None:
        return None
    if entry.payload_hash != payload_hash:
        raise ApiProblem(
            code="idempotency_payload_mismatch",
            message="Цей ключ повтору вже використано для іншого повернення.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"idempotency_key": ["Створіть новий ключ для зміненого запиту."]},
        )
    refund = _refund_with_context().filter(ledger_entry_id=entry.pk).first()
    if refund is None:
        raise ApiProblem(
            code="idempotency_key_conflict",
            message="Цей ключ уже зайнятий іншою фінансовою операцією.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"idempotency_key": ["Створіть новий ключ для повернення."]},
        )
    return refund


def _cash_adjustment_with_context() -> QuerySet[CashAdjustment]:
    return CashAdjustment.objects.select_related(
        "ledger_entry__cash_shift",
        "ledger_entry__created_by",
    )


def _existing_cash_adjustment(
    *,
    actor: User,
    idempotency_key: str,
    payload_hash: str,
) -> CashAdjustment | None:
    entry = (
        CashLedgerEntry.objects.filter(
            created_by=actor,
            kind__in=(CashLedgerEntryKind.DEPOSIT, CashLedgerEntryKind.WITHDRAWAL),
            idempotency_key=idempotency_key,
        )
        .only("id", "payload_hash")
        .first()
    )
    if entry is None:
        return None
    if entry.payload_hash != payload_hash:
        raise ApiProblem(
            code="idempotency_payload_mismatch",
            message="Цей ключ повтору вже використано для іншого касового руху.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"idempotency_key": ["Створіть новий ключ для зміненого запиту."]},
        )
    adjustment = _cash_adjustment_with_context().filter(ledger_entry_id=entry.pk).first()
    if adjustment is None:
        raise ApiProblem(
            code="idempotency_key_conflict",
            message="Цей ключ уже зайнятий іншою фінансовою операцією.",
            status_code=status.HTTP_409_CONFLICT,
            fields={"idempotency_key": ["Створіть новий ключ для касового руху."]},
        )
    return adjustment


def cash_shift_audit_snapshot(shift: CashShift) -> dict[str, Any]:
    snapshot = {
        "id": shift.pk,
        "public_number": shift.public_number,
        "employee_id": shift.employee_id,
        "employee_name": shift.employee_name_snapshot,
        "employee_email": shift.employee_email_snapshot,
        "employee_role": shift.employee_role_snapshot,
        "status": shift.status,
        "opened_at": shift.opened_at,
    }
    if shift.status == CashShiftStatus.CLOSED:
        snapshot.update(
            {
                "closed_at": shift.closed_at,
                "expected_cash_minor": shift.expected_cash_at_close_minor,
                "actual_cash_minor": shift.actual_cash_at_close_minor,
                "discrepancy_minor": shift.discrepancy_minor,
                "comment": shift.close_comment,
                "closed_by_id": shift.closed_by_id,
                "closed_by_name": shift.closed_by_name_snapshot,
                "closed_by_email": shift.closed_by_email_snapshot,
                "closed_by_role": shift.closed_by_role_snapshot,
            }
        )
    return snapshot


def cash_ledger_entry_read_model(entry: CashLedgerEntry) -> dict[str, Any]:
    return {
        "id": entry.pk,
        "public_number": entry.public_number,
        "kind": entry.kind,
        "amount_minor": entry.amount_minor,
        "payment_method": entry.payment_method or None,
        "actor_id": entry.created_by_id,
        "actor_name": entry.actor_name_snapshot,
        "actor_email": entry.actor_email_snapshot,
        "posted_at": entry.posted_at,
    }


def _cash_shift_totals(entries: list[CashLedgerEntry]) -> dict[str, int]:
    totals = {
        "operations_count": len(entries),
        "payment_count": 0,
        "refund_count": 0,
        "payments_total_minor": 0,
        "refunds_total_minor": 0,
        "cash_payments_minor": 0,
        "cash_refunds_minor": 0,
        "card_payments_minor": 0,
        "card_refunds_minor": 0,
        "transfer_payments_minor": 0,
        "transfer_refunds_minor": 0,
        "deposits_minor": 0,
        "withdrawals_minor": 0,
        "revenue_minor": 0,
        "expected_cash_minor": 0,
    }
    for entry in entries:
        if entry.kind == CashLedgerEntryKind.PAYMENT:
            totals["payment_count"] += 1
            totals["payments_total_minor"] += entry.amount_minor
            if entry.payment_method == PaymentMethod.CASH:
                totals["cash_payments_minor"] += entry.amount_minor
            elif entry.payment_method == PaymentMethod.CARD:
                totals["card_payments_minor"] += entry.amount_minor
            elif entry.payment_method == PaymentMethod.TRANSFER:
                totals["transfer_payments_minor"] += entry.amount_minor
        elif entry.kind == CashLedgerEntryKind.REFUND:
            totals["refund_count"] += 1
            totals["refunds_total_minor"] += entry.amount_minor
            if entry.payment_method == PaymentMethod.CASH:
                totals["cash_refunds_minor"] += entry.amount_minor
            elif entry.payment_method == PaymentMethod.CARD:
                totals["card_refunds_minor"] += entry.amount_minor
            elif entry.payment_method == PaymentMethod.TRANSFER:
                totals["transfer_refunds_minor"] += entry.amount_minor
        elif entry.kind == CashLedgerEntryKind.DEPOSIT:
            totals["deposits_minor"] += entry.amount_minor
        elif entry.kind == CashLedgerEntryKind.WITHDRAWAL:
            totals["withdrawals_minor"] += entry.amount_minor

    totals["revenue_minor"] = totals["payments_total_minor"] - totals["refunds_total_minor"]
    totals["expected_cash_minor"] = (
        totals["cash_payments_minor"]
        - totals["cash_refunds_minor"]
        + totals["deposits_minor"]
        - totals["withdrawals_minor"]
    )
    return totals


def _cash_shift_reconciliation(shift: CashShift) -> dict[str, Any] | None:
    if shift.status != CashShiftStatus.CLOSED:
        return None
    return {
        "expected_cash_minor": shift.expected_cash_at_close_minor,
        "actual_cash_minor": shift.actual_cash_at_close_minor,
        "discrepancy_minor": shift.discrepancy_minor,
        "comment": shift.close_comment,
        "closed_by": {
            "id": shift.closed_by_id,
            "name": shift.closed_by_name_snapshot,
            "email": shift.closed_by_email_snapshot,
            "role": shift.closed_by_role_snapshot,
        },
    }


def cash_shift_summary(
    shift: CashShift,
    *,
    entries: list[CashLedgerEntry] | None = None,
) -> dict[str, Any]:
    resolved_entries = list(shift.entries.all()) if entries is None else entries
    return {
        "id": shift.pk,
        "public_number": shift.public_number,
        "status": shift.status,
        "employee": {
            "id": shift.employee_id,
            "name": shift.employee_name_snapshot,
            "email": shift.employee_email_snapshot,
            "role": shift.employee_role_snapshot,
        },
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "totals": _cash_shift_totals(resolved_entries),
        "reconciliation": _cash_shift_reconciliation(shift),
    }


def cash_shift_projection(shift: CashShift) -> dict[str, Any]:
    entries = list(shift.entries.all())
    return {
        **cash_shift_summary(shift, entries=entries),
        "entries": [cash_ledger_entry_read_model(entry) for entry in entries],
    }


def available_cash_minor(shift: CashShift) -> int:
    aggregate = CashLedgerEntry.objects.filter(cash_shift=shift).aggregate(
        value=Sum(
            Case(
                When(
                    kind=CashLedgerEntryKind.PAYMENT,
                    payment_method=PaymentMethod.CASH,
                    then="amount_minor",
                ),
                When(kind=CashLedgerEntryKind.DEPOSIT, then="amount_minor"),
                When(
                    kind=CashLedgerEntryKind.REFUND,
                    payment_method=PaymentMethod.CASH,
                    then=-1 * F("amount_minor"),
                ),
                When(
                    kind=CashLedgerEntryKind.WITHDRAWAL,
                    then=-1 * F("amount_minor"),
                ),
                default=0,
                output_field=BigIntegerField(),
            ),
            default=0,
        )
    )
    return int(aggregate["value"] or 0)


def current_cash_shift(*, actor: User) -> CashShift | None:
    _validate_actor(actor)
    return (
        _cash_shift_queryset()
        .filter(
            employee=actor,
            status=CashShiftStatus.OPEN,
        )
        .first()
    )


@transaction.atomic
def open_cash_shift(*, actor: User, correlation_id: str) -> CashShift:
    _validate_actor(actor)
    locked_actor = User.objects.select_for_update().get(pk=actor.pk)
    _validate_actor(locked_actor)
    if CashShift.objects.filter(
        employee=locked_actor,
        status=CashShiftStatus.OPEN,
    ).exists():
        raise _cash_shift_already_open()

    try:
        with transaction.atomic():
            shift = CashShift.objects.create(employee=locked_actor)
    except IntegrityError as exc:
        if _constraint_name(exc) == "billing_one_open_cash_shift_per_employee":
            raise _cash_shift_already_open() from exc
        raise

    shift = CashShift.objects.select_related("employee").get(pk=shift.pk)
    record_audit_event(
        actor=locked_actor,
        action=AuditAction.CASH_SHIFT_OPENED,
        object_type="cash_shift",
        object_id=shift.pk,
        object_label=shift.public_number,
        correlation_id=correlation_id,
        before={},
        after=cash_shift_audit_snapshot(shift),
        description="Відкрито особисту касову зміну працівника.",
    )
    return shift


def _visible_cash_shifts(actor: User) -> QuerySet[CashShift]:
    return _scope_cash_shift_queryset(_cash_shift_queryset(), actor)


def _scope_cash_shift_queryset(
    queryset: QuerySet[CashShift],
    actor: User,
) -> QuerySet[CashShift]:
    _validate_actor(actor)
    if actor.role != UserRole.ADMIN:
        queryset = queryset.filter(employee=actor)
    return queryset


def cash_shift_detail(*, actor: User, shift_id: UUID) -> CashShift:
    shift = _visible_cash_shifts(actor).filter(pk=shift_id).first()
    if shift is None:
        raise _cash_shift_not_found()
    return shift


def cash_shift_export_snapshot(
    *,
    actor: User,
    shift_id: UUID,
    entry_limit: int,
) -> tuple[CashShift, list[CashLedgerEntry]]:
    _validate_actor(actor)
    queryset = CashShift.objects.select_related("employee", "closed_by")
    if actor.role != UserRole.ADMIN:
        queryset = queryset.filter(employee=actor)
    shift = queryset.filter(pk=shift_id).first()
    if shift is None:
        raise _cash_shift_not_found()
    entries = list(
        CashLedgerEntry.objects.filter(cash_shift=shift)
        .select_related("created_by")
        .order_by("-posted_at", "-id")[: entry_limit + 1]
    )
    return shift, entries


def cash_shift_close_preview(*, actor: User, shift_id: UUID) -> dict[str, Any]:
    shift = cash_shift_detail(actor=actor, shift_id=shift_id)
    if shift.status != CashShiftStatus.OPEN:
        raise _cash_shift_already_closed()
    unpaid = Receivable.objects.filter(
        status=ReceivableStatus.OPEN,
        amount_minor__gt=0,
    ).aggregate(
        count=Count("id"),
        total_minor=Coalesce(Sum("amount_minor"), 0),
    )
    return {
        "shift": cash_shift_projection(shift),
        "unpaid": {
            "count": int(unpaid["count"] or 0),
            "total_minor": int(unpaid["total_minor"] or 0),
        },
    }


@dataclass(frozen=True)
class CashShiftCursor:
    opened_at: datetime
    shift_id: UUID


CASH_SHIFT_CURSOR_SALT = "billing.cash-shift-history.v1"
CASH_SHIFT_PAGE_SIZE = 40


def _decode_cash_shift_cursor(value: str | None) -> CashShiftCursor | None:
    if value is None:
        return None
    try:
        payload = signing.loads(value, salt=CASH_SHIFT_CURSOR_SALT)
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("unsupported cursor")
        opened_at = datetime.fromisoformat(str(payload["opened_at"]))
        if opened_at.tzinfo is None:
            raise ValueError("cursor datetime must be aware")
        shift_id = UUID(str(payload["id"]))
    except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
        raise ApiProblem(
            code="validation_error",
            message="Дані запиту не пройшли перевірку.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"cursor": ["Некоректний або застарілий курсор сторінки."]},
        ) from exc
    return CashShiftCursor(opened_at=opened_at, shift_id=shift_id)


def _encode_cash_shift_cursor(shift: CashShift) -> str:
    return signing.dumps(
        {
            "version": 1,
            "opened_at": shift.opened_at.isoformat(),
            "id": str(shift.pk),
        },
        salt=CASH_SHIFT_CURSOR_SALT,
        compress=True,
    )


def _filter_cash_shift_history_queryset(
    *,
    actor: User,
    filters: dict[str, Any],
    queryset: QuerySet[CashShift],
) -> QuerySet[CashShift]:
    employee_id = filters.get("employee_id")
    if employee_id is not None:
        if actor.role != UserRole.ADMIN:
            raise _cash_shift_access_required()
        queryset = queryset.filter(employee_id=employee_id)

    search = str(filters.get("search", "")).strip()
    if search:
        queryset = queryset.filter(
            Q(public_number__icontains=search)
            | Q(employee_name_snapshot__icontains=search)
            | Q(employee_email_snapshot__icontains=search)
        )
    if filters.get("status") is not None:
        queryset = queryset.filter(status=filters["status"])

    local_timezone = ZoneInfo(settings.TIME_ZONE)
    date_from = filters.get("date_from")
    if date_from is not None:
        start = datetime.combine(date_from, time.min, tzinfo=local_timezone)
        queryset = queryset.filter(opened_at__gte=start)
    date_to = filters.get("date_to")
    if date_to is not None:
        end = datetime.combine(date_to, time.max, tzinfo=local_timezone)
        queryset = queryset.filter(opened_at__lte=end)
    return queryset


def cash_shift_history_page(
    *,
    actor: User,
    filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    queryset = _filter_cash_shift_history_queryset(
        actor=actor,
        filters=filters,
        queryset=_visible_cash_shifts(actor),
    )

    cursor = _decode_cash_shift_cursor(filters.get("cursor"))
    if cursor is not None:
        queryset = queryset.filter(
            Q(opened_at__lt=cursor.opened_at)
            | Q(opened_at=cursor.opened_at, id__lt=cursor.shift_id)
        )

    page = list(queryset.order_by("-opened_at", "-id")[: CASH_SHIFT_PAGE_SIZE + 1])
    has_more = len(page) > CASH_SHIFT_PAGE_SIZE
    visible_page = page[:CASH_SHIFT_PAGE_SIZE]
    next_cursor = _encode_cash_shift_cursor(visible_page[-1]) if has_more else None
    return [cash_shift_summary(shift) for shift in visible_page], next_cursor


def _cash_entry_sum(condition: Q) -> Any:
    return Coalesce(
        Sum("entries__amount_minor", filter=condition),
        Value(0),
        output_field=BigIntegerField(),
    )


def cash_shift_history_export_rows(
    *,
    actor: User,
    filters: dict[str, Any],
    row_limit: int,
) -> list[dict[str, Any]]:
    queryset = _filter_cash_shift_history_queryset(
        actor=actor,
        filters=filters,
        queryset=_scope_cash_shift_queryset(CashShift.objects.all(), actor),
    ).annotate(
        export_operations_count=Count("entries"),
        export_payment_count=Count(
            "entries",
            filter=Q(entries__kind=CashLedgerEntryKind.PAYMENT),
        ),
        export_refund_count=Count(
            "entries",
            filter=Q(entries__kind=CashLedgerEntryKind.REFUND),
        ),
        export_payments_total_minor=_cash_entry_sum(Q(entries__kind=CashLedgerEntryKind.PAYMENT)),
        export_refunds_total_minor=_cash_entry_sum(Q(entries__kind=CashLedgerEntryKind.REFUND)),
        export_cash_payments_minor=_cash_entry_sum(
            Q(
                entries__kind=CashLedgerEntryKind.PAYMENT,
                entries__payment_method=PaymentMethod.CASH,
            )
        ),
        export_cash_refunds_minor=_cash_entry_sum(
            Q(
                entries__kind=CashLedgerEntryKind.REFUND,
                entries__payment_method=PaymentMethod.CASH,
            )
        ),
        export_card_payments_minor=_cash_entry_sum(
            Q(
                entries__kind=CashLedgerEntryKind.PAYMENT,
                entries__payment_method=PaymentMethod.CARD,
            )
        ),
        export_card_refunds_minor=_cash_entry_sum(
            Q(
                entries__kind=CashLedgerEntryKind.REFUND,
                entries__payment_method=PaymentMethod.CARD,
            )
        ),
        export_transfer_payments_minor=_cash_entry_sum(
            Q(
                entries__kind=CashLedgerEntryKind.PAYMENT,
                entries__payment_method=PaymentMethod.TRANSFER,
            )
        ),
        export_transfer_refunds_minor=_cash_entry_sum(
            Q(
                entries__kind=CashLedgerEntryKind.REFUND,
                entries__payment_method=PaymentMethod.TRANSFER,
            )
        ),
        export_deposits_minor=_cash_entry_sum(Q(entries__kind=CashLedgerEntryKind.DEPOSIT)),
        export_withdrawals_minor=_cash_entry_sum(Q(entries__kind=CashLedgerEntryKind.WITHDRAWAL)),
    )
    shifts = list(queryset.order_by("-opened_at", "-id")[: row_limit + 1])
    rows: list[dict[str, Any]] = []
    for shift in shifts:
        annotated_shift = cast(Any, shift)
        payments_total = int(annotated_shift.export_payments_total_minor)
        refunds_total = int(annotated_shift.export_refunds_total_minor)
        cash_payments = int(annotated_shift.export_cash_payments_minor)
        cash_refunds = int(annotated_shift.export_cash_refunds_minor)
        card_payments = int(annotated_shift.export_card_payments_minor)
        card_refunds = int(annotated_shift.export_card_refunds_minor)
        transfer_payments = int(annotated_shift.export_transfer_payments_minor)
        transfer_refunds = int(annotated_shift.export_transfer_refunds_minor)
        deposits = int(annotated_shift.export_deposits_minor)
        withdrawals = int(annotated_shift.export_withdrawals_minor)
        rows.append(
            {
                "shift": shift,
                "totals": {
                    "operations_count": int(annotated_shift.export_operations_count),
                    "payment_count": int(annotated_shift.export_payment_count),
                    "refund_count": int(annotated_shift.export_refund_count),
                    "payments_total_minor": payments_total,
                    "refunds_total_minor": refunds_total,
                    "revenue_minor": payments_total - refunds_total,
                    "cash_net_minor": cash_payments - cash_refunds,
                    "card_net_minor": card_payments - card_refunds,
                    "transfer_net_minor": transfer_payments - transfer_refunds,
                    "deposits_minor": deposits,
                    "withdrawals_minor": withdrawals,
                    "expected_cash_minor": (cash_payments - cash_refunds + deposits - withdrawals),
                },
            }
        )
    return rows


def _normalized_close_payload(
    *,
    shift_id: UUID,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "shift_id": str(shift_id),
        "actual_cash_minor": int(data["actual_cash_minor"]),
        "expected_operations_count": int(data["expected_operations_count"]),
        "cash_count_confirmed": True,
        "comment": str(data.get("comment", "")).strip(),
    }


def _existing_cash_shift_close(
    *,
    actor: User,
    shift_id: UUID,
    idempotency_key: str,
    payload_hash: str,
) -> CashShift | None:
    shift = (
        _cash_shift_queryset()
        .filter(
            closed_by=actor,
            close_idempotency_key=idempotency_key,
        )
        .first()
    )
    if shift is None:
        return None
    if shift.close_payload_hash != payload_hash:
        raise _close_idempotency_payload_mismatch()
    if shift.pk != shift_id or shift.status != CashShiftStatus.CLOSED:
        raise _close_idempotency_key_conflict()
    return shift


@transaction.atomic
def close_cash_shift(
    *,
    actor: User,
    shift_id: UUID,
    correlation_id: str,
    idempotency_key: str,
    data: dict[str, Any],
) -> tuple[CashShift, bool]:
    _validate_actor(actor)
    normalized = _normalized_close_payload(shift_id=shift_id, data=data)
    request_hash = _payload_hash(normalized)
    existing = _existing_cash_shift_close(
        actor=actor,
        shift_id=shift_id,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    locked_queryset = CashShift.objects.select_for_update(of=("self",)).select_related(
        "employee", "closed_by"
    )
    if actor.role != UserRole.ADMIN:
        locked_queryset = locked_queryset.filter(employee=actor)
    shift = locked_queryset.filter(pk=shift_id).first()
    if shift is None:
        raise _cash_shift_not_found()

    if shift.status == CashShiftStatus.CLOSED:
        if shift.closed_by_id == actor.pk and shift.close_idempotency_key == idempotency_key:
            if shift.close_payload_hash != request_hash:
                raise _close_idempotency_payload_mismatch()
            return _cash_shift_queryset().get(pk=shift.pk), True
        raise _cash_shift_already_closed()

    entries = list(
        CashLedgerEntry.objects.filter(cash_shift=shift)
        .select_related("created_by")
        .order_by("-posted_at", "-id")
    )
    totals = _cash_shift_totals(entries)
    if totals["operations_count"] != normalized["expected_operations_count"]:
        raise _cash_shift_changed()

    expected_cash_minor = totals["expected_cash_minor"]
    actual_cash_minor = normalized["actual_cash_minor"]
    discrepancy_minor = actual_cash_minor - expected_cash_minor
    comment = normalized["comment"]
    if discrepancy_minor != 0 and not comment:
        raise ApiProblem(
            code="validation_error",
            message="Дані запиту не пройшли перевірку.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"comment": ["Поясніть нестачу або надлишок готівки."]},
        )

    before = cash_shift_summary(shift, entries=entries)
    shift.status = CashShiftStatus.CLOSED
    shift.closed_at = timezone.now()
    shift.expected_cash_at_close_minor = expected_cash_minor
    shift.actual_cash_at_close_minor = actual_cash_minor
    shift.discrepancy_minor = discrepancy_minor
    shift.close_comment = comment
    shift.closed_by = actor
    shift.closed_by_name_snapshot = actor.display_name
    shift.closed_by_email_snapshot = actor.email
    shift.closed_by_role_snapshot = actor.role
    shift.close_idempotency_key = idempotency_key
    shift.close_payload_hash = request_hash
    try:
        with transaction.atomic():
            shift.save(
                update_fields=(
                    "status",
                    "closed_at",
                    "expected_cash_at_close_minor",
                    "actual_cash_at_close_minor",
                    "discrepancy_minor",
                    "close_comment",
                    "closed_by",
                    "closed_by_name_snapshot",
                    "closed_by_email_snapshot",
                    "closed_by_role_snapshot",
                    "close_idempotency_key",
                    "close_payload_hash",
                )
            )
    except IntegrityError as exc:
        if _constraint_name(exc) == "billing_shift_close_actor_key_unique":
            replay = _existing_cash_shift_close(
                actor=actor,
                shift_id=shift_id,
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
            )
            if replay is not None:
                return replay, True
        raise

    after = cash_shift_summary(shift, entries=entries)
    record_audit_event(
        actor=actor,
        action=AuditAction.CASH_SHIFT_CLOSED,
        object_type="cash_shift",
        object_id=shift.pk,
        object_label=shift.public_number,
        correlation_id=correlation_id,
        before=before,
        after=after,
        description="Закрито касову зміну після перерахунку готівки.",
    )
    return _cash_shift_queryset().get(pk=shift.pk), False


def _service_snapshot(visit: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": str(line.pk),
            "code": line.service_code,
            "name": line.service_name,
            "quantity": line.quantity,
            "unit_price_minor": line.price_minor,
            "line_total_minor": line.line_total_minor,
        }
        for line in visit.service_lines.all()
    ]


def _service_search_snapshot(visit: Any) -> str:
    return " ".join(
        f"{line.service_code} {line.service_name}" for line in visit.service_lines.all()
    )


def _payments_for_operations() -> QuerySet[Payment]:
    return Payment.objects.select_related(
        "ledger_entry__cash_shift",
        "ledger_entry__created_by",
        "refund_record__ledger_entry__cash_shift",
        "refund_record__ledger_entry__created_by",
    )


def _payment_operations_queryset(filters: dict[str, Any]) -> QuerySet[Receivable]:
    if filters.get("type") not in (None, CashLedgerEntryKind.PAYMENT):
        return Receivable.objects.none()
    if filters.get("status") == "POSTED":
        return Receivable.objects.none()

    operations = (
        Receivable.objects.select_related(
            "visit__patient",
            "visit__specialist",
        )
        .prefetch_related(
            "visit__service_lines",
            Prefetch("payment_records", queryset=_payments_for_operations()),
        )
        .annotate(
            operation_occurred_at=Coalesce(
                "payment_records__ledger_entry__posted_at",
                "visit__completed_at",
                "created_at",
                output_field=DateTimeField(),
            ),
            patient_search_name=Concat(
                "visit__patient__first_name",
                Value(" "),
                "visit__patient__last_name",
                output_field=CharField(),
            ),
        )
    )
    if search := str(filters.get("search", "")).strip():
        operations = operations.filter(
            Q(
                payment_records__isnull=True,
                visit__patient__first_name__icontains=search,
            )
            | Q(
                payment_records__isnull=True,
                visit__patient__last_name__icontains=search,
            )
            | Q(payment_records__isnull=True, patient_search_name__icontains=search)
            | Q(
                payment_records__isnull=True,
                visit__patient__phone__icontains=search,
            )
            | Q(
                payment_records__isnull=True,
                visit__patient__normalized_phone__icontains=search,
            )
            | Q(
                payment_records__isnull=True,
                visit__patient__public_number__icontains=search,
            )
            | Q(
                payment_records__isnull=True,
                visit__public_number__icontains=search,
            )
            | Q(payment_records__ledger_entry__public_number__icontains=search)
            | Q(payment_records__patient_name_snapshot__icontains=search)
            | Q(payment_records__patient_phone_snapshot__icontains=search)
            | Q(payment_records__patient_public_number_snapshot__icontains=search)
            | Q(payment_records__visit_public_number_snapshot__icontains=search)
            | Q(payment_records__services_search_snapshot__icontains=search)
            | Q(payment_records__refund_record__ledger_entry__public_number__icontains=search)
            | Q(payment_records__refund_record__reason__icontains=search)
            | Q(
                payment_records__isnull=True,
                visit__service_lines__service_code__icontains=search,
            )
            | Q(
                payment_records__isnull=True,
                visit__service_lines__service_name__icontains=search,
            )
        ).distinct()
    if filters.get("status") is not None:
        operations = operations.filter(status=filters["status"])
    if filters.get("payment_method") is not None:
        operations = operations.filter(
            payment_records__ledger_entry__payment_method=filters["payment_method"]
        )
    if patient_id := filters.get("patient_id"):
        operations = operations.filter(
            Q(payment_records__patient_id_snapshot=patient_id)
            | Q(payment_records__isnull=True, visit__patient_id=patient_id)
        )
    if date_from := filters.get("date_from"):
        operations = operations.filter(operation_occurred_at__date__gte=date_from)
    if date_to := filters.get("date_to"):
        operations = operations.filter(operation_occurred_at__date__lte=date_to)
    if "amount_minor" in filters:
        operations = operations.filter(amount_minor=filters["amount_minor"])
    if filters.get("refundable_only"):
        operations = operations.filter(
            amount_minor__gt=0,
            status=ReceivableStatus.PAID,
            payment_records__isnull=False,
            payment_records__refund_record__isnull=True,
        )
    return operations.order_by("-operation_occurred_at", "-id")


def _refund_operations_queryset(filters: dict[str, Any]) -> QuerySet[Refund]:
    if filters.get("type") not in (None, CashLedgerEntryKind.REFUND):
        return Refund.objects.none()
    if filters.get("status") not in (None, "POSTED"):
        return Refund.objects.none()
    if filters.get("refundable_only"):
        return Refund.objects.none()

    operations = _refund_with_context().annotate(operation_occurred_at=F("ledger_entry__posted_at"))
    if search := str(filters.get("search", "")).strip():
        operations = operations.filter(
            Q(ledger_entry__public_number__icontains=search)
            | Q(original_payment__ledger_entry__public_number__icontains=search)
            | Q(original_payment__patient_name_snapshot__icontains=search)
            | Q(original_payment__patient_phone_snapshot__icontains=search)
            | Q(original_payment__patient_public_number_snapshot__icontains=search)
            | Q(original_payment__visit_public_number_snapshot__icontains=search)
            | Q(original_payment__services_search_snapshot__icontains=search)
            | Q(reason__icontains=search)
            | Q(employee_name_snapshot__icontains=search)
            | Q(employee_email_snapshot__icontains=search)
        )
    if filters.get("payment_method") is not None:
        operations = operations.filter(ledger_entry__payment_method=filters["payment_method"])
    if patient_id := filters.get("patient_id"):
        operations = operations.filter(original_payment__patient_id_snapshot=patient_id)
    if date_from := filters.get("date_from"):
        operations = operations.filter(operation_occurred_at__date__gte=date_from)
    if date_to := filters.get("date_to"):
        operations = operations.filter(operation_occurred_at__date__lte=date_to)
    if "amount_minor" in filters:
        operations = operations.filter(ledger_entry__amount_minor=filters["amount_minor"])
    return operations.order_by("-operation_occurred_at", "-id")


def _cash_adjustment_operations_queryset(
    filters: dict[str, Any],
    *,
    operation_type: str,
) -> QuerySet[CashAdjustment]:
    requested_type = filters.get("type")
    if requested_type not in (None, operation_type):
        return CashAdjustment.objects.none()
    if filters.get("status") not in (None, "POSTED"):
        return CashAdjustment.objects.none()
    if (
        filters.get("payment_method") is not None
        or filters.get("patient_id") is not None
        or filters.get("refundable_only")
    ):
        return CashAdjustment.objects.none()

    operations = _cash_adjustment_with_context().annotate(
        operation_occurred_at=F("ledger_entry__posted_at")
    )
    operations = operations.filter(ledger_entry__kind=operation_type)
    if search := str(filters.get("search", "")).strip():
        operations = operations.filter(
            Q(ledger_entry__public_number__icontains=search)
            | Q(reason__icontains=search)
            | Q(comment__icontains=search)
            | Q(employee_name_snapshot__icontains=search)
            | Q(employee_email_snapshot__icontains=search)
        )
    if date_from := filters.get("date_from"):
        operations = operations.filter(operation_occurred_at__date__gte=date_from)
    if date_to := filters.get("date_to"):
        operations = operations.filter(operation_occurred_at__date__lte=date_to)
    if "amount_minor" in filters:
        operations = operations.filter(ledger_entry__amount_minor=filters["amount_minor"])
    return operations.order_by("-operation_occurred_at", "-id")


def _finance_payment_payload(payment: Payment) -> dict[str, Any]:
    ledger = payment.ledger_entry
    return {
        "id": payment.pk,
        "ledger_entry_id": ledger.pk,
        "public_number": ledger.public_number,
        "payment_method": ledger.payment_method,
        "comment": payment.comment,
        "posted_at": ledger.posted_at,
        "actor": {
            "id": ledger.created_by_id,
            "name": payment.employee_name_snapshot,
        },
        "cash_shift": {
            "id": ledger.cash_shift_id,
            "public_number": ledger.cash_shift.public_number,
        },
    }


def _finance_refund_payload(refund: Refund) -> dict[str, Any]:
    ledger = refund.ledger_entry
    return {
        "id": refund.pk,
        "ledger_entry_id": ledger.pk,
        "public_number": ledger.public_number,
        "reason": refund.reason,
        "posted_at": ledger.posted_at,
        "actor": {
            "id": ledger.created_by_id,
            "name": refund.employee_name_snapshot,
        },
        "cash_shift": {
            "id": ledger.cash_shift_id,
            "public_number": ledger.cash_shift.public_number,
        },
    }


def _finance_patient_from_payment(payment: Payment) -> dict[str, Any]:
    return {
        "id": payment.patient_id_snapshot,
        "public_number": payment.patient_public_number_snapshot,
        "display_name": payment.patient_name_snapshot,
        "phone": payment.patient_phone_snapshot,
    }


def _finance_visit_from_payment(payment: Payment) -> dict[str, Any]:
    return {
        "id": payment.receivable.visit_id,
        "public_number": payment.visit_public_number_snapshot,
        "completed_at": payment.visit_completed_at_snapshot,
        "payment_handoff_requested": payment.visit_payment_handoff_requested_snapshot,
        "total_minor": payment.visit_total_minor_snapshot,
        "specialist": {
            "id": payment.specialist_id_snapshot,
            "name": payment.specialist_name_snapshot,
        },
        "services": list(payment.services_snapshot),
    }


def finance_payment_operation_read_model(receivable: Receivable) -> dict[str, Any]:
    payment = next(iter(receivable.payment_records.all()), None)
    visit = receivable.visit
    patient = visit.patient
    if payment is None:
        patient_id = patient.pk
        patient_public_number = patient.public_number
        patient_display_name = patient.display_name
        patient_phone = patient.phone
        visit_public_number = visit.public_number
        visit_completed_at = visit.completed_at
        specialist_id = visit.specialist_id
        specialist_name = visit.specialist.display_name
        services = _service_snapshot(visit)
        payment_payload = None
        refund_payload = None
        occurred_at = visit.completed_at or receivable.created_at
    else:
        patient_id = payment.patient_id_snapshot
        patient_public_number = payment.patient_public_number_snapshot
        patient_display_name = payment.patient_name_snapshot
        patient_phone = payment.patient_phone_snapshot
        visit_public_number = payment.visit_public_number_snapshot
        visit_completed_at = payment.visit_completed_at_snapshot
        specialist_id = payment.specialist_id_snapshot
        specialist_name = payment.specialist_name_snapshot
        services = list(payment.services_snapshot)
        occurred_at = payment.ledger_entry.posted_at
        payment_payload = _finance_payment_payload(payment)
        refund = getattr(payment, "refund_record", None)
        refund_payload = None if refund is None else _finance_refund_payload(refund)
    return {
        "id": receivable.pk,
        "type": CashLedgerEntryKind.PAYMENT,
        "status": receivable.status,
        "occurred_at": occurred_at,
        "amount_minor": receivable.amount_minor,
        "patient": {
            "id": patient_id,
            "public_number": patient_public_number,
            "display_name": patient_display_name,
            "phone": patient_phone,
        },
        "visit": {
            "id": visit.pk,
            "public_number": visit_public_number,
            "completed_at": visit_completed_at,
            "payment_handoff_requested": (
                payment.visit_payment_handoff_requested_snapshot
                if payment is not None
                else visit.payment_handoff_requested
            ),
            "total_minor": (
                payment.visit_total_minor_snapshot if payment is not None else visit.total_minor
            ),
            "specialist": {
                "id": specialist_id,
                "name": specialist_name,
            },
            "services": services,
        },
        "payment": payment_payload,
        "refund": refund_payload,
    }


def finance_refund_operation_read_model(refund: Refund) -> dict[str, Any]:
    payment = refund.original_payment
    ledger = refund.ledger_entry
    return {
        "id": refund.pk,
        "type": CashLedgerEntryKind.REFUND,
        "status": "POSTED",
        "occurred_at": ledger.posted_at,
        "amount_minor": ledger.amount_minor,
        "patient": _finance_patient_from_payment(payment),
        "visit": _finance_visit_from_payment(payment),
        "original_payment": _finance_payment_payload(payment),
        "refund": _finance_refund_payload(refund),
    }


def finance_cash_adjustment_operation_read_model(
    adjustment: CashAdjustment,
) -> dict[str, Any]:
    ledger = adjustment.ledger_entry
    return {
        "id": adjustment.pk,
        "type": ledger.kind,
        "status": "POSTED",
        "occurred_at": ledger.posted_at,
        "amount_minor": ledger.amount_minor,
        "cash_adjustment": {
            "id": adjustment.pk,
            "ledger_entry_id": ledger.pk,
            "public_number": ledger.public_number,
            "reason": adjustment.reason,
            "comment": adjustment.comment,
            "posted_at": ledger.posted_at,
            "actor": {
                "id": ledger.created_by_id,
                "name": adjustment.employee_name_snapshot,
            },
            "cash_shift": {
                "id": ledger.cash_shift_id,
                "public_number": ledger.cash_shift.public_number,
            },
        },
    }


@dataclass(frozen=True)
class FinanceOperationCursor:
    occurred_at: datetime
    operation_id: UUID
    operation_type: str


@dataclass(frozen=True)
class FinanceOperationCandidate:
    occurred_at: datetime
    operation_id: UUID
    operation_type: str
    value: Receivable | Refund | CashAdjustment


_FINANCE_CURSOR_SALT = "billing.finance.operations.v1"
_FINANCE_PAGE_SIZE = 40


def _decode_finance_cursor(value: str | None) -> FinanceOperationCursor | None:
    if not value:
        return None
    try:
        payload = signing.loads(value, salt=_FINANCE_CURSOR_SALT)
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        operation_id = UUID(str(payload["id"]))
        operation_type = str(payload["type"])
        if operation_type not in CashLedgerEntryKind.values or occurred_at.tzinfo is None:
            raise ValueError
    except (KeyError, TypeError, ValueError, signing.BadSignature) as exc:
        raise ApiProblem(
            code="validation_error",
            message="Курсор фінансових операцій недійсний.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            fields={"cursor": ["Оновіть список і спробуйте ще раз."]},
        ) from exc
    return FinanceOperationCursor(occurred_at, operation_id, operation_type)


def _encode_finance_cursor(candidate: FinanceOperationCandidate) -> str:
    return signing.dumps(
        {
            "occurred_at": candidate.occurred_at.isoformat(),
            "id": str(candidate.operation_id),
            "type": candidate.operation_type,
        },
        salt=_FINANCE_CURSOR_SALT,
        compress=True,
    )


def _apply_finance_cursor(
    queryset: QuerySet[Any],
    *,
    operation_type: str,
    cursor: FinanceOperationCursor | None,
) -> QuerySet[Any]:
    if cursor is None:
        return queryset
    same_id_lookup = "id__lte" if operation_type < cursor.operation_type else "id__lt"
    return queryset.filter(
        Q(operation_occurred_at__lt=cursor.occurred_at)
        | Q(
            operation_occurred_at=cursor.occurred_at,
            **{same_id_lookup: cursor.operation_id},
        )
    )


def _finance_operation_candidates(
    *,
    filters: dict[str, Any],
    cursor: FinanceOperationCursor | None,
    per_type_limit: int,
) -> list[FinanceOperationCandidate]:
    payment_rows = list(
        _apply_finance_cursor(
            _payment_operations_queryset(filters),
            operation_type=CashLedgerEntryKind.PAYMENT,
            cursor=cursor,
        )[:per_type_limit]
    )
    refund_rows = list(
        _apply_finance_cursor(
            _refund_operations_queryset(filters),
            operation_type=CashLedgerEntryKind.REFUND,
            cursor=cursor,
        )[:per_type_limit]
    )
    deposit_rows = list(
        _apply_finance_cursor(
            _cash_adjustment_operations_queryset(
                filters,
                operation_type=CashLedgerEntryKind.DEPOSIT,
            ),
            operation_type=CashLedgerEntryKind.DEPOSIT,
            cursor=cursor,
        )[:per_type_limit]
    )
    withdrawal_rows = list(
        _apply_finance_cursor(
            _cash_adjustment_operations_queryset(
                filters,
                operation_type=CashLedgerEntryKind.WITHDRAWAL,
            ),
            operation_type=CashLedgerEntryKind.WITHDRAWAL,
            cursor=cursor,
        )[:per_type_limit]
    )
    candidates = [
        *(
            FinanceOperationCandidate(
                row.operation_occurred_at,
                row.pk,
                CashLedgerEntryKind.PAYMENT,
                row,
            )
            for row in payment_rows
        ),
        *(
            FinanceOperationCandidate(
                row.operation_occurred_at,
                row.pk,
                CashLedgerEntryKind.REFUND,
                row,
            )
            for row in refund_rows
        ),
        *(
            FinanceOperationCandidate(
                row.operation_occurred_at,
                row.pk,
                row.ledger_entry.kind,
                row,
            )
            for row in [*deposit_rows, *withdrawal_rows]
        ),
    ]
    candidates.sort(
        key=lambda item: (
            item.occurred_at,
            str(item.operation_id),
            item.operation_type,
        ),
        reverse=True,
    )
    return candidates


def _finance_operation_candidate_read_model(
    item: FinanceOperationCandidate,
) -> dict[str, Any]:
    if item.operation_type == CashLedgerEntryKind.PAYMENT:
        return finance_payment_operation_read_model(cast(Receivable, item.value))
    if item.operation_type == CashLedgerEntryKind.REFUND:
        return finance_refund_operation_read_model(cast(Refund, item.value))
    return finance_cash_adjustment_operation_read_model(cast(CashAdjustment, item.value))


def finance_operations_page(
    *,
    actor: User,
    filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    _validate_finance_actor(actor)
    cursor = _decode_finance_cursor(filters.get("cursor"))
    candidates = _finance_operation_candidates(
        filters=filters,
        cursor=cursor,
        per_type_limit=_FINANCE_PAGE_SIZE + 1,
    )
    page = candidates[:_FINANCE_PAGE_SIZE]
    operations = [_finance_operation_candidate_read_model(item) for item in page]
    next_cursor = _encode_finance_cursor(page[-1]) if len(candidates) > len(page) else None
    return operations, next_cursor


def finance_operations_export_rows(
    *,
    actor: User,
    filters: dict[str, Any],
    row_limit: int,
) -> list[dict[str, Any]]:
    _validate_finance_actor(actor)
    candidates = _finance_operation_candidates(
        filters=filters,
        cursor=None,
        per_type_limit=row_limit + 1,
    )
    return [_finance_operation_candidate_read_model(item) for item in candidates[: row_limit + 1]]


def payment_operation_by_receivable_id(receivable_id: UUID) -> dict[str, Any]:
    receivable = _payment_operations_queryset({}).get(pk=receivable_id)
    return finance_payment_operation_read_model(receivable)


def payment_audit_snapshot(payment: Payment) -> dict[str, Any]:
    ledger = payment.ledger_entry
    return {
        "payment_id": payment.pk,
        "ledger_entry_id": ledger.pk,
        "public_number": ledger.public_number,
        "receivable_id": payment.receivable_id,
        "visit_id": payment.receivable.visit_id,
        "patient_id": payment.patient_id_snapshot,
        "cash_shift_id": ledger.cash_shift_id,
        "amount_minor": ledger.amount_minor,
        "payment_method": ledger.payment_method,
        "comment": payment.comment,
        "receivable_status": payment.receivable.status,
        "posted_at": ledger.posted_at,
    }


@transaction.atomic
def post_payment(
    *,
    actor: User,
    correlation_id: str,
    idempotency_key: str,
    data: dict[str, Any],
) -> tuple[Payment, bool]:
    _validate_finance_actor(actor)
    normalized = {
        "visit_id": str(data["visit_id"]),
        "payment_method": str(data["payment_method"]),
        "comment": str(data.get("comment", "")).strip(),
    }
    request_hash = _payload_hash(normalized)
    existing = _existing_payment(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    receivable = (
        Receivable.objects.select_for_update(of=("self",))
        .select_related("visit__patient", "visit__specialist")
        .prefetch_related("visit__service_lines")
        .filter(visit_id=data["visit_id"])
        .first()
    )
    if receivable is None:
        raise ApiProblem(
            code="not_found",
            message="Фінансове зобов’язання для прийому не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    existing = _existing_payment(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True
    if receivable.status == ReceivableStatus.PAID:
        raise _receivable_already_paid()
    if receivable.status == ReceivableStatus.REFUNDED:
        raise _receivable_already_refunded()
    if (
        receivable.status != ReceivableStatus.OPEN
        or receivable.amount_minor <= 0
        or receivable.visit.status != VisitStatus.COMPLETED
        or receivable.visit.completed_at is None
        or receivable.visit.total_minor != receivable.amount_minor
    ):
        raise _visit_not_payable()

    shift = (
        CashShift.objects.select_for_update(of=("self",))
        .filter(employee=actor, status=CashShiftStatus.OPEN)
        .first()
    )
    if shift is None:
        raise _cash_shift_required()

    existing = _existing_payment(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    patient = receivable.visit.patient
    specialist = receivable.visit.specialist
    before = {
        "receivable_id": receivable.pk,
        "visit_id": receivable.visit_id,
        "amount_minor": receivable.amount_minor,
        "receivable_status": receivable.status,
    }
    try:
        with transaction.atomic():
            ledger = CashLedgerEntry.objects.create(
                cash_shift=shift,
                created_by=actor,
                kind=CashLedgerEntryKind.PAYMENT,
                amount_minor=receivable.amount_minor,
                payment_method=data["payment_method"],
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
            )
            payment = Payment.objects.create(
                ledger_entry=ledger,
                receivable=receivable,
                comment=normalized["comment"],
                patient_id_snapshot=patient.pk,
                patient_public_number_snapshot=patient.public_number,
                patient_name_snapshot=patient.display_name,
                patient_phone_snapshot=patient.phone,
                visit_public_number_snapshot=receivable.visit.public_number,
                visit_completed_at_snapshot=receivable.visit.completed_at,
                visit_payment_handoff_requested_snapshot=(
                    receivable.visit.payment_handoff_requested
                ),
                visit_total_minor_snapshot=receivable.visit.total_minor,
                specialist_id_snapshot=specialist.pk,
                specialist_name_snapshot=specialist.display_name,
                employee_name_snapshot=actor.display_name,
                employee_email_snapshot=actor.email,
                services_snapshot=_service_snapshot(receivable.visit),
                services_search_snapshot=_service_search_snapshot(receivable.visit),
            )
    except IntegrityError as exc:
        constraint = _constraint_name(exc)
        if constraint == "billing_payment_receivable_unique":
            raise _receivable_already_paid() from exc
        if constraint == "billing_ledger_actor_kind_idempotency_unique":
            replay = _existing_payment(
                actor=actor,
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
            )
            if replay is not None:
                return replay, True
        raise

    receivable.status = ReceivableStatus.PAID
    receivable.save(update_fields=("status", "updated_at"))
    payment = _payment_with_context().get(pk=payment.pk)
    record_audit_event(
        actor=actor,
        action=AuditAction.PAYMENT_POSTED,
        object_type="payment",
        object_id=payment.pk,
        object_label=payment.ledger_entry.public_number,
        correlation_id=correlation_id,
        before=before,
        after=payment_audit_snapshot(payment),
        description="Проведено повну оплату завершеного прийому.",
    )
    return payment, False


def refund_audit_snapshot(refund: Refund) -> dict[str, Any]:
    ledger = refund.ledger_entry
    payment = refund.original_payment
    return {
        "refund_id": refund.pk,
        "ledger_entry_id": ledger.pk,
        "public_number": ledger.public_number,
        "original_payment_id": payment.pk,
        "original_payment_public_number": payment.ledger_entry.public_number,
        "receivable_id": payment.receivable_id,
        "visit_id": payment.receivable.visit_id,
        "patient_id": payment.patient_id_snapshot,
        "cash_shift_id": ledger.cash_shift_id,
        "amount_minor": ledger.amount_minor,
        "payment_method": ledger.payment_method,
        "reason": refund.reason,
        "receivable_status": payment.receivable.status,
        "posted_at": ledger.posted_at,
    }


@transaction.atomic
def post_refund(
    *,
    actor: User,
    correlation_id: str,
    idempotency_key: str,
    payment_id: UUID,
    data: dict[str, Any],
) -> tuple[Refund, bool]:
    _validate_finance_actor(actor)
    normalized = {
        "payment_id": str(payment_id),
        "reason": str(data["reason"]).strip(),
    }
    request_hash = _payload_hash(normalized)
    existing = _existing_refund(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    payment_identity = Payment.objects.filter(pk=payment_id).values("receivable_id").first()
    if payment_identity is None:
        raise ApiProblem(
            code="not_found",
            message="Оплату для повернення не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    receivable = (
        Receivable.objects.select_for_update(of=("self",))
        .select_related("visit")
        .get(pk=payment_identity["receivable_id"])
    )
    payment = (
        _payment_with_context()
        .select_for_update(of=("self",))
        .filter(pk=payment_id, receivable=receivable)
        .first()
    )
    if payment is None:
        raise ApiProblem(
            code="not_found",
            message="Оплату для повернення не знайдено.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    existing = _existing_refund(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True
    if (
        receivable.status == ReceivableStatus.REFUNDED
        or Refund.objects.filter(original_payment=payment).exists()
    ):
        raise _payment_already_refunded()
    if (
        receivable.status != ReceivableStatus.PAID
        or receivable.amount_minor <= 0
        or payment.ledger_entry.amount_minor != receivable.amount_minor
    ):
        raise _payment_not_refundable()

    shift = (
        CashShift.objects.select_for_update(of=("self",))
        .filter(employee=actor, status=CashShiftStatus.OPEN)
        .first()
    )
    if shift is None:
        raise _cash_shift_required()

    existing = _existing_refund(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True
    before_available_cash = available_cash_minor(shift)
    if (
        payment.ledger_entry.payment_method == PaymentMethod.CASH
        and before_available_cash < payment.ledger_entry.amount_minor
    ):
        raise _insufficient_cash()

    before = {
        "original_payment_id": payment.pk,
        "receivable_id": receivable.pk,
        "receivable_status": receivable.status,
        "available_cash_minor": before_available_cash,
    }
    try:
        with transaction.atomic():
            ledger = CashLedgerEntry.objects.create(
                cash_shift=shift,
                created_by=actor,
                kind=CashLedgerEntryKind.REFUND,
                amount_minor=payment.ledger_entry.amount_minor,
                payment_method=payment.ledger_entry.payment_method,
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
            )
            refund = Refund.objects.create(
                ledger_entry=ledger,
                original_payment=payment,
                reason=normalized["reason"],
                employee_name_snapshot=actor.display_name,
                employee_email_snapshot=actor.email,
            )
            receivable.status = ReceivableStatus.REFUNDED
            receivable.save(update_fields=("status", "updated_at"))
    except IntegrityError as exc:
        constraint = _constraint_name(exc)
        if constraint in {
            "billing_ledger_actor_kind_idempotency_unique",
            "billing_refund_ledger_unique",
        }:
            replay = _existing_refund(
                actor=actor,
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
            )
            if replay is not None:
                return replay, True
        if constraint == "billing_ledger_sufficient_cash":
            raise _insufficient_cash() from exc
        if Refund.objects.filter(original_payment_id=payment_id).exists():
            raise _payment_already_refunded() from exc
        raise

    refund = _refund_with_context().get(pk=refund.pk)
    record_audit_event(
        actor=actor,
        action=AuditAction.REFUND_POSTED,
        object_type="refund",
        object_id=refund.pk,
        object_label=refund.ledger_entry.public_number,
        correlation_id=correlation_id,
        before=before,
        after={
            **refund_audit_snapshot(refund),
            "available_cash_minor": available_cash_minor(shift),
        },
        description="Проведено повне повернення оплати.",
    )
    return refund, False


def cash_adjustment_audit_snapshot(adjustment: CashAdjustment) -> dict[str, Any]:
    ledger = adjustment.ledger_entry
    return {
        "cash_adjustment_id": adjustment.pk,
        "ledger_entry_id": ledger.pk,
        "public_number": ledger.public_number,
        "cash_shift_id": ledger.cash_shift_id,
        "type": ledger.kind,
        "amount_minor": ledger.amount_minor,
        "reason": adjustment.reason,
        "comment": adjustment.comment,
        "posted_at": ledger.posted_at,
    }


@transaction.atomic
def post_cash_movement(
    *,
    actor: User,
    correlation_id: str,
    idempotency_key: str,
    data: dict[str, Any],
) -> tuple[CashAdjustment, bool]:
    _validate_finance_actor(actor)
    movement_type = str(data["type"])
    amount_minor = int(data["amount_minor"])
    reason = str(data["reason"]).strip()
    comment = str(data.get("comment", "")).strip()
    normalized: dict[str, Any] = {
        "type": movement_type,
        "amount_minor": amount_minor,
        "reason": reason,
        "comment": comment,
    }
    request_hash = _payload_hash(normalized)
    existing = _existing_cash_adjustment(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True

    shift = (
        CashShift.objects.select_for_update(of=("self",))
        .filter(employee=actor, status=CashShiftStatus.OPEN)
        .first()
    )
    if shift is None:
        raise _cash_shift_required()

    existing = _existing_cash_adjustment(
        actor=actor,
        idempotency_key=idempotency_key,
        payload_hash=request_hash,
    )
    if existing is not None:
        return existing, True
    before_available_cash = available_cash_minor(shift)
    if movement_type == CashLedgerEntryKind.WITHDRAWAL and before_available_cash < amount_minor:
        raise _insufficient_cash()

    try:
        with transaction.atomic():
            ledger = CashLedgerEntry.objects.create(
                cash_shift=shift,
                created_by=actor,
                kind=movement_type,
                amount_minor=amount_minor,
                payment_method="",
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
            )
            adjustment = CashAdjustment.objects.create(
                ledger_entry=ledger,
                reason=reason,
                comment=comment,
                employee_name_snapshot=actor.display_name,
                employee_email_snapshot=actor.email,
            )
    except IntegrityError as exc:
        constraint = _constraint_name(exc)
        if constraint in {
            "billing_ledger_actor_kind_idempotency_unique",
            "billing_cash_movement_actor_idempotency_unique",
            "billing_cash_adjustment_ledger_unique",
        }:
            replay = _existing_cash_adjustment(
                actor=actor,
                idempotency_key=idempotency_key,
                payload_hash=request_hash,
            )
            if replay is not None:
                return replay, True
        if constraint == "billing_ledger_sufficient_cash":
            raise _insufficient_cash() from exc
        raise

    adjustment = _cash_adjustment_with_context().get(pk=adjustment.pk)
    record_audit_event(
        actor=actor,
        action=(
            AuditAction.CASH_DEPOSIT_POSTED
            if adjustment.ledger_entry.kind == CashLedgerEntryKind.DEPOSIT
            else AuditAction.CASH_WITHDRAWAL_POSTED
        ),
        object_type="cash_adjustment",
        object_id=adjustment.pk,
        object_label=adjustment.ledger_entry.public_number,
        correlation_id=correlation_id,
        before={
            "cash_shift_id": shift.pk,
            "available_cash_minor": before_available_cash,
        },
        after={
            **cash_adjustment_audit_snapshot(adjustment),
            "available_cash_minor": available_cash_minor(shift),
        },
        description=(
            "Проведено службове внесення готівки."
            if adjustment.ledger_entry.kind == CashLedgerEntryKind.DEPOSIT
            else "Проведено службове вилучення готівки."
        ),
    )
    return adjustment, False
