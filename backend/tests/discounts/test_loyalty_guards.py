from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.discounts.models import (
    Discount,
    LoyaltyPolicy,
    PatientLoyaltyState,
    VisitLoyaltyEvent,
)
from apps.patients.models import Patient
from apps.visits.models import Visit
from tests.visits.test_visit_start_and_draft import (
    arrived_appointment,
    authenticated_client,
    create_user,
    start,
)

MIGRATION_BASE = [
    ("billing", "0009_pricing_expand"),
    ("discounts", "0001_initial"),
]
MIGRATION_CURRENT = [("billing", "0010_pricing_contract")]


def _patient(*, suffix: str) -> Patient:
    return Patient.objects.create(
        first_name="Тест",
        last_name="Лояльність",
        phone=f"+38050123{suffix}",
    )


def _default_policy() -> LoyaltyPolicy:
    policy, _ = LoyaltyPolicy.objects.get_or_create(key="default")
    return policy


def _activate_policy(discount: Discount, *, every_n: int = 1) -> LoyaltyPolicy:
    policy = _default_policy()
    policy.is_active = True
    policy.every_n = every_n
    policy.discount = discount
    policy.started_at = timezone.now()
    policy.version += 1
    policy.save()
    return policy


@pytest.mark.django_db(transaction=True)
def test_raw_catalog_and_singleton_guards_reject_key_trim_and_delete() -> None:
    _default_policy()
    invalid_discount_id = uuid4()
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO discounts_discount (
                id, name, percent, is_active, version, created_at, updated_at
            ) VALUES (%s, %s, 10, TRUE, 1, NOW(), NOW())
            """,
            [invalid_discount_id, "  З пробілами  "],
        )

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO discounts_loyaltypolicy (
                key, is_active, every_n, discount_id, version,
                started_at, created_at, updated_at
            ) VALUES ('secondary', FALSE, 5, NULL, 1, NULL, NOW(), NOW())
            """
        )

    discount = Discount.objects.create(name="Захищена", percent=10)
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM discounts_discount WHERE id = %s", [discount.pk])
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM discounts_loyaltypolicy WHERE key = 'default'")

    assert Discount.objects.filter(pk=discount.pk).exists()
    assert LoyaltyPolicy.objects.filter(key="default").exists()
    assert not Discount.objects.filter(pk=invalid_discount_id).exists()


@pytest.mark.django_db(transaction=True)
def test_raw_deactivation_of_active_loyalty_discount_is_rejected() -> None:
    discount = Discount.objects.create(name="Активна лояльність", percent=10)
    _activate_policy(discount, every_n=5)

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE discounts_discount SET is_active = FALSE WHERE id = %s",
            [discount.pk],
        )

    discount.refresh_from_db()
    assert discount.is_active is True
    assert LoyaltyPolicy.objects.get(key="default").discount_id == discount.pk


@pytest.mark.django_db(transaction=True)
def test_raw_activation_with_inactive_loyalty_discount_is_rejected() -> None:
    discount = Discount.objects.create(
        name="Неактивна лояльність",
        percent=10,
        is_active=False,
    )
    _default_policy()

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE discounts_loyaltypolicy
               SET is_active = TRUE,
                   discount_id = %s,
                   started_at = NOW(),
                   version = version + 1,
                   updated_at = NOW()
             WHERE key = 'default'
            """,
            [discount.pk],
        )

    policy = LoyaltyPolicy.objects.get(key="default")
    assert policy.is_active is False
    assert policy.discount_id is None


@pytest.mark.django_db(transaction=True)
def test_deferred_guard_rejects_loyalty_counter_without_visit_event() -> None:
    patient = _patient(suffix="0001")
    state = PatientLoyaltyState.objects.create(patient=patient)

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE discounts_patientloyaltystate
               SET completed_count = 1, version = 2, updated_at = NOW()
             WHERE patient_id = %s
            """,
            [patient.pk],
        )

    state.refresh_from_db()
    assert state.completed_count == 0
    assert state.version == 1
    assert not VisitLoyaltyEvent.objects.filter(patient=patient).exists()


@pytest.mark.django_db(transaction=True)
def test_loyalty_event_is_append_only_after_valid_counter_advance() -> None:
    actor = create_user(email="loyalty-guard-admin@example.test", role=UserRole.ADMIN)
    appointment = arrived_appointment(actor=actor)
    started = start(authenticated_client(actor), appointment)
    assert started.status_code == 201, started.json()
    visit = Visit.objects.get(pk=started.json()["id"])
    discount = Discount.objects.create(name="Кожен візит", percent=10)
    policy = _activate_policy(discount)
    state = PatientLoyaltyState.objects.create(patient=visit.patient)

    with transaction.atomic():
        state.completed_count = 1
        state.version = 2
        state.save(update_fields=("completed_count", "version", "updated_at"))
        event = VisitLoyaltyEvent.objects.create(
            visit=visit,
            patient=visit.patient,
            sequence_number=1,
            eligible=True,
            every_n_snapshot=policy.every_n,
            discount=discount,
            discount_name_snapshot=discount.name,
            discount_percent_snapshot=discount.percent,
            policy_started_at_snapshot=policy.started_at,
        )

    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE discounts_visitloyaltyevent SET eligible = FALSE WHERE id = %s",
            [event.pk],
        )
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM discounts_visitloyaltyevent WHERE id = %s", [event.pk])

    event.refresh_from_db()
    assert event.eligible is True


@pytest.mark.django_db(transaction=True)
def test_loyalty_guards_reverse_before_usage_and_reapply_cleanly() -> None:
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(MIGRATION_BASE)
        applied = MigrationExecutor(connection).loader.applied_migrations
        assert ("billing", "0009_pricing_expand") in applied
        assert ("billing", "0010_pricing_contract") not in applied
        assert ("discounts", "0002_loyalty_guards") not in applied
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('discounts_visitpricing')")
            assert cursor.fetchone() == (None,)

        MigrationExecutor(connection).migrate(MIGRATION_CURRENT)
        applied = MigrationExecutor(connection).loader.applied_migrations
        assert ("billing", "0010_pricing_contract") in applied
        assert ("discounts", "0002_loyalty_guards") in applied
    finally:
        MigrationExecutor(connection).migrate(MIGRATION_CURRENT)


@pytest.mark.django_db(transaction=True)
def test_loyalty_guards_reverse_is_blocked_after_state_creation() -> None:
    patient = _patient(suffix="0002")
    PatientLoyaltyState.objects.create(patient=patient)

    with pytest.raises(RuntimeError, match="Cannot reverse pricing after loyalty"):
        MigrationExecutor(connection).migrate(MIGRATION_BASE)

    applied = MigrationExecutor(connection).loader.applied_migrations
    assert ("billing", "0010_pricing_contract") in applied
    assert ("discounts", "0002_loyalty_guards") in applied
