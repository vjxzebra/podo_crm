import csv
import json
import re
from io import StringIO
from uuid import UUID

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.billing import exports as billing_exports
from apps.billing.models import CashLedgerEntryKind, CashShift, PaymentMethod
from tests.billing.test_payments_api import completed_receivable
from tests.billing.test_payments_api import post_payment as post_full_payment
from tests.billing.test_refunds_and_cash_movements_api import post_movement, post_refund


def create_user(
    email: str,
    *,
    role: str = UserRole.RECEPTION,
    first_name: str = "Марина",
) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=role,
        first_name=first_name,
        last_name="Коваль",
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def csv_rows(response: object) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))


def operation_number(operation: dict[str, object]) -> str:
    operation_type = operation["type"]
    if operation_type == CashLedgerEntryKind.PAYMENT:
        payment = operation["payment"]
        if isinstance(payment, dict):
            return str(payment["public_number"])
        return str(operation["visit"]["public_number"])
    if operation_type == CashLedgerEntryKind.REFUND:
        return str(operation["refund"]["public_number"])
    return str(operation["cash_adjustment"]["public_number"])


@pytest.mark.django_db(transaction=True)
def test_finance_operation_export_reconciles_safe_summary_and_list_order() -> None:
    actor = create_user("finance-export-actor@example.test", first_name="@Марина")
    admin = create_user("finance-export-admin@example.test", role=UserRole.ADMIN)
    CashShift.objects.create(employee=actor)
    actor_client = authenticated_client(actor)
    open_receivable = completed_receivable(
        amount_minor=7_000,
        index=10060,
        patient_first_name="Відкрита",
        patient_last_name="Пацієнтка",
    )
    refunded_receivable = completed_receivable(
        amount_minor=5_000,
        index=10061,
        patient_first_name="=Секретна",
        patient_last_name="Пацієнтка",
        service_name="+Приватна послуга",
    )
    paid = post_full_payment(
        actor_client,
        refunded_receivable,
        key="finance-export-payment",
        payment_method=PaymentMethod.CASH,
        comment="@Повна оплата",
    )
    assert paid.status_code == 201, paid.json()
    refunded = post_refund(
        actor_client,
        paid.json()["operation"]["payment"]["id"],
        key="finance-export-refund",
        reason="=Помилкова оплата",
    )
    assert refunded.status_code == 201, refunded.json()
    assert (
        post_movement(
            actor_client,
            movement_type=CashLedgerEntryKind.DEPOSIT,
            amount_minor=1_200,
            key="finance-export-deposit",
            reason="+Розмін",
            comment="@Сейф",
        ).status_code
        == 201
    )
    assert (
        post_movement(
            actor_client,
            movement_type=CashLedgerEntryKind.WITHDRAWAL,
            amount_minor=300,
            key="finance-export-withdrawal",
            reason="-Інкасація",
        ).status_code
        == 201
    )
    audit_count = AuditEvent.objects.count()
    client = authenticated_client(admin)
    listed = client.get("/api/v1/finance/operations").json()["operations"]

    response = client.get(
        "/api/v1/finance/operations/export",
        HTTP_ACCEPT="text/csv",
    )

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in response.content
    assert response["Content-Type"].startswith("text/csv")
    assert response["Cache-Control"] == "no-store"
    assert response["X-Export-Operation-Count"] == "5"
    assert response["X-Export-Row-Count"] == "6"
    assert re.fullmatch(
        'attachment; filename="finance-operations-\\d{8}-\\d{6}\\.csv"',
        response["Content-Disposition"],
    )
    decoded = response.content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(decoded))
    assert tuple(reader.fieldnames or ()) == billing_exports.FINANCE_OPERATION_EXPORT_COLUMNS
    rows = list(reader)
    assert rows[0]["row_type"] == "REPORT_SUMMARY"
    assert all(row["row_type"] == "FINANCE_OPERATION" for row in rows[1:])
    assert [row["operation_number"] for row in rows[1:]] == [
        operation_number(operation) for operation in listed
    ]
    summary = rows[0]
    assert summary["operation_count"] == "5"
    assert summary["payment_count"] == "2"
    assert summary["refund_count"] == "1"
    assert summary["deposit_count"] == "1"
    assert summary["withdrawal_count"] == "1"
    assert summary["open_count"] == "1"
    assert summary["refunded_count"] == "1"
    assert summary["posted_count"] == "3"
    assert summary["outstanding_minor"] == "7000"
    assert summary["payments_minor"] == "5000"
    assert summary["refunds_minor"] == "5000"
    assert summary["deposits_minor"] == "1200"
    assert summary["withdrawals_minor"] == "300"
    assert summary["net_posted_minor"] == "900"
    payment_row = next(
        row
        for row in rows[1:]
        if row["operation_type"] == "PAYMENT" and row["operation_status"] == "REFUNDED"
    )
    refund_row = next(row for row in rows[1:] if row["operation_type"] == "REFUND")
    deposit_row = next(row for row in rows[1:] if row["operation_type"] == "DEPOSIT")
    assert payment_row["patient_name"] == "'=Секретна Пацієнтка"
    assert payment_row["services"].startswith("PAY-10061-")
    assert "+Приватна послуга" in payment_row["services"]
    assert payment_row["comment"] == "'@Повна оплата"
    assert payment_row["cash_effect_minor"] == "5000"
    assert refund_row["reason"] == "'=Помилкова оплата"
    assert refund_row["cash_effect_minor"] == "-5000"
    assert refund_row["original_payment_number"] == payment_row["operation_number"]
    assert deposit_row["reason"] == "'+Розмін"
    assert deposit_row["comment"] == "'@Сейф"
    assert deposit_row["patient_name"] == ""
    assert deposit_row["cash_effect_minor"] == "1200"
    assert open_receivable.visit.patient.phone not in decoded
    assert refunded_receivable.visit.patient.phone not in decoded
    internal_ids = {str(operation["id"]) for operation in listed if UUID(str(operation["id"]))}
    internal_ids.add(str(paid.json()["operation"]["payment"]["ledger_entry_id"]))
    assert not any(internal_id in decoded for internal_id in internal_ids)
    assert "ledger_entry_id" not in decoded
    assert "patient_phone" not in decoded
    assert AuditEvent.objects.count() == audit_count


