# Generated manually for TP-1017 recipient Notification Telegram delivery.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking_requests", "0006_workitemtelegramdelivery"),
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationTelegramDelivery",
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
                ("chat_id", models.BigIntegerField()),
                ("message_id", models.BigIntegerField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("SENT", "Sent"),
                            ("RETRY", "Retry"),
                            ("PERMANENT_FAILURE", "Permanent failure"),
                        ],
                        default="PENDING",
                        max_length=32,
                    ),
                ),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, max_length=64)),
                ("error_message", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True, editable=False)),
                (
                    "notification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="telegram_deliveries",
                        to="notifications.notification",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notification_deliveries",
                        to="booking_requests.telegramsubscription",
                    ),
                ),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.AddIndex(
            model_name="notificationtelegramdelivery",
            index=models.Index(
                fields=["status", "next_attempt_at", "created_at"],
                name="notif_tg_delivery_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notificationtelegramdelivery",
            index=models.Index(
                fields=["notification", "status"],
                name="notif_tg_notification_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="notificationtelegramdelivery",
            constraint=models.UniqueConstraint(
                fields=("notification", "subscription"),
                name="notif_tg_notif_sub_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="notificationtelegramdelivery",
            constraint=models.CheckConstraint(
                condition=models.Q(("attempt_count__gte", 0)),
                name="notif_tg_attempt_nonnegative",
            ),
        ),
    ]
