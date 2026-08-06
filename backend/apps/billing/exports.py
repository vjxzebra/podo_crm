import csv
from collections.abc import Mapping, Sequence
from datetime import datetime
from io import StringIO
from typing import Any, cast

from django.utils import timezone

from apps.billing.models import CashLedgerEntry, CashLedgerEntryKind, CashShift
from apps.billing.services import cash_shift_summary
from config.api.csv import spreadsheet_safe_text

CASH_SHIFT_EXPORT_ENTRY_LIMIT = 5000
CASH_SHIFT_EXPORT_COLUMNS = (
    "row_type",
    "shift_number",
    "shift_status",
    "shift_opened_at_local",
    "shift_closed_at_local",
    "shift_employee_name",
    "shift_employee_email",
    "currency",
    "opening_basis",
    "opening_cash_minor",
    "opening_source_shift_number",
    "operations_count",
    "revenue_minor",
    "expected_cash_minor",
    "actual_cash_minor",
    "discrepancy_minor",
    "close_comment",
    "closed_by_name",
    "closed_by_email",
    "entry_posted_at_local",
    "entry_number",
    "entry_kind",
    "payment_method",
    "signed_amount_minor",
    "actor_name",
    "actor_email",
)

CASH_SHIFT_HISTORY_EXPORT_ROW_LIMIT = 5000
CASH_SHIFT_HISTORY_EXPORT_COLUMNS = (
    "row_type",
    "shift_number",
    "shift_status",
    "opened_at_local",
    "closed_at_local",
    "employee_name",
    "employee_email",
    "currency",
    "opening_basis",
    "opening_cash_minor",
    "opening_source_shift_number",
    "shift_count",
    "open_shift_count",
    "closed_shift_count",
    "operations_count",
    "payment_count",
    "refund_count",
    "payments_total_minor",
    "refunds_total_minor",
    "revenue_minor",
    "cash_net_minor",
    "card_net_minor",
    "transfer_net_minor",
    "deposits_minor",
    "withdrawals_minor",
    "expected_cash_minor",
    "actual_cash_minor",
    "discrepancy_minor",
    "close_comment",
    "closed_by_name",
    "closed_by_email",
)

FINANCE_OPERATION_EXPORT_ROW_LIMIT = 5000
FINANCE_OPERATION_EXPORT_COLUMNS = (
    "row_type",
    "filter_search",
    "filter_type",
    "filter_status",
    "filter_payment_method",
    "filter_date_from",
    "filter_date_to",
    "operation_count",
    "payment_count",
    "refund_count",
    "deposit_count",
    "withdrawal_count",
    "open_count",
    "paid_count",
    "refunded_count",
    "posted_count",
    "outstanding_minor",
    "payments_minor",
    "refunds_minor",
    "deposits_minor",
    "withdrawals_minor",
    "net_posted_minor",
    "occurred_at_local",
    "operation_number",
    "operation_type",
    "operation_status",
    "amount_minor",
    "cash_effect_minor",
    "currency",
    "payment_method",
    "patient_number",
    "patient_name",
    "visit_number",
    "visit_completed_at_local",
    "specialist_name",
    "services",
    "cash_shift_number",
    "actor_name",
    "reason",
    "comment",
    "original_payment_number",
)


def signed_ledger_amount(entry: CashLedgerEntry) -> int:
    if entry.kind in (CashLedgerEntryKind.REFUND, CashLedgerEntryKind.WITHDRAWAL):
        return -entry.amount_minor
    return entry.amount_minor


def _local_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return timezone.localtime(value).isoformat(timespec="seconds")


