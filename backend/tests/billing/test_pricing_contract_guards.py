from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import (
    DatabaseError,
    close_old_connections,
    connection,
    connections,
    transaction,
)

from apps.accounts.models import UserRole
from apps.billing.models import (
    CashShift,
    Payment,
    PaymentMethod,
    PricingState,
    ReceivableStatus,
    VisitPricing,
)
from apps.discounts.models import Discount
from apps.visits import finish_services
from tests.billing.test_payments_api import (
    authenticated_client,
    completed_receivable,
    create_user,
    post_payment,
)
from tests.visits.test_loyalty_pricing import _additional_arrived
from tests.visits.test_visit_finish import _finish, _finish_payload
from tests.visits.test_visit_start_and_draft import arrived_appointment, start


def _wait_for_database_lock(application_name: str, *, timeout: float = 5.0) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT wait_event_type
                  FROM pg_stat_activity
                 WHERE datname = current_database()
                   AND application_name = %s
                """,
                [application_name],
            )
            if any(row[0] == "Lock" for row in cursor.fetchall()):
                return
        sleep(0.05)
    pytest.fail(f"Database session {application_name!r} did not block on a lock.")


@pytest.mark.django_db(transaction=True)
def test_raw_sql_guards_protect_service_lines_pricing_and_payment_snapshots() -> None:
    actor = create_user(email="pricing-raw@example.test", role=UserRole.RECEPTION)
    CashShift.objects.create(employee=actor)
    receivable = completed_receivable()
    visit = receivable.visit
    pricing = VisitPricing.objects.get(visit=visit)
    service_line = visit.service_lines.get()

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE visits_visitserviceline SET quantity = 2 WHERE id = %s",
            [service_line.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM visits_visitserviceline WHERE id = %s",
            [service_line.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM billing_visitpricing WHERE id = %s", [pricing.pk])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE billing_visitpricing
               SET gross_minor = gross_minor + 1,
                   net_minor = net_minor + 1,
                   version = version + 1,
                   updated_at = NOW()
             WHERE id = %s
            """,
            [pricing.pk],
        )

    paid = post_payment(
        authenticated_client(actor),
        receivable,
        key="pricing-raw-payment",
        payment_method=PaymentMethod.CARD,
    )
    assert paid.status_code == 201, paid.json()
    payment = Payment.objects.get(receivable=receivable)
    pricing.refresh_from_db()
    assert pricing.state == PricingState.SETTLED

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE billing_visitpricing
               SET version = version + 1, updated_at = NOW()
             WHERE id = %s
            """,
            [pricing.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE billing_payment
               SET net_total_minor_snapshot = net_total_minor_snapshot - 1
             WHERE id = %s
            """,
            [payment.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM billing_payment WHERE id = %s", [payment.pk])

    service_line.refresh_from_db()
    pricing.refresh_from_db()
    payment.refresh_from_db()
    assert service_line.quantity == 1
    assert pricing.version == 2
    assert payment.net_total_minor_snapshot == receivable.amount_minor


@pytest.mark.django_db(transaction=True)
def test_raw_pricing_requires_valid_formula_snapshot_and_manual_actor() -> None:
    actor = create_user(email="pricing-formula@example.test", role=UserRole.RECEPTION)
    receivable = completed_receivable()
    pricing = VisitPricing.objects.get(visit_id=receivable.visit_id)
    discount = Discount.objects.create(name="Raw 10", percent=10)
    discount_amount = pricing.gross_minor * discount.percent // 100

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE billing_visitpricing
               SET discount_id = %s,
                   discount_name_snapshot = %s,
                   discount_percent_snapshot = %s,
                   discount_source = 'RECEPTION',
                   applied_by_id = NULL,
                   discount_amount_minor = %s,
                   net_minor = gross_minor - %s,
                   version = version + 1,
                   updated_at = NOW()
             WHERE id = %s
            """,
            [
                discount.pk,
                discount.name,
                discount.percent,
                discount_amount,
                discount_amount,
                pricing.pk,
            ],
        )

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE billing_visitpricing
               SET discount_id = %s,
                   discount_name_snapshot = %s,
                   discount_percent_snapshot = %s,
                   discount_source = 'RECEPTION',
                   applied_by_id = %s,
                   discount_amount_minor = %s + 1,
                   net_minor = gross_minor - (%s + 1),
                   version = version + 1,
                   updated_at = NOW()
             WHERE id = %s
            """,
            [
                discount.pk,
                discount.name,
                discount.percent,
                actor.pk,
                discount_amount,
                discount_amount,
                pricing.pk,
            ],
        )

    pricing.refresh_from_db()
    assert pricing.discount_id is None
    assert pricing.discount_amount_minor == 0
    assert pricing.net_minor == pricing.gross_minor
    assert pricing.version == 1


