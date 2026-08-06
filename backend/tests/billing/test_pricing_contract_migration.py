from typing import Any
from uuid import UUID, uuid4

import pytest
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.billing.models import CashDrawer, CashShift, Payment, VisitPricing
from apps.clinic.models import Service
from apps.discounts.models import PatientLoyaltyState, VisitLoyaltyEvent
from tests.billing.test_payments_api import completed_receivable
from tests.visits.test_loyalty_pricing import _additional_arrived
from tests.visits.test_visit_start_and_draft import (
    arrived_appointment,
    authenticated_client,
    create_user,
    start,
)

MIGRATION_OLD = [
    ("billing", "0008_cash_drawer_contract"),
    ("discounts", "0001_initial"),
]
MIGRATION_EXPANDED = [
    ("billing", "0009_pricing_expand"),
    ("discounts", "0001_initial"),
]
MIGRATION_LATEST = [("billing", "0010_pricing_contract")]


def _started_visits(*, actor: User, amounts: list[int]) -> list[UUID]:
    first = arrived_appointment(actor=actor)
    appointments = [first]
    appointments.extend(
        _additional_arrived(actor=actor, source=first, day_offset=index)
        for index in range(1, len(amounts))
    )
    visit_ids: list[UUID] = []
    for appointment, amount_minor in zip(appointments, amounts, strict=True):
        Service.objects.filter(pk=appointment.service_id).update(price_minor=amount_minor)
        response = start(authenticated_client(actor), appointment)
        assert response.status_code == 201, response.json()
        visit_ids.append(UUID(response.json()["id"]))
    return visit_ids


def _cash_shift(*, actor: User) -> CashShift:
    CashDrawer.objects.get_or_create(key=CashDrawer.MAIN_KEY)
    return CashShift.objects.create(employee=actor)


def _legacy_billing_fact(
    apps: Any,
    *,
    visit_id: UUID,
    status: str,
    actor: User,
    shift_id: UUID | None,
) -> dict[str, Any]:
    HistoricalVisit = apps.get_model("visits", "Visit")
    HistoricalLine = apps.get_model("visits", "VisitServiceLine")
    HistoricalReceivable = apps.get_model("billing", "Receivable")
    HistoricalLedger = apps.get_model("billing", "CashLedgerEntry")
    HistoricalPayment = apps.get_model("billing", "Payment")
    HistoricalRefund = apps.get_model("billing", "Refund")

    visit = HistoricalVisit.objects.get(pk=visit_id)
    line = HistoricalLine.objects.get(visit_id=visit_id)
    amount_minor = line.price_minor * line.quantity
    completed_at = timezone.now()
    receivable_id = uuid4()
    payment_id = None
    refund_id = None

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = replica")
        HistoricalVisit.objects.filter(pk=visit_id).update(
            status="COMPLETED",
            total_minor=amount_minor,
            payment_handoff_requested=True,
            completed_at=completed_at,
            updated_at=completed_at,
        )
        receivable = HistoricalReceivable.objects.create(
            id=receivable_id,
            visit_id=visit_id,
            amount_minor=amount_minor,
            status=status,
        )
        if status in {"PAID", "REFUNDED"}:
            assert shift_id is not None
            ledger_id = uuid4()
            ledger = HistoricalLedger.objects.create(
                id=ledger_id,
                public_number=f"TXN-{ledger_id.hex[:12].upper()}",
                cash_shift_id=shift_id,
                created_by_id=actor.pk,
                kind="PAYMENT",
                amount_minor=amount_minor,
                payment_method="CARD",
                idempotency_key=f"legacy-payment-{visit_id}",
                payload_hash="a" * 64,
                actor_name_snapshot=actor.display_name,
                actor_email_snapshot=actor.email,
                actor_role_snapshot=actor.role,
            )
            patient = visit.patient
            specialist = visit.specialist
            payment_id = uuid4()
            payment = HistoricalPayment.objects.create(
                id=payment_id,
                ledger_entry=ledger,
                receivable=receivable,
                comment="Legacy payment",
                patient_id_snapshot=patient.pk,
                patient_public_number_snapshot=patient.public_number,
                patient_name_snapshot=(f"{patient.first_name} {patient.last_name}".strip()),
                patient_phone_snapshot=patient.phone,
                visit_public_number_snapshot=visit.public_number,
                visit_completed_at_snapshot=completed_at,
                visit_payment_handoff_requested_snapshot=True,
                visit_total_minor_snapshot=amount_minor,
                specialist_id_snapshot=specialist.pk,
                specialist_name_snapshot=(
                    f"{specialist.first_name} {specialist.last_name}".strip() or specialist.email
                ),
                employee_name_snapshot=actor.display_name,
                employee_email_snapshot=actor.email,
                services_snapshot=[
                    {
                        "id": str(line.pk),
                        "code": line.service_code,
                        "name": line.service_name,
                        "quantity": line.quantity,
                        "unit_price_minor": line.price_minor,
                        "line_total_minor": amount_minor,
                    }
                ],
                services_search_snapshot=f"{line.service_code} {line.service_name}",
            )
            if status == "REFUNDED":
                refund_ledger_id = uuid4()
                refund_ledger = HistoricalLedger.objects.create(
                    id=refund_ledger_id,
                    public_number=f"TXN-{refund_ledger_id.hex[:12].upper()}",
                    cash_shift_id=shift_id,
                    created_by_id=actor.pk,
                    kind="REFUND",
                    amount_minor=amount_minor,
                    payment_method="CARD",
                    idempotency_key=f"legacy-refund-{visit_id}",
                    payload_hash="b" * 64,
                    actor_name_snapshot=actor.display_name,
                    actor_email_snapshot=actor.email,
                    actor_role_snapshot=actor.role,
                )
                refund_id = uuid4()
                HistoricalRefund.objects.create(
                    id=refund_id,
                    ledger_entry=refund_ledger,
                    original_payment=payment,
                    reason="Legacy refund",
                    employee_name_snapshot=actor.display_name,
                    employee_email_snapshot=actor.email,
                )

    return {
        "visit_id": visit_id,
        "receivable_id": receivable_id,
        "payment_id": payment_id,
        "refund_id": refund_id,
        "amount_minor": amount_minor,
        "status": status,
    }


