# Generated for TP-401 on 2026-07-21.

import uuid

import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.db.models.deletion
from django.conf import settings
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("clinic", "0003_status_schedule"),
        ("patients", "0002_medical_profile"),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.CreateModel(
            name="Appointment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("public_number", models.CharField(editable=False, max_length=24, unique=True)),
                (
                    "time_range",
                    django.contrib.postgres.fields.ranges.DateTimeRangeField(),
                ),
                ("duration_minutes", models.PositiveSmallIntegerField()),
                ("service_name_snapshot", models.CharField(max_length=160)),
                ("service_color_snapshot", models.CharField(max_length=7)),
                ("room_label_snapshot", models.CharField(max_length=100)),
                ("complaints", models.TextField(blank=True, max_length=4000)),
                ("has_no_complaints", models.BooleanField(default=False)),
                ("comment", models.TextField(blank=True, max_length=4000)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="patients.patient",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="clinic.room",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="clinic.service",
                    ),
                ),
                (
                    "specialist",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        db_column="status",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="clinic.appointmentstatusconfig",
                    ),
                ),
            ],
            options={
                "ordering": ("time_range", "specialist_id", "id"),
                "indexes": [
                    models.Index(fields=["specialist"], name="scheduling_specialist_idx"),
                    models.Index(fields=["room"], name="scheduling_room_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("duration_minutes__gt", 0)),
                        name="scheduling_appointment_duration_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("has_no_complaints", True), ("complaints", "")),
                            models.Q(
                                ("has_no_complaints", False),
                                models.Q(("complaints", ""), _negated=True),
                            ),
                            _connector="OR",
                        ),
                        name="scheduling_appointment_complaints_xor",
                    ),
                    django.contrib.postgres.constraints.ExclusionConstraint(
                        condition=models.Q(("status", "CANCELED"), _negated=True),
                        expressions=(
                            ("specialist", "="),
                            ("time_range", "&&"),
                        ),
                        name="scheduling_no_specialist_overlap",
                    ),
                    django.contrib.postgres.constraints.ExclusionConstraint(
                        condition=models.Q(("status", "CANCELED"), _negated=True),
                        expressions=(
                            ("room", "="),
                            ("time_range", "&&"),
                        ),
                        name="scheduling_no_room_overlap",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE scheduling_appointment "
                "ADD CONSTRAINT scheduling_time_range_non_empty "
                "CHECK (NOT isempty(time_range) AND lower(time_range) < upper(time_range));"
            ),
            reverse_sql=(
                "ALTER TABLE scheduling_appointment "
                "DROP CONSTRAINT IF EXISTS scheduling_time_range_non_empty;"
            ),
            state_operations=[],
        ),
    ]