@pytest.mark.django_db(transaction=True)
def test_raw_service_line_cannot_be_reparented_into_priced_visit() -> None:
    actor = create_user(email="line-reparent@example.test", role=UserRole.ADMIN)
    target_receivable = completed_receivable(index=9)
    source_appointment = arrived_appointment(actor=actor)
    source = start(authenticated_client(actor), source_appointment)
    assert source.status_code == 201, source.json()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM visits_visitserviceline WHERE visit_id = %s",
            [source.json()["id"]],
        )
        source_line_id = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE visits_visitserviceline SET is_primary = FALSE WHERE id = %s",
            [source_line_id],
        )

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO visits_visitserviceline (
                id, visit_id, service_id, service_code, service_name,
                duration_minutes, price_minor, quantity, is_primary,
                created_at, updated_at
            )
            SELECT %s, %s, service_id, service_code, service_name,
                   duration_minutes, price_minor, quantity, FALSE, NOW(), NOW()
              FROM visits_visitserviceline
             WHERE id = %s
            """,
            [uuid4(), target_receivable.visit_id, source_line_id],
        )

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE visits_visitserviceline SET visit_id = %s WHERE id = %s",
            [target_receivable.visit_id, source_line_id],
        )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT visit_id FROM visits_visitserviceline WHERE id = %s",
            [source_line_id],
        )
        assert str(cursor.fetchone()[0]) == source.json()["id"]


@pytest.mark.django_db(transaction=True)
def test_deferred_financial_guards_reject_partial_commit_but_allow_atomic_repricing() -> None:
    actor = create_user(email="pricing-deferred@example.test", role=UserRole.RECEPTION)
    receivable = completed_receivable()
    visit = receivable.visit
    pricing = VisitPricing.objects.get(visit=visit)

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE visits_visit SET total_minor = total_minor - 1 WHERE id = %s",
            [visit.pk],
        )

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE billing_visitpricing
               SET state = 'SETTLED',
                   settled_at = NOW(),
                   version = version + 1,
                   updated_at = NOW()
             WHERE id = %s
            """,
            [pricing.pk],
        )

    discount = Discount.objects.create(name="Deferred 10", percent=10)
    discount_amount = pricing.gross_minor * discount.percent // 100
    net_minor = pricing.gross_minor - discount_amount
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE visits_visit SET total_minor = %s WHERE id = %s",
            [net_minor, visit.pk],
        )
        cursor.execute(
            "UPDATE billing_receivable SET amount_minor = %s WHERE id = %s",
            [net_minor, receivable.pk],
        )
        cursor.execute(
            """
            UPDATE billing_visitpricing
               SET discount_id = %s,
                   discount_name_snapshot = %s,
                   discount_percent_snapshot = %s,
                   discount_source = 'RECEPTION',
                   applied_by_id = %s,
                   discount_amount_minor = %s,
                   net_minor = %s,
                   version = version + 1,
                   updated_at = NOW()
             WHERE id = %s
            """,
            [
                discount.pk,
                discount.name,
                discount.percent,
                actor.pk,
                discount_amount,
                net_minor,
                pricing.pk,
            ],
        )

    visit.refresh_from_db()
    receivable.refresh_from_db()
    pricing.refresh_from_db()
    assert visit.total_minor == net_minor
    assert receivable.amount_minor == net_minor
    assert receivable.status == ReceivableStatus.OPEN
    assert pricing.net_minor == net_minor
    assert pricing.discount_id == discount.pk
    assert pricing.version == 2
    assert pricing.state == PricingState.OPEN


