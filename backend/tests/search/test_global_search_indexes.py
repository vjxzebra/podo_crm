import json
from typing import Any

import pytest
from django.db import connection, models, transaction

from apps.accounts.models import User, UserRole
from apps.billing.models import CashLedgerEntry, Payment
from apps.billing.selectors import payment_receivables_for_global_search
from apps.inventory.models import Material
from apps.patients.models import Patient
from apps.patients.selectors import patients_for_global_search
from apps.scheduling.models import Appointment
from apps.scheduling.selectors import appointments_for_global_search
from apps.visits.models import Visit, VisitServiceLine

EXPECTED_SEARCH_INDEXES = {
    "patients_global_search_gin",
    "scheduling_global_search_gin",
    "inventory_global_search_gin",
    "visits_number_search_gin",
    "visits_service_search_gin",
    "billing_ledger_search_gin",
    "billing_payment_search_gin",
    "billing_phone_digits_gin",
}


def _index_names(node: Any) -> set[str]:
    if isinstance(node, dict):
        values = {str(node["Index Name"])} if "Index Name" in node else set()
        for value in node.values():
            values.update(_index_names(value))
        return values
    if isinstance(node, list):
        values: set[str] = set()
        for value in node:
            values.update(_index_names(value))
        return values
    return set()


def _planned_indexes(queryset: Any) -> set[str]:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        plan = json.loads(queryset.explain(format="json"))
    return _index_names(plan)


@pytest.mark.django_db
def test_pg_trgm_extension_and_targeted_search_indexes_exist() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
        assert cursor.fetchone() == ("pg_trgm",)
        cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
        installed = {row[0] for row in cursor.fetchall()}
    assert EXPECTED_SEARCH_INDEXES <= installed


@pytest.mark.django_db
def test_combined_patient_global_selector_keeps_trigram_index_in_query_plan() -> None:
    admin = User.objects.create_user(
        email="plan-admin@example.test",
        password=None,
        role=UserRole.ADMIN,
    )
    indexes = _planned_indexes(patients_for_global_search(admin, "орбіта"))
    assert "patients_global_search_gin" in indexes


@pytest.mark.django_db
def test_combined_appointment_global_selector_keeps_trigram_index_in_query_plan() -> None:
    admin = User.objects.create_user(
        email="appointment-plan-admin@example.test",
        password=None,
        role=UserRole.ADMIN,
    )

    indexes = _planned_indexes(appointments_for_global_search(admin, "орбіта"))

    assert "scheduling_global_search_gin" in indexes


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("search", "expected_index"),
    [
        ("орбіта", "billing_payment_search_gin"),
        ("380671234567", "billing_phone_digits_gin"),
        ("txn-abcd", "billing_ledger_search_gin"),
    ],
)
def test_combined_payment_global_selector_keeps_trigram_indexes_in_query_plan(
    search: str,
    expected_index: str,
) -> None:
    reception = User.objects.create_user(
        email=f"payment-plan-{expected_index}@example.test",
        password=None,
        role=UserRole.RECEPTION,
    )

    indexes = _planned_indexes(payment_receivables_for_global_search(reception, search))

    assert expected_index in indexes


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("queryset", "expected_index"),
    [
        (Patient.objects.filter(first_name__icontains="орбіта"), "patients_global_search_gin"),
        (
            Appointment.objects.filter(service_name_snapshot__icontains="орбіта"),
            "scheduling_global_search_gin",
        ),
        (Material.objects.filter(name__icontains="орбіта"), "inventory_global_search_gin"),
        (Visit.objects.filter(public_number__icontains="v-abcd"), "visits_number_search_gin"),
        (
            VisitServiceLine.objects.filter(service_name__icontains="орбіта"),
            "visits_service_search_gin",
        ),
        (
            CashLedgerEntry.objects.filter(public_number__icontains="txn-abcd"),
            "billing_ledger_search_gin",
        ),
        (
            Payment.objects.filter(patient_name_snapshot__icontains="орбіта"),
            "billing_payment_search_gin",
        ),
        (
            Payment.objects.annotate(
                phone_digits=models.Func(
                    "patient_phone_snapshot",
                    models.Value("[^0-9]"),
                    models.Value(""),
                    models.Value("g"),
                    function="REGEXP_REPLACE",
                    output_field=models.CharField(),
                )
            ).filter(phone_digits__contains="38067123"),
            "billing_phone_digits_gin",
        ),
    ],
)
def test_trigram_search_queries_are_index_backed(queryset: Any, expected_index: str) -> None:
    assert expected_index in _planned_indexes(queryset)
