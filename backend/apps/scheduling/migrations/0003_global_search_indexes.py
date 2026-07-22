import django.contrib.postgres.indexes
import django.db.models.functions.text
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("global_search", "0001_enable_pg_trgm"),
        ("patients", "0003_global_search_indexes"),
        ("scheduling", "0002_appointment_cancellation_reason"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="appointment",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("public_number"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("service_name_snapshot"),
                    name="gin_trgm_ops",
                ),
                name="scheduling_global_search_gin",
            ),
        )
    ]
