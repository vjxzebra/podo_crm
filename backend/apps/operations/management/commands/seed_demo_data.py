import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.operations.demo_seed import (
    DEMO_CONFIRMATION,
    DEMO_SCALES,
    seed_demo_data,
)


class Command(BaseCommand):
    help = "Seed a deterministic, cross-domain demo dataset into an otherwise empty CRM database."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--confirm",
            required=True,
            help=f"Exact required token: {DEMO_CONFIRMATION}",
        )
        parser.add_argument(
            "--scale",
            choices=tuple(DEMO_SCALES),
            default="large",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["confirm"] != DEMO_CONFIRMATION:
            raise CommandError(f"Exact confirmation token {DEMO_CONFIRMATION} is required.")
        try:
            result = seed_demo_data(scale_name=options["scale"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, sort_keys=True))
