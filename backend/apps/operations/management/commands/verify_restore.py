import hashlib
import json
from collections.abc import Iterator
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.clinic.models import ClinicProfile
from apps.visits.models import VisitPhoto
from config import object_storage


def _key_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _object_references() -> Iterator[tuple[str, str]]:
    for object_key in ClinicProfile.objects.exclude(logo_object_key="").values_list(
        "logo_object_key", flat=True
    ):
        yield "clinic_logo", object_key
    for object_key, preview_object_key in VisitPhoto.objects.values_list(
        "object_key", "preview_object_key"
    ).iterator():
        yield "visit_photo", object_key
        if preview_object_key:
            yield "visit_photo_preview", preview_object_key


def build_restore_report() -> dict[str, Any]:
    executor = MigrationExecutor(connection)
    pending = [
        f"{migration.app_label}.{migration.name}"
        for migration, _backwards in executor.migration_plan(executor.loader.graph.leaf_nodes())
    ]

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE NOT convalidated
            ORDER BY conname
            """
        )
        invalid_constraints = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT COUNT(*) FROM django_migrations")
        migration_count = int(cursor.fetchone()[0])

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    references = list(_object_references())
    missing_objects = [
        {"kind": kind, "key_sha256": _key_digest(object_key)}
        for kind, object_key in references
        if not object_storage.private_object_exists(object_key=object_key)
    ]
    return {
        "status": "ok" if not (pending or invalid_constraints or missing_objects) else "failed",
        "migration_count": migration_count,
        "pending_migrations": pending,
        "invalid_constraints": invalid_constraints,
        "object_reference_count": len(references),
        "missing_object_count": len(missing_objects),
        "missing_objects": missing_objects,
    }


class Command(BaseCommand):
    help = "Verify migrations, PostgreSQL constraints and private-object references after restore."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args: Any, **options: Any) -> None:
        report = build_restore_report()
        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)
        if options["as_json"]:
            self.stdout.write(rendered)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Restore verification passed: "
                    f"{report['migration_count']} migrations, "
                    f"{report['object_reference_count']} object references."
                )
                if report["status"] == "ok"
                else rendered
            )
        if report["status"] != "ok":
            raise CommandError("Restore verification failed.")
