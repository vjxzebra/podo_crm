import csv
import json
import re
from datetime import timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.billing import exports as billing_exports
from apps.billing.models import (
    CashLedgerEntry,
    CashLedgerEntryKind,
    CashShift,
    PaymentMethod,
)
from config.api.csv import spreadsheet_safe_text


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


def post_cash_movement(
    client: APIClient,
    *,
    kind: str,
    amount_minor: int,
    key: str,
) -> None:
    response = client.post(
        "/api/v1/cash-movements",
        {
            "type": kind,
            "amount_minor": amount_minor,
            "reason": "@Контрольна операція",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.json()


def close_shift(
    client: APIClient,
    shift: CashShift,
    *,
    actual_cash_minor: int,
    expected_operations_count: int,
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
        HTTP_IDEMPOTENCY_KEY="cash-shift-export-close",
    )
    assert response.status_code == 201, response.json()


def csv_rows(response: object) -> list[dict[str, str]]:
    content = response.content.decode("utf-8-sig")
    return list(csv.DictReader(StringIO(content)))


@pytest.mark.django_db(transaction=True)
def test_exact_cash_shift_export_has_safe_summary_first_csv_contract() -> None:
    owner = create_user("owner-export@example.test", first_name="=Марина")
    shift = CashShift.objects.create(employee=owner)
    client = authenticated_client(owner)
    post_cash_movement(
        client,
        kind=CashLedgerEntryKind.DEPOSIT,
        amount_minor=1_000,
        key="cash-shift-export-deposit",
    )
    post_cash_movement(
        client,
        kind=CashLedgerEntryKind.WITHDRAWAL,
        amount_minor=250,
        key="cash-shift-export-withdrawal",
    )
    close_shift(client, shift, actual_cash_minor=700, expected_operations_count=2)
    shift.refresh_from_db()
    audit_count = AuditEvent.objects.count()

    response = client.get(
        f"/api/v1/cash-shifts/{shift.pk}/export",
        HTTP_ACCEPT="text/csv",
    )

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in response.content
    assert response["Content-Type"].startswith("text/csv")
    assert response["Cache-Control"] == "no-store"
    assert response["X-Export-Entry-Count"] == "2"
    assert response["X-Export-Row-Count"] == "3"
    assert re.fullmatch(
        f'attachment; filename="cash-shift-{shift.public_number}-\\d{{8}}-\\d{{6}}\\.csv"',
        response["Content-Disposition"],
    )

    decoded = response.content.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(decoded))
    assert tuple(reader.fieldnames or ()) == billing_exports.CASH_SHIFT_EXPORT_COLUMNS
    rows = list(reader)
    assert [row["row_type"] for row in rows] == [
        "SHIFT_SUMMARY",
        "LEDGER_ENTRY",
        "LEDGER_ENTRY",
    ]
    summary = rows[0]
    assert summary["shift_number"] == shift.public_number
    assert summary["shift_employee_name"] == "'=Марина Коваль"
    assert summary["operations_count"] == "2"
    assert summary["revenue_minor"] == "0"
    assert summary["expected_cash_minor"] == "750"
    assert summary["actual_cash_minor"] == "700"
    assert summary["discrepancy_minor"] == "-50"
    assert summary["close_comment"] == "'@Перераховано повторно"
    assert summary["closed_by_name"] == "'=Марина Коваль"
    assert summary["shift_opened_at_local"] == timezone.localtime(shift.opened_at).isoformat(
        timespec="seconds"
    )
    assert summary["shift_closed_at_local"] == timezone.localtime(shift.closed_at).isoformat(
        timespec="seconds"
    )
    assert [row["entry_kind"] for row in rows[1:]] == [
        CashLedgerEntryKind.WITHDRAWAL,
        CashLedgerEntryKind.DEPOSIT,
    ]
    assert [row["signed_amount_minor"] for row in rows[1:]] == ["-250", "1000"]
    assert all(row["currency"] == "UAH" for row in rows)
    assert "patient" not in decoded.lower()
    assert "service" not in decoded.lower()
    assert AuditEvent.objects.count() == audit_count


@pytest.mark.django_db
def test_empty_cash_shift_export_contains_only_authoritative_summary_row() -> None:
    owner = create_user("empty-export@example.test")
    shift = CashShift.objects.create(employee=owner)

    response = authenticated_client(owner).get(f"/api/v1/cash-shifts/{shift.pk}/export")

    assert response.status_code == 200
    assert response["X-Export-Entry-Count"] == "0"
    assert response["X-Export-Row-Count"] == "1"
    rows = csv_rows(response)
    assert len(rows) == 1
    assert rows[0]["row_type"] == "SHIFT_SUMMARY"
    assert rows[0]["operations_count"] == "0"
    assert rows[0]["actual_cash_minor"] == ""
    assert rows[0]["entry_number"] == ""


@pytest.mark.django_db
def test_cash_shift_export_rejects_partial_file_and_query_parameters(monkeypatch) -> None:
    owner = create_user("bounded-export@example.test")
    shift = CashShift.objects.create(employee=owner)
    client = authenticated_client(owner)
    post_cash_movement(
        client,
        kind=CashLedgerEntryKind.DEPOSIT,
        amount_minor=1_000,
        key="bounded-export-one",
    )
    post_cash_movement(
        client,
        kind=CashLedgerEntryKind.DEPOSIT,
        amount_minor=2_000,
        key="bounded-export-two",
    )
    monkeypatch.setattr(billing_exports, "CASH_SHIFT_EXPORT_ENTRY_LIMIT", 1)

    too_large = client.get(
        f"/api/v1/cash-shifts/{shift.pk}/export",
        HTTP_ACCEPT="text/csv",
    )
    query = client.get(f"/api/v1/cash-shifts/{shift.pk}/export", {"cursor": "unexpected"})

    assert too_large.status_code == 422
    assert json.loads(too_large.content)["code"] == "cash_shift_export_too_large"
    assert "Content-Disposition" not in too_large
    assert query.status_code == 422
    assert query.json()["code"] == "cash_shift_export_query_not_supported"
    assert query.json()["fields"] == {"cursor": ["Приберіть query parameter з exact-shift export."]}


@pytest.mark.django_db
def test_cash_shift_export_matches_existing_object_scope() -> None:
    owner = create_user("scope-owner@example.test")
    foreign = create_user("scope-foreign@example.test")
    admin = create_user("scope-admin@example.test", role=UserRole.ADMIN)
    podologist = create_user("scope-podologist@example.test", role=UserRole.PODOLOGIST)
    shift = CashShift.objects.create(employee=owner)
    path = f"/api/v1/cash-shifts/{shift.pk}/export"

    assert authenticated_client(owner).get(path).status_code == 200
    assert authenticated_client(admin).get(path).status_code == 200
    assert authenticated_client(foreign).get(path).status_code == 404
    assert authenticated_client(podologist).get(path).status_code == 403
    assert APIClient().get(path).status_code == 401
    assert (
        authenticated_client(admin).get(f"/api/v1/cash-shifts/{uuid4()}/export").status_code == 404
    )


@pytest.mark.django_db
def test_renderer_maps_all_ledger_signs_and_payment_methods_without_pii_join() -> None:
    owner = create_user("render-export@example.test")
    shift = CashShift.objects.create(employee=owner)
    posted_at = timezone.now() - timedelta(minutes=5)
    kinds = (
        (CashLedgerEntryKind.PAYMENT, PaymentMethod.CARD, 1200),
        (CashLedgerEntryKind.REFUND, PaymentMethod.CASH, -300),
        (CashLedgerEntryKind.DEPOSIT, "", 500),
        (CashLedgerEntryKind.WITHDRAWAL, "", -100),
    )
    entries = [
        CashLedgerEntry(
            id=uuid4(),
            public_number=f"CSL-EXPORT-{index}",
            cash_shift=shift,
            created_by=owner,
            actor_name_snapshot="  +Касир",
            actor_email_snapshot=owner.email,
            actor_role_snapshot=owner.role,
            kind=kind,
            amount_minor=abs(signed_amount),
            payment_method=method,
            idempotency_key=f"render-export-{index}",
            payload_hash="a" * 64,
            posted_at=posted_at + timedelta(seconds=index),
        )
        for index, (kind, method, signed_amount) in enumerate(kinds)
    ]

    rows = list(
        csv.DictReader(
            StringIO(billing_exports.render_cash_shift_csv(shift, entries).decode("utf-8-sig"))
        )
    )[1:]

    assert [row["entry_kind"] for row in rows] == [item[0] for item in kinds]
    assert [row["payment_method"] for row in rows] == [item[1] for item in kinds]
    assert [row["signed_amount_minor"] for row in rows] == [str(item[2]) for item in kinds]
    assert all(row["actor_name"] == "'  +Касир" for row in rows)
    assert spreadsheet_safe_text("\x00=SUM(1+1)") == "'=SUM(1+1)"
