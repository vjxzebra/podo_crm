from pathlib import Path
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.models import User, UserRole
from apps.accounts.team_services import team_user_snapshot
from apps.audit.registry import AuditAction
from apps.audit.services import record_audit_event


def _credential_value(*, path: Path, key: str) -> str:
    values: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        candidate_key, value = stripped.split("=", 1)
        if candidate_key.strip() == key:
            values.append(value.strip().strip('"').strip("'"))
    if len(values) != 1 or not values[0]:
        raise CommandError(f"Credentials file must contain exactly one non-empty {key} entry.")
    return values[0]


class Command(BaseCommand):
    help = "Create the first production administrator from a credentials file."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--credentials-file", required=True)
        parser.add_argument("--email-key", default="PODORIA_INITIAL_ADMIN_EMAIL")
        parser.add_argument("--password-key", default="PODORIA_INITIAL_ADMIN_PASSWORD")
        parser.add_argument("--first-name", default="Перший")
        parser.add_argument("--last-name", default="Адміністратор")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if User.objects.select_for_update().exists():
            raise CommandError(
                "Initial administrator can be provisioned only into an empty user table."
            )

        credentials_path = Path(options["credentials_file"]).expanduser().resolve(strict=True)
        email = User.objects.normalize_login(
            _credential_value(path=credentials_path, key=options["email_key"])
        )
        password = _credential_value(path=credentials_path, key=options["password_key"])
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("Initial administrator email is invalid.") from exc

        user = User(
            email=email,
            first_name=options["first_name"].strip(),
            last_name=options["last_name"].strip(),
            role=UserRole.ADMIN,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        try:
            validate_password(password, user=user)
        except ValidationError as exc:
            raise CommandError("Initial administrator password does not pass validation.") from exc
        user.set_password(password)
        user.save()
        record_audit_event(
            actor=user,
            action=AuditAction.USER_CREATED,
            object_type="user",
            object_id=user.pk,
            object_label=user.display_name,
            correlation_id="production-bootstrap",
            before={},
            after=team_user_snapshot(user),
            description="Створено першого адміністратора production-середовища.",
        )
        self.stdout.write(self.style.SUCCESS("Initial production administrator created."))
