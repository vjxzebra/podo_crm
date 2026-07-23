# Generated manually for TP-301.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Patient",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("public_number", models.CharField(editable=False, max_length=24, unique=True)),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("phone", models.CharField(max_length=32)),
                (
                    "normalized_phone",
                    models.CharField(db_index=True, editable=False, max_length=16),
                ),
                ("birth_date", models.DateField(blank=True, null=True)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_patients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "primary_podologist",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="primary_patients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "constraints": [
                    models.CheckConstraint(
                        condition=~models.Q(public_number=""),
                        name="patients_public_number_not_empty",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(normalized_phone=""),
                        name="patients_normalized_phone_not_empty",
                    ),
                ],
            },
        ),
    ]
