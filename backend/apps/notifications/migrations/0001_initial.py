# Generated manually for TP-802 notification state.

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0004_user_phone"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("event_key", models.CharField(editable=False, max_length=255)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("appointment_arrived", "Пацієнт прибув"),
                            ("appointment_upcoming", "Запис незабаром"),
                            ("appointment_canceled", "Запис скасовано"),
                            ("work_item_overdue", "Справу прострочено"),
                            ("visit_payment_ready", "Прийом очікує оплати"),
                            ("password_reset_requested", "Запит на скидання пароля"),
                        ],
                        editable=False,
                        max_length=40,
                    ),
                ),
                ("title", models.CharField(editable=False, max_length=200)),
                ("message", models.CharField(editable=False, max_length=500)),
                (
                    "tone",
                    models.CharField(
                        choices=[
                            ("sage", "Зелений"),
                            ("sand", "Пісочний"),
                            ("blue", "Синій"),
                            ("lilac", "Ліловий"),
                            ("coral", "Кораловий"),
                        ],
                        default="sage",
                        editable=False,
                        max_length=16,
                    ),
                ),
                ("is_important", models.BooleanField(default=False, editable=False)),
                ("deep_link", models.CharField(default="/", editable=False, max_length=500)),
                (
                    "occurred_at",
                    models.DateTimeField(default=django.utils.timezone.now, editable=False),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "-created_at", "-id"],
                name="notif_recipient_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["recipient", "read_at", "-created_at"],
                name="notif_recipient_read_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                fields=("recipient", "event_key"),
                name="notif_recipient_event_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.CheckConstraint(
                condition=~models.Q(("event_key", "")),
                name="notif_event_key_nonempty",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.CheckConstraint(
                condition=models.Q(("deep_link__startswith", "/"))
                & ~models.Q(("deep_link__startswith", "//")),
                name="notif_deep_link_relative",
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.CheckConstraint(
                condition=models.Q(("read_at__isnull", True))
                | models.Q(("read_at__gte", models.F("created_at"))),
                name="notif_read_at_after_create",
            ),
        ),
    ]
