# Generated for appointment multi-service support on 2026-08-03.

from typing import Any

import django.db.models.deletion
from django.db import migrations, models


def copy_primary_services(apps: Any, schema_editor: Any) -> None:
    Appointment = apps.get_model("scheduling", "Appointment")
    AppointmentServiceLine = apps.get_model("scheduling", "AppointmentServiceLine")
    lines = (
        AppointmentServiceLine(
            appointment_id=appointment.pk,
            service_id=appointment.service_id,
            position=0,
            duration_minutes=appointment.duration_minutes,
            service_name_snapshot=appointment.service_name_snapshot,
            service_color_snapshot=appointment.service_color_snapshot,
        )
        for appointment in Appointment.objects.all().iterator(chunk_size=500)
    )
    AppointmentServiceLine.objects.bulk_create(lines, batch_size=500)


def remove_service_lines(apps: Any, schema_editor: Any) -> None:
    AppointmentServiceLine = apps.get_model("scheduling", "AppointmentServiceLine")
    AppointmentServiceLine.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("clinic", "0003_status_schedule"),
        ("scheduling", "0003_global_search_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppointmentServiceLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("position", models.PositiveSmallIntegerField()),
                ("duration_minutes", models.PositiveSmallIntegerField()),
                ("service_name_snapshot", models.CharField(max_length=160)),
                ("service_color_snapshot", models.CharField(max_length=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "appointment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_lines",
                        to="scheduling.appointment",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointment_service_lines",
                        to="clinic.service",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("appointment", "service"),
                        name="scheduling_appointment_service_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("appointment", "position"),
                        name="scheduling_appointment_service_position_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("duration_minutes__gt", 0)),
                        name="scheduling_appointment_service_duration_positive",
                    ),
                ],
            },
        ),
        migrations.RunPython(copy_primary_services, remove_service_lines),
    ]
