import csv
import json
import re
from io import StringIO

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.billing import exports as billing_exports
from apps.billing.models import CashLedgerEntryKind, CashShift, PaymentMethod
from config.api.csv import spreadsheet_safe_text
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


def close_shift(
    client: APIClient,
    shift: CashShift,
    *,
    expected_operations_count: int,
    actual_cash_minor: int,
) -> None:
    response = client.post(
        f"/api/v1/cash-shifts/{shift.pk}/close",
        {
            "actual_cash_minor": actual_cash_minor,
            "expected_operations_count": expected_operations_count,
            "cash_count_confirmed": True,
            "comment": "@Перераховано повторно",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"history-export-close-{shift.pk}",
    )
    assert response.status_code == 201, response.json()


@pytest.mark.django_db(transaction=True)
def test_filtered_cash_shift_history_export_has_safe_summary_first_contract() -> None:
    owner = create_user("history-owner@example.test", first_name="=Марина")
    admin = create_user("history-admin@example.test", role=UserRole.ADMIN)
    shift = CashShift.objects.create(employee=owner)
    owner_client = authenticated_client(owner)
    receivable = completed_receivable(
        amount_minor=5_000,
        index=1004,
        patient_first_name="Секретна",
        service_name="Приватна послуга",
    )
    paid = post_full_payment(
        owner_client,
        receivable,
        key="history-export-payment",
        payment_method=PaymentMethod.CASH,
    )
    assert paid.status_code == 201, paid.json()
    refunded = post_refund(
        owner_client,
        paid.json()["operation"]["payment"]["id"],
        key="history-export-refund",
    )
    assert refunded.status_code == 201, refunded.json()
    assert (
        post_movement(
            owner_client,
            movement_type=CashLedgerEntryKind.DEPOSIT,
            amount_minor=1_000,
            key="history-export-deposit",
        ).status_code
        == 201
    )
    assert (
        post_movement(
            owner_client,
            movement_type=CashLedgerEntryKind.WITHDRAWAL,
            amount_minor=250,
            key="history-export-withdrawal",
        ).status_code
        == 201
    )
    close_shift(
        owner_client,
        shift,
        expected_operations_count=4,
        actual_cash_minor=700,
    )
    shift.refresh_from_db()
    newest_open = CashShift.objects.create(employee=owner)
    audit_count = AuditEvent.objects.count()
    today = timezone.localdate().isoformat()

    with CaptureQueriesContext(connection) as queries:
        response = authenticated_client(admin).get(
            "/api/v1/cash-shifts/export",
            {
                "search": "history-owner@",
                "date_from": today,
                "date_to": today,
                "employee_id": owner.pk,
            },
            HTTP_ACCEPT="text/csv",
        )

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in response.content
    assert response["Content-Type"].startswith("text/csv")
    assert response["Cache-Control"] == "no-store"
    assert response["X-Export-Shift-Count"] == "2"
    assert response["X-Export-Row-Count"] == "3"
    assert re.fullmatch(
        'attachment; filename="cash-shift-history-\\d{8}-\\d{6}\\.csv"',
        response["Content-Disposition"],
    )
    decoded = response.content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(decoded))
    assert tuple(reader.fieldnames or ()) == billing_exports.CASH_SHIFT_HISTORY_EXPORT_COLUMNS
    rows = list(reader)
    assert [row["row_type"] for row in rows] == [
        "REPORT_SUMMARY",
        "CASH_SHIFT",
        "CASH_SHIFT",
    ]
    report, open_row, closed_row = rows
    assert report["shift_count"] == "2"
    assert report["open_shift_count"] == "1"
    assert report["closed_shift_count"] == "1"
    assert report["operations_count"] == "4"
    assert report["payment_count"] == "1"
    assert report["refund_count"] == "1"
    assert report["payments_total_minor"] == "5000"
    assert report["refunds_total_minor"] == "5000"
    assert report["revenue_minor"] == "0"
    assert report["cash_net_minor"] == "0"
    assert report["deposits_minor"] == "1000"
    assert report["withdrawals_minor"] == "250"
    assert report["expected_cash_minor"] == "750"
    assert report["actual_cash_minor"] == "700"
    assert report["discrepancy_minor"] == "-50"
    assert open_row["shift_number"] == newest_open.public_number
    assert open_row["actual_cash_minor"] == ""
    assert closed_row["shift_number"] == shift.public_number
    assert closed_row["employee_name"] == "'=Марина Коваль"
    assert closed_row["opened_at_local"] == timezone.localtime(shift.opened_at).isoformat(
        timespec="seconds"
    )
    assert closed_row["closed_at_local"] == timezone.localtime(shift.closed_at).isoformat(
        timespec="seconds"
    )
    assert closed_row["close_comment"] == "'@Перераховано повторно"
    assert closed_row["closed_by_name"] == "'=Марина Коваль"
    assert all(row["currency"] == "UAH" for row in rows)
    assert "Секретна" not in decoded
    assert "Приватна послуга" not in decoded
    sql = " ".join(query["sql"].lower() for query in queries.captured_queries)
    assert "patients_patient" not in sql
    assert "visits_visit" not in sql
    assert "clinic_service" not in sql
    assert "billing_payment" not in sql
    assert "billing_refund" not in sql
    assert AuditEvent.objects.count() == audit_count


