import django.contrib.postgres.indexes
import django.db.models.functions.text
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("global_search", "0001_enable_pg_trgm"),
        ("inventory", "0005_inventoryoperation_inventory_operation_visit_source_consistent"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="material",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("sku"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("name"),
                    name="gin_trgm_ops",
                ),
                name="inventory_global_search_gin",
            ),
        )
    ]
