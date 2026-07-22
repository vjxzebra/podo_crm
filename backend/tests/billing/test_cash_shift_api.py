from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connections
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction, AuditSection
from apps.billing.models import (
    CashLedgerEntry,
    CashLedgerEntryKind,
    CashShift,
    PaymentMethod,
)
from tests.billing.test_payments_api import (
    completed_receivable,
)
from tests.billing.test_payments_api import (
    post_payment as post_full_payment,
)


def create_user(
    *,
    email: str,
    role: str,
    first_name: str = "Марина",
    last_name: str = "Бойко",
) -> User:
    return User.objects.create_user(
        email=email,
        password=None,
        role=role,
        first_name=first_name,
        last_name=last_name,
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def post_open(client: APIClient):
    return client.post("/api/v1/cash-shifts", format="json")


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.RECEPTION, UserRole.ADMIN])
def test_current_cash_shift_returns_explicit_null_when_actor_has_no_open_shift(role: str) -> None:
    actor = create_user(email=f"{role}@example.test", role=role)

    response = authenticated_client(actor).get("/api/v1/cash-shifts/current")

    assert response.status_code == 200
    assert response.json() == {"shift": None}


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.RECEPTION, UserRole.ADMIN])
def test_open_shift_returns_zero_projection_and_writes_same_transaction_audit(role: str) -> None:
    actor = create_user(email=f"{role}-open@example.test", role=role)
    client = authenticated_client(actor)

    response = client.post(
        "/api/v1/cash-shifts",
        format="json",
        HTTP_X_REQUEST_ID="tp701-open-shift",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["public_number"].startswith("CSH-")
    assert body["status"] == "OPEN"
    assert body["closed_at"] is None
    assert body["reconciliation"] is None
    assert body["employee"] == {
        "id": actor.pk,
        "name": "Марина Бойко",
        "email": actor.email,
        "role": role,
    }
    assert body["entries"] == []
    assert body["totals"] == {
        "operations_count": 0,
        "payment_count": 0,
        "refund_count": 0,
        "payments_total_minor": 0,
        "refunds_total_minor": 0,
        "revenue_minor": 0,
        "cash_payments_minor": 0,
        "cash_refunds_minor": 0,
        "card_payments_minor": 0,
        "card_refunds_minor": 0,
        "transfer_payments_minor": 0,
        "transfer_refunds_minor": 0,
        "deposits_minor": 0,
        "withdrawals_minor": 0,
        "expected_cash_minor": 0,
    }
    current = client.get("/api/v1/cash-shifts/current")
    assert current.status_code == 200
    assert current.json()["shift"] == body

    shift = CashShift.objects.get()
    event = AuditEvent.objects.get(action=AuditAction.CASH_SHIFT_OPENED)
    assert event.section == AuditSection.CASH
    assert event.actor == actor
    assert event.object_id == str(shift.pk)
    assert event.object_label == shift.public_number
    assert event.correlation_id == "tp701-open-shift"
    assert event.before == {}
    assert event.after["id"] == str(shift.pk)
    assert event.after["employee_id"] == actor.pk
    assert event.after["status"] == "OPEN"


@pytest.mark.django_db
def test_duplicate_open_returns_stable_conflict_without_second_shift_or_audit() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    client = authenticated_client(actor)

    first = post_open(client)
    duplicate = post_open(client)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "cash_shift_already_open"
    assert CashShift.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.CASH_SHIFT_OPENED).count() == 1


@pytest.mark.django_db
def test_current_shift_is_always_actor_owned_for_reception_and_admin() -> None:
    reception = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    other = create_user(email="other@example.test", role=UserRole.RECEPTION)
    admin = create_user(email="admin@example.test", role=UserRole.ADMIN)

    reception_body = post_open(authenticated_client(reception)).json()
    other_body = post_open(authenticated_client(other)).json()

    reception_current = (
        authenticated_client(reception).get("/api/v1/cash-shifts/current").json()["shift"]
    )
    admin_current = authenticated_client(admin).get("/api/v1/cash-shifts/current").json()["shift"]

    assert reception_current["id"] == reception_body["id"]
    assert reception_current["id"] != other_body["id"]
    assert admin_current is None


