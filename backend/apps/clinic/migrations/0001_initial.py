import uuid

import django.db.models.functions.text
from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def seed_clinic(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    ClinicProfile = apps.get_model("clinic", "ClinicProfile")
    Room = apps.get_model("clinic", "Room")
    ClinicProfile.objects.get_or_create(
        key="clinic",
        defaults={
            "name": "Podoria Clinic",
            "phone": "+380 00 000 00 00",
            "email": "clinic@example.com",
            "address": "Укажіть адресу кабінету",
            "description": "Професійний догляд за стопами та нігтями.",
        },
    )
    Room.objects.get_or_create(name="Кабінет 1")


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ClinicProfile",
            fields=[
                (
                    "key",
                    models.CharField(
                        default="clinic",
                        editable=False,
                        max_length=16,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=160)),
                ("phone", models.CharField(max_length=32)),
                ("email", models.EmailField(max_length=254)),
                ("address", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, max_length=1000)),
                ("logo_object_key", models.CharField(blank=True, max_length=255)),
                ("logo_content_type", models.CharField(blank=True, max_length=32)),
                ("logo_size", models.PositiveIntegerField(blank=True, null=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("key", "clinic")), name="clinic_profile_singleton_key"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Room",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-is_active", "name", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("name"),
                        name="clinic_room_name_ci_unique",
                    )
                ],
            },
        ),
        migrations.RunPython(seed_clinic, migrations.RunPython.noop),
    ]
