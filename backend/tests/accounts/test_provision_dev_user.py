from io import StringIO

import pytest
from django.conf import settings as django_settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User, UserRole

PREVIOUS_PASSWORD = "previous-local-password"  # noqa: S105
REPLACEMENT_PASSWORD = "replacement-local-password"  # noqa: S105


@pytest.mark.django_db
def test_provision_dev_user_reads_env_file_without_exposing_password(tmp_path, settings):
    settings.DEBUG = True
    credentials = tmp_path / ".env.local"
    credentials.write_text(
        "PODORIA_LOCAL_ADMIN_PASSWORD=local-only-password-placeholder\n",
        encoding="utf-8",
    )
    stdout = StringIO()

    call_command(
        "provision_dev_user",
        "--email",
        "local-admin@example.test",
        "--credentials-file",
        str(credentials),
        "--role",
        UserRole.ADMIN,
        stdout=stdout,
    )

    user = User.objects.get(email="local-admin@example.test")
    assert user.check_password("local-only-password-placeholder")
    assert "local-only-password-placeholder" not in stdout.getvalue()


@pytest.mark.django_db
def test_provision_dev_user_revokes_existing_sessions(client, tmp_path, settings):
    settings.DEBUG = True
    user = User.objects.create_user(
        email="local-admin@example.test",
        password=PREVIOUS_PASSWORD,
        role=UserRole.ADMIN,
    )
    assert client.login(email=user.email, password=PREVIOUS_PASSWORD)
    session_key = client.cookies[django_settings.SESSION_COOKIE_NAME].value
    credentials = tmp_path / ".env.local"
    credentials.write_text(
        f"PODORIA_LOCAL_ADMIN_PASSWORD={REPLACEMENT_PASSWORD}\n",
        encoding="utf-8",
    )

    call_command(
        "provision_dev_user",
        "--email",
        user.email,
        "--credentials-file",
        str(credentials),
        "--role",
        UserRole.ADMIN,
    )

    assert not client.session.exists(session_key)


@pytest.mark.django_db
def test_provision_dev_user_rejects_missing_password_entry(tmp_path, settings):
    settings.DEBUG = True
    credentials = tmp_path / ".env.local"
    credentials.write_text("UNRELATED=value\n", encoding="utf-8")

    with pytest.raises(CommandError, match="exactly one non-empty"):
        call_command(
            "provision_dev_user",
            "--email",
            "local-admin@example.test",
            "--credentials-file",
            str(credentials),
            "--role",
            UserRole.ADMIN,
        )


@pytest.mark.django_db
def test_provision_dev_user_refuses_non_debug(tmp_path, settings):
    settings.DEBUG = False
    credentials = tmp_path / ".env.local"
    credentials.write_text(
        "PODORIA_LOCAL_ADMIN_PASSWORD=local-only-password-placeholder\n",
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="only when DEBUG is enabled"):
        call_command(
            "provision_dev_user",
            "--email",
            "local-admin@example.test",
            "--credentials-file",
            str(credentials),
            "--role",
            UserRole.ADMIN,
        )