@pytest.mark.django_db(transaction=True)
def test_current_projection_is_ledger_derived_with_explicit_method_totals_and_order() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    client = authenticated_client(actor)
    assert post_open(client).status_code == 201
    created = []
    for index, (amount, method) in enumerate(
        (
            (1_000, PaymentMethod.CASH),
            (2_000, PaymentMethod.CARD),
            (3_000, PaymentMethod.TRANSFER),
        ),
        start=1,
    ):
        receivable = completed_receivable(amount_minor=amount, index=index)
        paid = post_full_payment(
            client,
            receivable,
            key=f"projection-payment-{index}",
            payment_method=method,
        )
        assert paid.status_code == 201, paid.json()
        payment_id = paid.json()["operation"]["payment"]["id"]
        created.append(
            CashLedgerEntry.objects.get(pk=paid.json()["operation"]["payment"]["ledger_entry_id"])
        )
        refunded = client.post(
            f"/api/v1/payments/{payment_id}/refunds",
            {"reason": "Тестове повне повернення"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"projection-refund-{index}",
        )
        assert refunded.status_code == 201, refunded.json()
        created.append(
            CashLedgerEntry.objects.get(
                pk=refunded.json()["operation"]["refund"]["ledger_entry_id"]
            )
        )
    for index, (movement_type, amount) in enumerate(
        ((CashLedgerEntryKind.DEPOSIT, 500), (CashLedgerEntryKind.WITHDRAWAL, 100)),
        start=1,
    ):
        movement = client.post(
            "/api/v1/cash-movements",
            {
                "type": movement_type,
                "amount_minor": amount,
                "reason": "Тестовий рух",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"projection-movement-{index}",
        )
        assert movement.status_code == 201, movement.json()
        created.append(
            CashLedgerEntry.objects.get(
                pk=movement.json()["operation"]["cash_adjustment"]["ledger_entry_id"]
            )
        )

    response = client.get("/api/v1/cash-shifts/current")

    assert response.status_code == 200
    body = response.json()["shift"]
    assert body["totals"] == {
        "operations_count": 8,
        "payment_count": 3,
        "refund_count": 3,
        "payments_total_minor": 6_000,
        "refunds_total_minor": 6_000,
        "revenue_minor": 0,
        "cash_payments_minor": 1_000,
        "cash_refunds_minor": 1_000,
        "card_payments_minor": 2_000,
        "card_refunds_minor": 2_000,
        "transfer_payments_minor": 3_000,
        "transfer_refunds_minor": 3_000,
        "deposits_minor": 500,
        "withdrawals_minor": 100,
        "expected_cash_minor": 400,
    }
    assert [item["id"] for item in body["entries"]] == [
        str(entry.pk) for entry in reversed(created)
    ]
    assert body["entries"][0]["actor_id"] == actor.pk
    assert body["entries"][0]["actor_name"] == actor.display_name
    assert body["entries"][0]["actor_email"] == actor.email
    assert body["entries"][0]["public_number"].startswith("TXN-")


@pytest.mark.django_db
def test_cash_shift_endpoints_enforce_role_and_authentication() -> None:
    podologist = create_user(email="podologist@example.test", role=UserRole.PODOLOGIST)
    podologist_client = authenticated_client(podologist)
    anonymous = APIClient()

    assert podologist_client.get("/api/v1/cash-shifts/current").status_code == 403
    assert post_open(podologist_client).status_code == 403
    assert anonymous.get("/api/v1/cash-shifts/current").status_code == 401
    assert post_open(anonymous).status_code == 401
    assert not CashShift.objects.exists()


@pytest.mark.django_db
def test_open_shift_rolls_back_if_audit_write_fails() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)

    with patch(
        "apps.billing.services.record_audit_event",
        side_effect=RuntimeError("audit down"),
    ):
        response = post_open(authenticated_client(actor))

    assert response.status_code == 500
    assert not CashShift.objects.exists()
    assert not AuditEvent.objects.filter(action=AuditAction.CASH_SHIFT_OPENED).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_open_creates_exactly_one_shift_and_audit() -> None:
    actor = create_user(email="reception@example.test", role=UserRole.RECEPTION)
    barrier = Barrier(2)

    def submit(_: int) -> tuple[int, str]:
        close_old_connections()
        request_actor = User.objects.get(pk=actor.pk)
        barrier.wait(timeout=5)
        try:
            response = post_open(authenticated_client(request_actor))
            return response.status_code, response.json().get("code", "created")
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, range(2)))

    assert sorted(code for code, _ in results) == [201, 409]
    assert {result for _, result in results} == {"created", "cash_shift_already_open"}
    assert CashShift.objects.count() == 1
    assert AuditEvent.objects.filter(action=AuditAction.CASH_SHIFT_OPENED).count() == 1


