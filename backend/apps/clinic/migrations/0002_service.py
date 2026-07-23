import uuid

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("clinic", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Service",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code", models.CharField(max_length=32)),
                ("name", models.CharField(max_length=160)),
                ("duration_minutes", models.PositiveSmallIntegerField()),
                ("price_minor", models.PositiveBigIntegerField()),
                ("color", models.CharField(default="#4F46E5", max_length=7)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-is_active", "name", "code", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        django.db.models.functions.text.Lower("code"),
                        name="clinic_service_code_ci_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("duration_minutes__gt", 0)),
                        name="clinic_service_duration_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("price_minor__gte", 0)),
                        name="clinic_service_price_non_negative",
                    ),
                ],
            },
        )
    ]
