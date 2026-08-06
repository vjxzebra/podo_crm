import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.billing.models import CashShift, Payment, Receivable, Refund, VisitPricing
from apps.clinic.models import (
    AppointmentStatusConfig,
    ClinicProfile,
    ClinicWorkday,
    Room,
    Service,
)
from apps.inventory.models import (
    InventoryOperation,
    Material,
    MaterialLot,
    StockMovement,
    Stocktake,
    Supplier,
)
from apps.notifications.models import Notification
from apps.operations.demo_seed import (
    DEMO_CONFIRMATION,
    DEMO_SEED_VERSION,
)
from apps.patients.models import Patient
from apps.scheduling.models import Appointment
from apps.visits.models import Visit, VisitPhoto
from apps.work_items.models import WorkItem


def _admin() -> User:
    return User.objects.create_superuser(
        email="seed-owner@example.test",
        password=None,
        first_name="Seed",
        last_name="Owner",
    )


@pytest.mark.django_db(transaction=True)
def test_small_demo_seed_is_cross_domain_secret_safe_and_idempotent() -> None:
    _admin()
    first_stdout = StringIO()
    second_stdout = StringIO()

    with patch("apps.operations.demo_seed.put_private_object") as put_object:
        call_command(
            "seed_demo_data",
            "--confirm",
            DEMO_CONFIRMATION,
            "--scale",
            "small",
            stdout=first_stdout,
        )
        first = json.loads(first_stdout.getvalue())
        first_storage_calls = put_object.call_count
        call_command(
            "seed_demo_data",
            "--confirm",
            DEMO_CONFIRMATION,
            "--scale",
            "small",
            stdout=second_stdout,
        )
        second = json.loads(second_stdout.getvalue())

    assert first["status"] == "seeded"
    assert second["status"] == "already_seeded"
    assert first["seed_version"] == second["seed_version"] == DEMO_SEED_VERSION
    assert first["scale"] == second["scale"] == "small"
    assert first_storage_calls == 8
    assert put_object.call_count == first_storage_calls
    assert "password" not in first_stdout.getvalue().lower().replace('"passwords"', "")
    assert first["demo_accounts"]["passwords"] == "unusable"

    marker = User.objects.get(email="demo.reception.01@podoria.test")
    assert not marker.has_usable_password()
    assert User.objects.count() == 5
    assert ClinicProfile.objects.filter(pk="clinic").exists()
    assert AppointmentStatusConfig.objects.count() == 8
    assert ClinicWorkday.objects.count() == 7
    assert Room.objects.count() == 2
    assert Service.objects.count() == 6
    assert Patient.objects.count() == 12
    assert Appointment.objects.count() == 28
    assert Visit.objects.exists()
    assert VisitPhoto.objects.count() == 4
    assert Supplier.objects.count() == 3
    assert Material.objects.count() == 8
    assert MaterialLot.objects.exists()
    assert InventoryOperation.objects.exists()
    assert StockMovement.objects.exists()
    assert Stocktake.objects.count() == 1
    assert Receivable.objects.exists()
    assert Payment.objects.exists()
    assert Refund.objects.exists()
    completed_visit_count = Visit.objects.filter(status="COMPLETED").count()
    assert VisitPricing.objects.filter(visit__status="COMPLETED").count() == completed_visit_count
    assert Receivable.objects.filter(visit__status="COMPLETED").count() == completed_visit_count
    assert not VisitPricing.objects.filter(is_legacy_backfill=True).exists()
    assert not Payment.objects.filter(pricing_snapshot_is_legacy=True).exists()
    assert CashShift.objects.count() == 2
    assert WorkItem.objects.count() == 16
    assert Notification.objects.count() >= 16
    assert second["counts"] == first["counts"]


@pytest.mark.django_db(transaction=True)
def test_large_demo_seed_reaches_the_production_cardinalities() -> None:
    _admin()
    stdout = StringIO()

    with patch("apps.operations.demo_seed.put_private_object") as put_object:
        call_command(
            "seed_demo_data",
            "--confirm",
            DEMO_CONFIRMATION,
            "--scale",
            "large",
            stdout=stdout,
        )

    result = json.loads(stdout.getvalue())
    assert result["status"] == "seeded"
    assert result["scale"] == "large"
    assert put_object.call_count == 80
    assert User.objects.count() == 9
    assert Patient.objects.count() == 140
    assert Appointment.objects.count() == 360
    assert VisitPhoto.objects.count() == 40
    assert Supplier.objects.count() == 10
    assert Material.objects.count() == 36
    assert Room.objects.count() == 4
    assert Service.objects.count() == 12
    assert WorkItem.objects.count() == 90


@pytest.mark.django_db
def test_demo_seed_requires_exact_confirmation_and_initial_admin() -> None:
    with pytest.raises(CommandError, match="Exact confirmation token"):
        call_command("seed_demo_data", "--confirm", "WRONG", "--scale", "small")

    with pytest.raises(CommandError, match="initial production administrator"):
        call_command(
            "seed_demo_data",
            "--confirm",
            DEMO_CONFIRMATION,
            "--scale",
            "small",
        )


@pytest.mark.django_db
def test_demo_seed_refuses_an_occupied_domain_database() -> None:
    admin = _admin()
    Patient.objects.create(
        first_name="Existing",
        last_name="Patient",
        phone="+380670000001",
        created_by=admin,
    )

    with pytest.raises(CommandError, match="only into an empty CRM domain database"):
        call_command(
            "seed_demo_data",
            "--confirm",
            DEMO_CONFIRMATION,
            "--scale",
            "small",
        )
