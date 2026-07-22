import json
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.clinic.models import ClinicProfile
from config.settings import env_secret


def test_env_secret_reads_file_without_exposing_it(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret"
    secret_file.write_text("file-only-value\n", encoding="utf-8")
    monkeypatch.delenv("TP903_TEST_SECRET", raising=False)
    monkeypatch.setenv("TP903_TEST_SECRET_FILE", str(secret_file))

    assert env_secret("TP903_TEST_SECRET") == "file-only-value"


def test_env_secret_rejects_ambiguous_sources(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret"
    secret_file.write_text("file-value", encoding="utf-8")
    monkeypatch.setenv("TP903_TEST_SECRET", "direct-value")
    monkeypatch.setenv("TP903_TEST_SECRET_FILE", str(secret_file))

    with pytest.raises(ImproperlyConfigured, match="Set only one"):
        env_secret("TP903_TEST_SECRET")


def test_env_secret_rejects_empty_direct_value(monkeypatch):
    monkeypatch.setenv("TP903_TEST_SECRET", "")
    monkeypatch.delenv("TP903_TEST_SECRET_FILE", raising=False)

    with pytest.raises(ImproperlyConfigured, match="must not be empty"):
        env_secret("TP903_TEST_SECRET")


@pytest.mark.django_db
def test_verify_restore_reports_current_migrations_and_objects(monkeypatch):
    monkeypatch.setattr(
        "config.object_storage.private_object_exists",
        lambda *, object_key: True,
    )
    stdout = StringIO()

    call_command("verify_restore", "--json", stdout=stdout)

    report = json.loads(stdout.getvalue())
    assert report["status"] == "ok"
    assert report["migration_count"] > 0
    assert report["pending_migrations"] == []
    assert report["missing_object_count"] == 0


@pytest.mark.django_db
def test_verify_restore_fails_without_leaking_missing_object_key(monkeypatch):
    profile = ClinicProfile.objects.get(pk="clinic")
    profile.logo_object_key = "private/patient-sensitive-logo.png"
    profile.save(update_fields=("logo_object_key", "updated_at"))
    monkeypatch.setattr(
        "config.object_storage.private_object_exists",
        lambda *, object_key: False,
    )
    stdout = StringIO()

    with pytest.raises(CommandError, match="Restore verification failed"):
        call_command("verify_restore", "--json", stdout=stdout)

    output = stdout.getvalue()
    report = json.loads(output)
    assert report["status"] == "failed"
    assert report["missing_object_count"] == 1
    assert "patient-sensitive-logo" not in output
