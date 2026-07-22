import django.contrib.postgres.indexes
import django.db.models.functions.text
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("global_search", "0001_enable_pg_trgm"),
        ("patients", "0002_medical_profile"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="patient",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("first_name"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("last_name"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("public_number"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("normalized_phone"),
                    name="gin_trgm_ops",
                ),
                name="patients_global_search_gin",
            ),
        )
    ]