@pytest.mark.django_db(transaction=True)
def test_deferred_lifecycle_rejects_pricing_or_receivable_without_counterpart() -> None:
    actor = create_user(email="pricing-orphan@example.test", role=UserRole.ADMIN)
    pricing_appointment = arrived_appointment(actor=actor)
    pricing_start = start(authenticated_client(actor), pricing_appointment)
    assert pricing_start.status_code == 201, pricing_start.json()
    pricing_visit_id = pricing_start.json()["id"]

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(SUM(price_minor * quantity), 0)
              FROM visits_visitserviceline
             WHERE visit_id = %s
            """,
            [pricing_visit_id],
        )
        gross_minor = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO billing_visitpricing (
                id, visit_id, gross_minor, discount_id,
                discount_name_snapshot, discount_percent_snapshot,
                discount_source, applied_by_id, discount_amount_minor,
                net_minor, is_legacy_backfill, version, state, settled_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, NULL, '', NULL, '', NULL, 0,
                %s, FALSE, 1, 'OPEN', NULL, NOW(), NOW()
            )
            """,
            [uuid4(), pricing_visit_id, gross_minor, gross_minor],
        )

    receivable_appointment = _additional_arrived(
        actor=actor,
        source=pricing_appointment,
        day_offset=1,
    )
    receivable_start = start(authenticated_client(actor), receivable_appointment)
    assert receivable_start.status_code == 201, receivable_start.json()
    receivable_visit_id = receivable_start.json()["id"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(SUM(price_minor * quantity), 0)
              FROM visits_visitserviceline
             WHERE visit_id = %s
            """,
            [receivable_visit_id],
        )
        amount_minor = cursor.fetchone()[0]

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO billing_receivable (
                id, visit_id, amount_minor, status, created_at, updated_at
            ) VALUES (%s, %s, %s, 'OPEN', NOW(), NOW())
            """,
            [uuid4(), receivable_visit_id, amount_minor],
        )


@pytest.mark.django_db(transaction=True)
def test_raw_zero_gross_pricing_rejects_discount_identity() -> None:
    actor = create_user(email="zero-raw@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=actor)
    appointment.service.price_minor = 0
    appointment.service.save(update_fields=("price_minor", "updated_at"))
    started = start(authenticated_client(actor), appointment)
    assert started.status_code == 201, started.json()
    discount = Discount.objects.create(name="Zero raw 99", percent=99)

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO billing_visitpricing (
                id, visit_id, gross_minor, discount_id,
                discount_name_snapshot, discount_percent_snapshot,
                discount_source, applied_by_id, discount_amount_minor,
                net_minor, is_legacy_backfill, version, state, settled_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, 0, %s, %s, %s, 'LOYALTY', NULL, 0,
                0, FALSE, 1, 'SETTLED', NOW(), NOW(), NOW()
            )
            """,
            [uuid4(), started.json()["id"], discount.pk, discount.name, discount.percent],
        )
        cursor.execute(
            """
            INSERT INTO billing_receivable (
                id, visit_id, amount_minor, status, created_at, updated_at
            ) VALUES (%s, %s, 0, 'PAID', NOW(), NOW())
            """,
            [uuid4(), started.json()["id"]],
        )
        cursor.execute(
            """
            UPDATE visits_visit
               SET status = 'COMPLETED', total_minor = 0,
                   completed_at = NOW(), updated_at = NOW()
             WHERE id = %s
            """,
            [started.json()["id"]],
        )


@pytest.mark.django_db(transaction=True)
def test_finish_first_serializes_raw_service_mutation_then_rejects_it() -> None:
    actor = create_user(email="finish-lock-first@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=actor)
    started = start(authenticated_client(actor), appointment)
    assert started.status_code == 201, started.json()
    visit_id = started.json()["id"]
    visit_version = started.json()["version"]
    service_line_id = started.json()["service_lines"][0]["id"]
    pricing_created = Event()
    release_finish = Event()
    mutation_started = Event()
    original_create_pricing = finish_services.create_visit_pricing

    def paused_create_pricing(*args, **kwargs):
        pricing = original_create_pricing(*args, **kwargs)
        pricing_created.set()
        if not release_finish.wait(timeout=10):
            raise TimeoutError("Timed out while holding the finish Visit lock.")
        return pricing

    def submit_finish() -> int:
        close_old_connections()
        request_actor = type(actor).objects.get(pk=actor.pk)
        try:
            response = _finish(
                authenticated_client(request_actor),
                visit_id,
                _finish_payload(version=visit_version, recommendation=""),
                key="finish-lock-first",
            )
            return response.status_code
        finally:
            connections["default"].close()

    def mutate_service_line() -> str:
        close_old_connections()
        mutation_connection = connections["default"]
        try:
            with mutation_connection.cursor() as cursor:
                cursor.execute("SET application_name = 'pricing_guard_mutation_after_finish'")
            mutation_started.set()
            try:
                with transaction.atomic(using="default"):
                    with mutation_connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE visits_visitserviceline
                               SET quantity = 2, updated_at = NOW()
                             WHERE id = %s
                            """,
                            [service_line_id],
                        )
                return "committed"
            except DatabaseError:
                return "rejected"
        finally:
            mutation_connection.close()

    try:
        with (
            patch.object(
                finish_services,
                "create_visit_pricing",
                side_effect=paused_create_pricing,
            ),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            finish_future = executor.submit(submit_finish)
            assert pricing_created.wait(timeout=10)
            mutation_future = executor.submit(mutate_service_line)
            assert mutation_started.wait(timeout=5)
            _wait_for_database_lock("pricing_guard_mutation_after_finish")
            assert not mutation_future.done()
            release_finish.set()
            assert finish_future.result(timeout=15) == 201
            assert mutation_future.result(timeout=15) == "rejected"
    finally:
        release_finish.set()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT quantity FROM visits_visitserviceline WHERE id = %s",
            [service_line_id],
        )
        assert cursor.fetchone() == (1,)
    assert VisitPricing.objects.filter(visit_id=visit_id).exists()


