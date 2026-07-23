from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User, UserRole
from apps.audit.models import AuditEvent
from apps.audit.registry import AuditAction

INITIAL_PASSWORD = "Strong-initial-password-284!"  # noqa: S105


def credentials_file(tmp_path, *, email: str = "admin@example.test"):
    path = tmp_path / "initial-admin.env"
    path.write_text(
        "\n".join(
            (
                f"PODORIA_INITIAL_ADMIN_EMAIL={email}",
                f"PODORIA_INITIAL_ADMIN_PASSWORD={INITIAL_PASSWORD}",
                "",
            )
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.django_db
def test_provision_initial_admin_creates_admin_without_exposing_password(tmp_path):
    stdout = StringIO()

    call_command(
        "provision_initial_admin",
        "--credentials-file",
        str(credentials_file(tmp_path)),
        stdout=stdout,
    )

    user = User.objects.get(email="admin@example.test")
    assert user.role == UserRole.ADMIN
    assert user.is_active is True
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.check_password(INITIAL_PASSWORD)
    assert INITIAL_PASSWORD not in stdout.getvalue()
    event = AuditEvent.objects.get(action=AuditAction.USER_CREATED)
    assert event.actor_id == user.pk
    assert event.correlation_id == "production-bootstrap"
    assert INITIAL_PASSWORD not in str(event.after)


@pytest.mark.django_db
def test_provision_initial_admin_refuses_non_empty_user_table(tmp_path):
    User.objects.create_user(
        email="existing@example.test",
        password=INITIAL_PASSWORD,
        role=UserRole.ADMIN,
    )

    with pytest.raises(CommandError, match="empty user table"):
        call_command(
            "provision_initial_admin",
            "--credentials-file",
            str(credentials_file(tmp_path)),
        )


@pytest.mark.django_db
def test_provision_initial_admin_rejects_missing_password(tmp_path):
    path = tmp_path / "initial-admin.env"
    path.write_text("PODORIA_INITIAL_ADMIN_EMAIL=admin@example.test\n", encoding="utf-8")

    with pytest.raises(CommandError, match="PODORIA_INITIAL_ADMIN_PASSWORD"):
        call_command("provision_initial_admin", "--credentials-file", str(path))


@pytest.mark.django_db
def test_provision_initial_admin_rejects_invalid_email(tmp_path):
    with pytest.raises(CommandError, match="email is invalid"):
        call_command(
            "provision_initial_admin",
            "--credentials-file",
            str(credentials_file(tmp_path, email="not-an-email")),
        )
