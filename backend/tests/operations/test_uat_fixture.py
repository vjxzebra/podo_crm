import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.access import route_ids_for
from apps.accounts.models import User
from apps.clinic.models import AppointmentStatusConfig
from apps.operations.management.commands.uat_fixture import (
    UAT_PATIENT_PHONE,
    UAT_PODOLOGIST_EMAIL,
    UAT_RECEPTION_EMAIL,
    UAT_ROOM_NAME,
    UAT_SERVICE_CODE,
)
from apps.patients.models import Patient
from apps.scheduling.models import Appointment


@pytest.mark.django_db(transaction=True)
def test_uat_fixture_prepare_is_secret_safe_idempotent_and_exactly_cleanable(tmp_path, settings):
    settings.DEBUG = True
    AppointmentStatusConfig.objects.get_or_create(
        code="CONFIRMED",
        defaults={
            "label": "Підтверджено",
            "color": "#2563EB",
            "manual_admin": True,
            "manual_reception": True,
            "manual_podologist": False,
        },
    )
    credentials_file = tmp_path / ".env.local"
    credentials_file.write_text(
        "PODORIA_LOCAL_ADMIN_PASSWORD=local-test-password-placeholder\n",
        encoding="utf-8",
    )
    stdout = StringIO()

    call_command(
        "uat_fixture",
        "prepare",
        "--credentials-file",
        str(credentials_file),
        stdout=stdout,
    )
    first_report = json.loads(stdout.getvalue())
    stdout.seek(0)
    stdout.truncate(0)
    call_command(
        "uat_fixture",
        "prepare",
        "--credentials-file",
        str(credentials_file),
        stdout=stdout,
    )
    second_report = json.loads(stdout.getvalue())

    assert first_report["event"] == second_report["event"] == "tp904_uat_fixture_prepared"
    assert "password" not in stdout.getvalue().lower()
    assert User.objects.filter(email=UAT_RECEPTION_EMAIL).count() == 1
    assert User.objects.filter(email=UAT_PODOLOGIST_EMAIL).count() == 1
    podologist = User.objects.get(email=UAT_PODOLOGIST_EMAIL)
    reception = User.objects.get(email=UAT_RECEPTION_EMAIL)
    assert podologist.check_password("local-test-password-placeholder")
    assert "finance" not in route_ids_for(podologist)
    assert "finance" in route_ids_for(reception)
    assert Patient.objects.filter(phone=UAT_PATIENT_PHONE).count() == 1
    assert Appointment.objects.filter(comment="TP-904-UAT").count() == 1

    stdout.seek(0)
    stdout.truncate(0)
    call_command("uat_fixture", "cleanup", stdout=stdout)
    cleanup_report = json.loads(stdout.getvalue())

    assert cleanup_report["event"] == "tp904_uat_fixture_cleaned"
    assert not User.objects.filter(email__in=(UAT_RECEPTION_EMAIL, UAT_PODOLOGIST_EMAIL)).exists()
    assert not Patient.objects.filter(phone=UAT_PATIENT_PHONE).exists()
    assert not Appointment.objects.filter(comment="TP-904-UAT").exists()
    assert not Appointment.objects.filter(room__name=UAT_ROOM_NAME).exists()
    assert not Appointment.objects.filter(service__code=UAT_SERVICE_CODE).exists()


@pytest.mark.django_db
def test_uat_fixture_rejects_missing_or_empty_credentials_file(tmp_path, settings):
    settings.DEBUG = True
    with pytest.raises(CommandError, match="--credentials-file is required"):
        call_command("uat_fixture", "prepare")

    empty_file = tmp_path / "empty"
    empty_file.write_text("\n", encoding="utf-8")
    with pytest.raises(CommandError, match="exactly one non-empty"):
        call_command("uat_fixture", "prepare", "--credentials-file", str(empty_file))


@pytest.mark.django_db
def test_uat_fixture_refuses_non_debug(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="only when DEBUG is enabled"):
        call_command("uat_fixture", "cleanup")