@pytest.mark.django_db(transaction=True)
def test_service_mutation_first_serializes_finish_and_updates_pricing_gross() -> None:
    actor = create_user(email="mutation-lock-first@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=actor)
    started = start(authenticated_client(actor), appointment)
    assert started.status_code == 201, started.json()
    visit_id = started.json()["id"]
    visit_version = started.json()["version"]
    service_line_id = started.json()["service_lines"][0]["id"]
    unit_price_minor = started.json()["service_lines"][0]["price_minor"]
    mutation_applied = Event()
    release_mutation = Event()
    finish_started = Event()

    def hold_service_mutation() -> str:
        close_old_connections()
        mutation_connection = connections["default"]
        try:
            with transaction.atomic(using="default"):
                with mutation_connection.cursor() as cursor:
                    cursor.execute("SET LOCAL application_name = 'pricing_guard_mutation_owner'")
                    cursor.execute(
                        """
                        UPDATE visits_visitserviceline
                           SET quantity = 2, updated_at = NOW()
                         WHERE id = %s
                        """,
                        [service_line_id],
                    )
                mutation_applied.set()
                if not release_mutation.wait(timeout=10):
                    raise TimeoutError("Timed out while holding the mutation Visit lock.")
            return "committed"
        finally:
            mutation_connection.close()

    def submit_finish() -> int:
        close_old_connections()
        finish_connection = connections["default"]
        request_actor = type(actor).objects.get(pk=actor.pk)
        try:
            with finish_connection.cursor() as cursor:
                cursor.execute("SET application_name = 'pricing_guard_finish_after_mutation'")
            finish_started.set()
            response = _finish(
                authenticated_client(request_actor),
                visit_id,
                _finish_payload(version=visit_version, recommendation=""),
                key="mutation-lock-first",
            )
            return response.status_code
        finally:
            finish_connection.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            mutation_future = executor.submit(hold_service_mutation)
            assert mutation_applied.wait(timeout=10)
            finish_future = executor.submit(submit_finish)
            assert finish_started.wait(timeout=5)
            _wait_for_database_lock("pricing_guard_finish_after_mutation")
            assert not finish_future.done()
            release_mutation.set()
            assert mutation_future.result(timeout=15) == "committed"
            assert finish_future.result(timeout=15) == 201
    finally:
        release_mutation.set()

    pricing = VisitPricing.objects.get(visit_id=visit_id)
    assert pricing.gross_minor == unit_price_minor * 2
    assert pricing.net_minor == unit_price_minor * 2
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT quantity FROM visits_visitserviceline WHERE id = %s",
            [service_line_id],
        )
        assert cursor.fetchone() == (2,)