def render_cash_shift_csv(
    shift: CashShift,
    entries: Sequence[CashLedgerEntry],
) -> bytes:
    resolved_entries = list(entries)
    summary = cash_shift_summary(shift, entries=resolved_entries)
    employee = summary["employee"]
    totals = summary["totals"]
    reconciliation = summary["reconciliation"]
    common = (
        spreadsheet_safe_text(summary["public_number"]),
        spreadsheet_safe_text(summary["status"]),
        _local_iso(summary["opened_at"]),
        _local_iso(summary["closed_at"]),
        spreadsheet_safe_text(employee["name"]),
        spreadsheet_safe_text(employee["email"]),
        "UAH",
        spreadsheet_safe_text(summary["opening_basis"]),
        summary["opening_cash_minor"],
        ""
        if summary["opening_source_shift"] is None
        else spreadsheet_safe_text(summary["opening_source_shift"]["public_number"]),
    )

    output = StringIO(newline="")
    csv_writer = csv.writer(output, dialect="excel", lineterminator="\r\n")
    csv_writer.writerow(CASH_SHIFT_EXPORT_COLUMNS)
    csv_writer.writerow(
        (
            "SHIFT_SUMMARY",
            *common,
            totals["operations_count"],
            totals["revenue_minor"],
            totals["expected_cash_minor"],
            "" if reconciliation is None else reconciliation["actual_cash_minor"],
            "" if reconciliation is None else reconciliation["discrepancy_minor"],
            "" if reconciliation is None else spreadsheet_safe_text(reconciliation["comment"]),
            ""
            if reconciliation is None
            else spreadsheet_safe_text(reconciliation["closed_by"]["name"]),
            ""
            if reconciliation is None
            else spreadsheet_safe_text(reconciliation["closed_by"]["email"]),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
    )
    for entry in resolved_entries:
        csv_writer.writerow(
            (
                "LEDGER_ENTRY",
                *common,
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                _local_iso(entry.posted_at),
                spreadsheet_safe_text(entry.public_number),
                spreadsheet_safe_text(entry.kind),
                spreadsheet_safe_text(entry.payment_method),
                signed_ledger_amount(entry),
                spreadsheet_safe_text(entry.actor_name_snapshot),
                spreadsheet_safe_text(entry.actor_email_snapshot),
            )
        )
    return output.getvalue().encode("utf-8-sig")


def _history_totals(totals: Mapping[str, int]) -> tuple[int, ...]:
    return (
        totals["operations_count"],
        totals["payment_count"],
        totals["refund_count"],
        totals["payments_total_minor"],
        totals["refunds_total_minor"],
        totals["revenue_minor"],
        totals["cash_net_minor"],
        totals["card_net_minor"],
        totals["transfer_net_minor"],
        totals["deposits_minor"],
        totals["withdrawals_minor"],
    )


def render_cash_shift_history_csv(rows: Sequence[Mapping[str, Any]]) -> bytes:
    report_totals = {
        "operations_count": 0,
        "payment_count": 0,
        "refund_count": 0,
        "payments_total_minor": 0,
        "refunds_total_minor": 0,
        "revenue_minor": 0,
        "cash_net_minor": 0,
        "card_net_minor": 0,
        "transfer_net_minor": 0,
        "deposits_minor": 0,
        "withdrawals_minor": 0,
    }
    open_count = 0
    closed_count = 0
    actual_cash_minor = 0
    discrepancy_minor = 0
    for row in rows:
        shift = cast(CashShift, row["shift"])
        totals = cast(Mapping[str, int], row["totals"])
        for name in report_totals:
            report_totals[name] += totals[name]
        if shift.status == "CLOSED":
            closed_count += 1
            actual_cash_minor += int(shift.actual_cash_at_close_minor or 0)
            discrepancy_minor += int(shift.discrepancy_minor or 0)
        else:
            open_count += 1

    output = StringIO(newline="")
    csv_writer = csv.writer(output, dialect="excel", lineterminator="\r\n")
    csv_writer.writerow(CASH_SHIFT_HISTORY_EXPORT_COLUMNS)
    csv_writer.writerow(
        (
            "REPORT_SUMMARY",
            "",
            "",
            "",
            "",
            "",
            "",
            "UAH",
            "",
            "",
            "",
            len(rows),
            open_count,
            closed_count,
            *_history_totals(report_totals),
            "",
            "",
            "",
            "",
            "",
            "",
        )
    )
    for row in rows:
        shift = cast(CashShift, row["shift"])
        totals = cast(Mapping[str, int], row["totals"])
        is_closed = shift.status == "CLOSED"
        csv_writer.writerow(
            (
                "CASH_SHIFT",
                spreadsheet_safe_text(shift.public_number),
                spreadsheet_safe_text(shift.status),
                _local_iso(shift.opened_at),
                _local_iso(shift.closed_at),
                spreadsheet_safe_text(shift.employee_name_snapshot),
                spreadsheet_safe_text(shift.employee_email_snapshot),
                "UAH",
                spreadsheet_safe_text(shift.opening_basis),
                shift.opening_cash_minor,
                ""
                if shift.opening_source_shift is None
                else spreadsheet_safe_text(shift.opening_source_shift.public_number),
                "",
                "",
                "",
                *_history_totals(totals),
                totals["expected_cash_minor"],
                "" if not is_closed else shift.actual_cash_at_close_minor,
                "" if not is_closed else shift.discrepancy_minor,
                "" if not is_closed else spreadsheet_safe_text(shift.close_comment),
                "" if not is_closed else spreadsheet_safe_text(shift.closed_by_name_snapshot),
                "" if not is_closed else spreadsheet_safe_text(shift.closed_by_email_snapshot),
            )
        )
    return output.getvalue().encode("utf-8-sig")


def _finance_cash_effect(operation: Mapping[str, Any]) -> int:
    amount = int(operation["amount_minor"])
    operation_type = str(operation["type"])
    if operation_type == CashLedgerEntryKind.PAYMENT:
        return amount if operation.get("payment") is not None else 0
    if operation_type in (CashLedgerEntryKind.REFUND, CashLedgerEntryKind.WITHDRAWAL):
        return -amount
    return amount


def _finance_services(operation: Mapping[str, Any]) -> str:
    visit = operation.get("visit")
    if not isinstance(visit, Mapping):
        return ""
    services = cast(Sequence[Mapping[str, Any]], visit["services"])
    return "; ".join(
        f"{service['code']} {service['name']} ×{service['quantity']}" for service in services
    )


def _finance_operation_cells(operation: Mapping[str, Any]) -> tuple[Any, ...]:
    operation_type = str(operation["type"])
    patient = operation.get("patient")
    visit = operation.get("visit")
    payment_method = ""
    cash_shift_number = ""
    actor_name = ""
    reason = ""
    comment = ""
    original_payment_number = ""
    if operation_type == CashLedgerEntryKind.PAYMENT:
        payment = operation.get("payment")
        if isinstance(payment, Mapping):
            operation_number = payment["public_number"]
            payment_method = payment["payment_method"]
            cash_shift_number = cast(Mapping[str, Any], payment["cash_shift"])["public_number"]
            actor_name = cast(Mapping[str, Any], payment["actor"])["name"]
            comment = payment["comment"]
        else:
            operation_number = cast(Mapping[str, Any], visit)["public_number"]
    elif operation_type == CashLedgerEntryKind.REFUND:
        refund = cast(Mapping[str, Any], operation["refund"])
        original_payment = cast(Mapping[str, Any], operation["original_payment"])
        operation_number = refund["public_number"]
        payment_method = original_payment["payment_method"]
        cash_shift_number = cast(Mapping[str, Any], refund["cash_shift"])["public_number"]
        actor_name = cast(Mapping[str, Any], refund["actor"])["name"]
        reason = refund["reason"]
        original_payment_number = original_payment["public_number"]
    else:
        adjustment = cast(Mapping[str, Any], operation["cash_adjustment"])
        operation_number = adjustment["public_number"]
        cash_shift_number = cast(Mapping[str, Any], adjustment["cash_shift"])["public_number"]
        actor_name = cast(Mapping[str, Any], adjustment["actor"])["name"]
        reason = adjustment["reason"]
        comment = adjustment["comment"]

    patient_mapping = patient if isinstance(patient, Mapping) else {}
    visit_mapping = visit if isinstance(visit, Mapping) else {}
    specialist = visit_mapping.get("specialist")
    return (
        _local_iso(cast(datetime, operation["occurred_at"])),
        spreadsheet_safe_text(operation_number),
        spreadsheet_safe_text(operation_type),
        spreadsheet_safe_text(operation["status"]),
        operation["amount_minor"],
        _finance_cash_effect(operation),
        "UAH",
        spreadsheet_safe_text(payment_method),
        spreadsheet_safe_text(patient_mapping.get("public_number", "")),
        spreadsheet_safe_text(patient_mapping.get("display_name", "")),
        spreadsheet_safe_text(visit_mapping.get("public_number", "")),
        _local_iso(cast(datetime | None, visit_mapping.get("completed_at"))),
        spreadsheet_safe_text(
            specialist.get("name", "") if isinstance(specialist, Mapping) else ""
        ),
        spreadsheet_safe_text(_finance_services(operation)),
        spreadsheet_safe_text(cash_shift_number),
        spreadsheet_safe_text(actor_name),
        spreadsheet_safe_text(reason),
        spreadsheet_safe_text(comment),
        spreadsheet_safe_text(original_payment_number),
    )


def render_finance_operations_csv(
    operations: Sequence[Mapping[str, Any]],
    filters: Mapping[str, Any],
) -> bytes:
    summary = {
        "payment_count": 0,
        "refund_count": 0,
        "deposit_count": 0,
        "withdrawal_count": 0,
        "open_count": 0,
        "paid_count": 0,
        "refunded_count": 0,
        "posted_count": 0,
        "outstanding_minor": 0,
        "payments_minor": 0,
        "refunds_minor": 0,
        "deposits_minor": 0,
        "withdrawals_minor": 0,
        "net_posted_minor": 0,
    }
    for operation in operations:
        operation_type = str(operation["type"]).lower()
        operation_status = str(operation["status"]).lower()
        summary[f"{operation_type}_count"] += 1
        summary[f"{operation_status}_count"] += 1
        amount = int(operation["amount_minor"])
        cash_effect = _finance_cash_effect(operation)
        if operation["type"] == CashLedgerEntryKind.PAYMENT:
            if operation["status"] == "OPEN":
                summary["outstanding_minor"] += amount
            elif operation.get("payment") is not None:
                summary["payments_minor"] += amount
        elif operation["type"] == CashLedgerEntryKind.REFUND:
            summary["refunds_minor"] += amount
        elif operation["type"] == CashLedgerEntryKind.DEPOSIT:
            summary["deposits_minor"] += amount
        else:
            summary["withdrawals_minor"] += amount
        summary["net_posted_minor"] += cash_effect

    filter_cells = (
        spreadsheet_safe_text(filters.get("search", "")),
        spreadsheet_safe_text(filters.get("type", "")),
        spreadsheet_safe_text(filters.get("status", "")),
        spreadsheet_safe_text(filters.get("payment_method", "")),
        "" if filters.get("date_from") is None else filters["date_from"].isoformat(),
        "" if filters.get("date_to") is None else filters["date_to"].isoformat(),
    )
    summary_cells = (
        len(operations),
        summary["payment_count"],
        summary["refund_count"],
        summary["deposit_count"],
        summary["withdrawal_count"],
        summary["open_count"],
        summary["paid_count"],
        summary["refunded_count"],
        summary["posted_count"],
        summary["outstanding_minor"],
        summary["payments_minor"],
        summary["refunds_minor"],
        summary["deposits_minor"],
        summary["withdrawals_minor"],
        summary["net_posted_minor"],
    )

    output = StringIO(newline="")
    csv_writer = csv.writer(output, dialect="excel", lineterminator="\r\n")
    csv_writer.writerow(FINANCE_OPERATION_EXPORT_COLUMNS)
    csv_writer.writerow(
        (
            "REPORT_SUMMARY",
            *filter_cells,
            *summary_cells,
            *(("",) * 19),
        )
    )
    for operation in operations:
        csv_writer.writerow(
            (
                "FINANCE_OPERATION",
                *(("",) * 6),
                *(("",) * 15),
                *_finance_operation_cells(operation),
            )
        )
    return output.getvalue().encode("utf-8-sig")