def _assert_neutral_pricing(pricing: Any, fact: dict[str, Any]) -> None:
    assert pricing.visit_id == fact["visit_id"]
    assert pricing.gross_minor == fact["amount_minor"]
    assert pricing.discount_id is None
    assert pricing.discount_name_snapshot == ""
    assert pricing.discount_percent_snapshot is None
    assert pricing.discount_source == ""
    assert pricing.applied_by_id is None
    assert pricing.discount_amount_minor == 0
    assert pricing.net_minor == fact["amount_minor"]
    assert pricing.is_legacy_backfill is True
    assert pricing.version == 1
    assert pricing.state == ("OPEN" if fact["status"] == "OPEN" else "SETTLED")
    assert (pricing.settled_at is None) is (fact["status"] == "OPEN")


@pytest.mark.django_db(transaction=True)
def test_pricing_expand_contract_backfills_legacy_rows_and_safe_reverse_reapplies() -> None:
    admin = create_user(email="pricing-migration-admin@example.test", role=UserRole.ADMIN)
    reception = create_user(
        email="pricing-migration-reception@example.test",
        role=UserRole.RECEPTION,
    )
    shift = _cash_shift(actor=reception)
    visit_ids = _started_visits(actor=admin, amounts=[11_000, 22_000, 33_000, 44_000])
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_OLD)
    try:
        old_apps = executor.loader.project_state(MIGRATION_OLD).apps
        facts = [
            _legacy_billing_fact(
                old_apps,
                visit_id=visit_id,
                status=status,
                actor=reception,
                shift_id=shift.pk,
            )
            for visit_id, status in zip(
                visit_ids[:3],
                ["OPEN", "PAID", "REFUNDED"],
                strict=True,
            )
        ]

        executor = MigrationExecutor(connection)
        executor.migrate(MIGRATION_EXPANDED)
        expanded_apps = executor.loader.project_state(MIGRATION_EXPANDED).apps
        ExpandedPricing = expanded_apps.get_model("billing", "VisitPricing")
        ExpandedPayment = expanded_apps.get_model("billing", "Payment")
        assert ExpandedPricing.objects.count() == 3
        for fact in facts:
            _assert_neutral_pricing(
                ExpandedPricing.objects.get(visit_id=fact["visit_id"]),
                fact,
            )
        for fact in facts:
            if fact["payment_id"] is None:
                continue
            payment = ExpandedPayment.objects.get(pk=fact["payment_id"])
            assert payment.gross_total_minor_snapshot == fact["amount_minor"]
            assert payment.discount_id_snapshot is None
            assert payment.discount_name_snapshot == ""
            assert payment.discount_percent_snapshot is None
            assert payment.discount_source_snapshot == ""
            assert payment.discount_amount_minor_snapshot == 0
            assert payment.net_total_minor_snapshot == fact["amount_minor"]
            assert payment.pricing_snapshot_is_legacy is True

        bridge_fact = _legacy_billing_fact(
            expanded_apps,
            visit_id=visit_ids[3],
            status="PAID",
            actor=reception,
            shift_id=shift.pk,
        )
        assert not ExpandedPricing.objects.filter(visit_id=visit_ids[3]).exists()
        assert (
            ExpandedPayment.objects.get(pk=bridge_fact["payment_id"]).gross_total_minor_snapshot
            is None
        )
        facts.append(bridge_fact)

        MigrationExecutor(connection).migrate(MIGRATION_LATEST)
        assert VisitPricing.objects.count() == 4
        for fact in facts:
            _assert_neutral_pricing(
                VisitPricing.objects.get(visit_id=fact["visit_id"]),
                fact,
            )
        bridge_payment = Payment.objects.get(pk=bridge_fact["payment_id"])
        assert bridge_payment.gross_total_minor_snapshot == bridge_fact["amount_minor"]
        assert bridge_payment.net_total_minor_snapshot == bridge_fact["amount_minor"]
        assert bridge_payment.pricing_snapshot_is_legacy is True
        assert not PatientLoyaltyState.objects.exists()
        assert not VisitLoyaltyEvent.objects.exists()

        MigrationExecutor(connection).migrate(MIGRATION_OLD)
        reversed_apps = MigrationExecutor(connection).loader.project_state(MIGRATION_OLD).apps
        ReversedReceivable = reversed_apps.get_model("billing", "Receivable")
        ReversedPayment = reversed_apps.get_model("billing", "Payment")
        ReversedRefund = reversed_apps.get_model("billing", "Refund")
        assert set(ReversedReceivable.objects.values_list("pk", flat=True)) == {
            fact["receivable_id"] for fact in facts
        }
        assert set(ReversedPayment.objects.values_list("pk", flat=True)) == {
            fact["payment_id"] for fact in facts if fact["payment_id"] is not None
        }
        assert set(ReversedRefund.objects.values_list("pk", flat=True)) == {
            fact["refund_id"] for fact in facts if fact["refund_id"] is not None
        }

        MigrationExecutor(connection).migrate(MIGRATION_LATEST)
        assert VisitPricing.objects.count() == 4
        assert Payment.objects.filter(pricing_snapshot_is_legacy=True).count() == 3
    finally:
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_pricing_expand_preflight_rejects_total_mismatch_before_schema_mutation() -> None:
    admin = create_user(email="pricing-mismatch@example.test", role=UserRole.ADMIN)
    visit_id = _started_visits(actor=admin, amounts=[51_000])[0]
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_OLD)
    fact = _legacy_billing_fact(
        executor.loader.project_state(MIGRATION_OLD).apps,
        visit_id=visit_id,
        status="OPEN",
        actor=admin,
        shift_id=None,
    )
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = replica")
        cursor.execute(
            "UPDATE visits_visit SET total_minor = total_minor + 1 WHERE id = %s",
            [visit_id],
        )
    try:
        with pytest.raises(RuntimeError, match="service, Visit and Receivable totals differ"):
            MigrationExecutor(connection).migrate(MIGRATION_EXPANDED)
        assert ("billing", "0009_pricing_expand") not in (
            MigrationExecutor(connection).loader.applied_migrations
        )
    finally:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL session_replication_role = replica")
            cursor.execute(
                "UPDATE visits_visit SET total_minor = %s WHERE id = %s",
                [fact["amount_minor"], visit_id],
            )
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_pricing_contract_preflight_rejects_orphan_payment_ledger() -> None:
    admin = create_user(email="pricing-orphan-admin@example.test", role=UserRole.ADMIN)
    reception = create_user(
        email="pricing-orphan-reception@example.test",
        role=UserRole.RECEPTION,
    )
    shift = _cash_shift(actor=reception)
    visit_id = _started_visits(actor=admin, amounts=[61_000])[0]
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_OLD)
    old_apps = executor.loader.project_state(MIGRATION_OLD).apps
    _legacy_billing_fact(
        old_apps,
        visit_id=visit_id,
        status="OPEN",
        actor=reception,
        shift_id=shift.pk,
    )
    HistoricalLedger = old_apps.get_model("billing", "CashLedgerEntry")
    ledger_id = uuid4()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = replica")
        HistoricalLedger.objects.create(
            id=ledger_id,
            public_number=f"TXN-{ledger_id.hex[:12].upper()}",
            cash_shift_id=shift.pk,
            created_by_id=reception.pk,
            kind="PAYMENT",
            amount_minor=61_000,
            payment_method="CARD",
            idempotency_key="orphan-pricing-ledger",
            payload_hash="c" * 64,
            actor_name_snapshot=reception.display_name,
            actor_email_snapshot=reception.email,
            actor_role_snapshot=reception.role,
        )
    MigrationExecutor(connection).migrate(MIGRATION_EXPANDED)
    try:
        with pytest.raises(RuntimeError, match="untyped PAYMENT ledger entry"):
            MigrationExecutor(connection).migrate(MIGRATION_LATEST)
        applied = MigrationExecutor(connection).loader.applied_migrations
        assert ("billing", "0009_pricing_expand") in applied
        assert ("billing", "0010_pricing_contract") not in applied
    finally:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL session_replication_role = replica")
            cursor.execute("DELETE FROM billing_cashledgerentry WHERE id = %s", [ledger_id])
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_pricing_contract_preflight_rejects_partial_payment_bridge_snapshot() -> None:
    admin = create_user(email="pricing-partial-admin@example.test", role=UserRole.ADMIN)
    reception = create_user(
        email="pricing-partial-reception@example.test",
        role=UserRole.RECEPTION,
    )
    shift = _cash_shift(actor=reception)
    visit_id = _started_visits(actor=admin, amounts=[71_000])[0]
    executor = MigrationExecutor(connection)
    executor.migrate(MIGRATION_EXPANDED)
    expanded_apps = executor.loader.project_state(MIGRATION_EXPANDED).apps
    fact = _legacy_billing_fact(
        expanded_apps,
        visit_id=visit_id,
        status="PAID",
        actor=reception,
        shift_id=shift.pk,
    )
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL session_replication_role = replica")
        cursor.execute(
            """
            UPDATE billing_payment
               SET gross_total_minor_snapshot = %s
             WHERE id = %s
            """,
            [fact["amount_minor"], fact["payment_id"]],
        )
    try:
        with pytest.raises(RuntimeError, match="partial bridge pricing snapshots"):
            MigrationExecutor(connection).migrate(MIGRATION_LATEST)
        assert ("billing", "0010_pricing_contract") not in (
            MigrationExecutor(connection).loader.applied_migrations
        )
    finally:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SET LOCAL session_replication_role = replica")
            cursor.execute(
                """
                UPDATE billing_payment
                   SET gross_total_minor_snapshot = NULL
                 WHERE id = %s
                """,
                [fact["payment_id"]],
            )
        MigrationExecutor(connection).migrate(MIGRATION_LATEST)


@pytest.mark.django_db(transaction=True)
def test_pricing_reverse_is_blocked_after_nonlegacy_pricing_use() -> None:
    completed_receivable(index=18)

    with pytest.raises(RuntimeError, match="Cannot reverse pricing after"):
        MigrationExecutor(connection).migrate(MIGRATION_OLD)

    assert ("billing", "0010_pricing_contract") in (
        MigrationExecutor(connection).loader.applied_migrations
    )
