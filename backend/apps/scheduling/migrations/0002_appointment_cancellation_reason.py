# Generated for TP-403 on 2026-07-21.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scheduling", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="cancellation_reason",
            field=models.TextField(blank=True, max_length=1000),
        ),
    ]