@pytest.mark.django_db
def test_openapi_freezes_cash_shift_component_names_and_contract() -> None:
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    components = schema["components"]["schemas"]
    open_operation = paths["/api/v1/cash-shifts"]["post"]
    current_operation = paths["/api/v1/cash-shifts/current"]["get"]

    assert "requestBody" not in open_operation
    assert open_operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CashShiftProjection"
    }
    assert current_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CashShiftCurrentResponse"
    }
    assert {
        "CashLedgerEntry",
        "CashShiftEmployee",
        "CashShiftTotals",
        "CashShiftProjection",
        "CashShiftCurrentResponse",
    }.issubset(components)
    assert set(components["CashLedgerEntry"]["required"]) == {
        "id",
        "public_number",
        "kind",
        "amount_minor",
        "payment_method",
        "actor_id",
        "actor_name",
        "actor_email",
        "posted_at",
    }
    assert set(components["CashLedgerEntry"]["properties"]) == set(
        components["CashLedgerEntry"]["required"]
    )
    assert set(components["CashShiftTotals"]["required"]) == {
        "operations_count",
        "payment_count",
        "refund_count",
        "payments_total_minor",
        "refunds_total_minor",
        "revenue_minor",
        "cash_payments_minor",
        "cash_refunds_minor",
        "card_payments_minor",
        "card_refunds_minor",
        "transfer_payments_minor",
        "transfer_refunds_minor",
        "deposits_minor",
        "withdrawals_minor",
        "expected_cash_minor",
    }
    assert set(components["CashShiftEmployee"]["required"]) == {
        "id",
        "name",
        "email",
        "role",
    }
    assert set(components["CashShiftEmployee"]["properties"]) == set(
        components["CashShiftEmployee"]["required"]
    )
    assert set(components["CashShiftProjection"]["required"]) == {
        "id",
        "public_number",
        "status",
        "employee",
        "opened_at",
        "closed_at",
        "totals",
        "reconciliation",
        "entries",
    }
    assert set(components["CashShiftProjection"]["properties"]) == set(
        components["CashShiftProjection"]["required"]
    )
    assert components["CashShiftEmployee"]["properties"]["id"]["type"] == "integer"
    assert components["CashLedgerEntry"]["properties"]["actor_id"]["type"] == "integer"
    assert components["CashLedgerEntry"]["properties"]["payment_method"]["nullable"] is True
    assert set(components["CashShiftCurrentResponse"]["required"]) == {"shift"}
    assert set(components["CashShiftCurrentResponse"]["properties"]) == {"shift"}
    assert components["CashShiftCurrentResponse"]["properties"]["shift"]["nullable"] is True
    assert not any(
        parameter.get("in") == "header" and parameter.get("name") == "Idempotency-Key"
        for parameter in open_operation.get("parameters", [])
    )