@pytest.mark.django_db
def test_finance_operation_export_applies_only_six_main_list_filters() -> None:
    actor = create_user("finance-filter-actor@example.test")
    admin = create_user("finance-filter-admin@example.test", role=UserRole.ADMIN)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable(
        amount_minor=8_500,
        index=10062,
        patient_first_name="Фільтрована",
        patient_last_name="Пацієнтка",
    )
    paid = post_full_payment(
        authenticated_client(actor),
        receivable,
        key="finance-filter-payment",
        payment_method=PaymentMethod.CARD,
    )
    assert paid.status_code == 201, paid.json()
    today = timezone.localdate().isoformat()
    query = {
        "search": "Фільтрована",
        "type": "PAYMENT",
        "status": "PAID",
        "payment_method": "CARD",
        "date_from": today,
        "date_to": today,
    }
    client = authenticated_client(admin)
    listed = client.get("/api/v1/finance/operations", query).json()["operations"]

    response = client.get("/api/v1/finance/operations/export", query)

    assert response.status_code == 200
    rows = csv_rows(response)
    assert len(rows) == 2
    assert rows[0]["filter_search"] == "Фільтрована"
    assert rows[0]["filter_type"] == "PAYMENT"
    assert rows[0]["filter_status"] == "PAID"
    assert rows[0]["filter_payment_method"] == "CARD"
    assert rows[0]["filter_date_from"] == today
    assert rows[0]["filter_date_to"] == today
    assert [row["operation_number"] for row in rows[1:]] == [
        operation_number(operation) for operation in listed
    ]


@pytest.mark.django_db
def test_empty_finance_operation_export_contains_zero_report_summary() -> None:
    admin = create_user("finance-empty-admin@example.test", role=UserRole.ADMIN)

    response = authenticated_client(admin).get(
        "/api/v1/finance/operations/export",
        {"search": "missing-operation"},
    )

    assert response.status_code == 200
    assert response["X-Export-Operation-Count"] == "0"
    assert response["X-Export-Row-Count"] == "1"
    rows = csv_rows(response)
    assert len(rows) == 1
    assert rows[0]["row_type"] == "REPORT_SUMMARY"
    assert rows[0]["operation_count"] == "0"
    assert rows[0]["net_posted_minor"] == "0"


@pytest.mark.django_db
def test_finance_operation_export_is_admin_only_and_rejects_unsupported_bounds() -> None:
    admin = create_user("finance-scope-admin@example.test", role=UserRole.ADMIN)
    reception = create_user("finance-scope-reception@example.test")
    podologist = create_user(
        "finance-scope-podologist@example.test",
        role=UserRole.PODOLOGIST,
    )
    path = "/api/v1/finance/operations/export"
    client = authenticated_client(admin)

    too_wide = client.get(path, {"date_from": "2025-01-01", "date_to": "2026-01-02"})
    inverted = client.get(path, {"date_from": "2026-07-23", "date_to": "2026-07-22"})
    cursor = client.get(path, {"cursor": "opaque"})
    hidden_filter = client.get(path, {"patient_id": "8c0a7ab4-55d5-4be5-887d-405708fd1a5d"})

    assert too_wide.status_code == 422
    assert "366" in too_wide.json()["fields"]["date_to"][0]
    assert inverted.status_code == 422
    assert cursor.status_code == 422
    assert cursor.json()["code"] == "finance_operation_export_query_not_supported"
    assert hidden_filter.status_code == 422
    assert hidden_filter.json()["code"] == "finance_operation_export_query_not_supported"
    assert authenticated_client(reception).get(path).status_code == 403
    assert authenticated_client(podologist).get(path).status_code == 403
    assert APIClient().get(path).status_code == 401


@pytest.mark.django_db
def test_finance_operation_export_rejects_limit_without_partial_file(monkeypatch) -> None:
    admin = create_user("finance-limit-admin@example.test", role=UserRole.ADMIN)
    completed_receivable(index=10063)
    completed_receivable(index=10064)
    monkeypatch.setattr(billing_exports, "FINANCE_OPERATION_EXPORT_ROW_LIMIT", 1)

    response = authenticated_client(admin).get("/api/v1/finance/operations/export")

    assert response.status_code == 422
    assert json.loads(response.content)["code"] == "finance_operation_export_too_large"
    assert "Content-Disposition" not in response


def test_finance_operation_csv_sanitizes_nul_before_formula() -> None:
    now = timezone.now()
    content = billing_exports.render_finance_operations_csv(
        [
            {
                "id": "ignored",
                "type": "DEPOSIT",
                "status": "POSTED",
                "occurred_at": now,
                "amount_minor": 100,
                "cash_adjustment": {
                    "public_number": "CA-1",
                    "reason": "\x00=SUM(1+1)",
                    "comment": "\x00@hidden",
                    "actor": {"name": "\x00+Actor"},
                    "cash_shift": {"public_number": "CS-1"},
                },
            }
        ],
        {},
    )

    row = list(csv.DictReader(StringIO(content.decode("utf-8-sig"))))[1]
    assert row["reason"] == "'=SUM(1+1)"
    assert row["comment"] == "'@hidden"
    assert row["actor_name"] == "'+Actor"