@pytest.mark.django_db
def test_empty_cash_shift_history_export_contains_zero_report_summary() -> None:
    admin = create_user("empty-history@example.test", role=UserRole.ADMIN)

    response = authenticated_client(admin).get(
        "/api/v1/cash-shifts/export",
        {"search": "missing-shift"},
    )

    assert response.status_code == 200
    assert response["X-Export-Shift-Count"] == "0"
    assert response["X-Export-Row-Count"] == "1"
    rows = csv_rows(response)
    assert len(rows) == 1
    assert rows[0]["row_type"] == "REPORT_SUMMARY"
    assert rows[0]["shift_count"] == "0"
    assert rows[0]["operations_count"] == "0"
    assert rows[0]["actual_cash_minor"] == "0"


@pytest.mark.django_db
def test_cash_shift_history_export_rejects_bounds_and_partial_file(monkeypatch) -> None:
    admin = create_user("bounded-history@example.test", role=UserRole.ADMIN)
    CashShift.objects.create(employee=create_user("bounded-one@example.test"))
    CashShift.objects.create(employee=create_user("bounded-two@example.test"))
    monkeypatch.setattr(billing_exports, "CASH_SHIFT_HISTORY_EXPORT_ROW_LIMIT", 1)
    client = authenticated_client(admin)

    too_large = client.get("/api/v1/cash-shifts/export", HTTP_ACCEPT="text/csv")
    too_wide = client.get(
        "/api/v1/cash-shifts/export",
        {"date_from": "2025-01-01", "date_to": "2026-01-02"},
    )
    inverted = client.get(
        "/api/v1/cash-shifts/export",
        {"date_from": "2026-07-23", "date_to": "2026-07-22"},
    )
    cursor = client.get("/api/v1/cash-shifts/export", {"cursor": "opaque"})

    assert too_large.status_code == 422
    assert json.loads(too_large.content)["code"] == "cash_shift_history_export_too_large"
    assert "Content-Disposition" not in too_large
    assert too_wide.status_code == 422
    assert "366" in too_wide.json()["fields"]["date_to"][0]
    assert inverted.status_code == 422
    assert cursor.status_code == 422
    assert cursor.json()["code"] == "cash_shift_history_export_cursor_not_supported"


@pytest.mark.django_db
def test_cash_shift_history_export_matches_list_scope_and_employee_filter() -> None:
    owner = create_user("history-scope-owner@example.test")
    foreign = create_user("history-scope-foreign@example.test")
    admin = create_user("history-scope-admin@example.test", role=UserRole.ADMIN)
    podologist = create_user(
        "history-scope-podologist@example.test",
        role=UserRole.PODOLOGIST,
    )
    own_shift = CashShift.objects.create(employee=owner)
    foreign_shift = CashShift.objects.create(employee=foreign)
    path = "/api/v1/cash-shifts/export"

    owner_response = authenticated_client(owner).get(path)
    admin_response = authenticated_client(admin).get(path, {"employee_id": foreign.pk})

    assert owner_response.status_code == 200
    assert [row["shift_number"] for row in csv_rows(owner_response)[1:]] == [
        own_shift.public_number
    ]
    assert admin_response.status_code == 200
    assert [row["shift_number"] for row in csv_rows(admin_response)[1:]] == [
        foreign_shift.public_number
    ]
    assert authenticated_client(owner).get(path, {"employee_id": owner.pk}).status_code == 403
    assert authenticated_client(podologist).get(path).status_code == 403
    assert APIClient().get(path).status_code == 401


def test_cash_shift_history_csv_sanitizer_removes_nul() -> None:
    assert spreadsheet_safe_text("\x00=SUM(1+1)") == "'=SUM(1+1)"
