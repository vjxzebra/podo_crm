from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.models import User, UserRole
from apps.accounts.services import revoke_user_sessions


class Command(BaseCommand):
    help = "Create or update one local development user. Refuses to run outside DEBUG."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--credentials-file", required=True)
        parser.add_argument("--password-key", default="PODORIA_LOCAL_ADMIN_PASSWORD")
        parser.add_argument("--role", required=True, choices=UserRole.values)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("provision_dev_user is available only when DEBUG is enabled.")

        credentials_path = Path(options["credentials_file"]).expanduser().resolve(strict=True)
        password_values: list[str] = []
        for line in credentials_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == options["password_key"]:
                password_values.append(value.strip().strip('"').strip("'"))
        if len(password_values) != 1 or not password_values[0]:
            raise CommandError(
                "Credentials file must contain exactly one non-empty password entry."
            )

        email = User.objects.normalize_login(options["email"])
        user = User.objects.filter(email__iexact=email).first()
        created = user is None
        if user is None:
            user = User(email=email)
        user.role = options["role"]
        user.first_name = options["first_name"]
        user.last_name = options["last_name"]
        user.is_active = True
        user.set_password(password_values[0])
        user.save()
        revoke_user_sessions(user)
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Development user {email} {action}."))
