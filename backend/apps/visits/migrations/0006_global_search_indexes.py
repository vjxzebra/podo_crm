import django.contrib.postgres.indexes
import django.db.models.functions.text
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("global_search", "0001_enable_pg_trgm"),
        ("visits", "0005_add_patient_history_index"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="visit",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("public_number"),
                    name="gin_trgm_ops",
                ),
                name="visits_number_search_gin",
            ),
        ),
        migrations.AddIndex(
            model_name="visitserviceline",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("service_code"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("service_name"),
                    name="gin_trgm_ops",
                ),
                name="visits_service_search_gin",
            ),
        ),
    ]
