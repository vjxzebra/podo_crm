from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.models import User, UserRole


class Command(BaseCommand):
    help = "Create or update one local development user. Refuses to run outside DEBUG."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--role", required=True, choices=UserRole.values)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("provision_dev_user is available only when DEBUG is enabled.")

        email = User.objects.normalize_login(options["email"])
        user = User.objects.filter(email__iexact=email).first()
        created = user is None
        if user is None:
            user = User(email=email)
        user.role = options["role"]
        user.first_name = options["first_name"]
        user.last_name = options["last_name"]
        user.is_active = True
        user.set_password(options["password"])
        user.save()
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Development user {email} {action}."))
