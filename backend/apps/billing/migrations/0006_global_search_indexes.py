import django.contrib.postgres.indexes
import django.db.models
import django.db.models.functions.text
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_cash_shift_close_history"),
        ("global_search", "0001_enable_pg_trgm"),
        ("patients", "0003_global_search_indexes"),
        ("visits", "0006_global_search_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="cashledgerentry",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("public_number"),
                    name="gin_trgm_ops",
                ),
                name="billing_ledger_search_gin",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("patient_public_number_snapshot"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("patient_name_snapshot"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("visit_public_number_snapshot"),
                    name="gin_trgm_ops",
                ),
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.functions.text.Upper("services_search_snapshot"),
                    name="gin_trgm_ops",
                ),
                name="billing_payment_search_gin",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass(
                    django.db.models.Func(
                        "patient_phone_snapshot",
                        django.db.models.Value("[^0-9]"),
                        django.db.models.Value(""),
                        django.db.models.Value("g"),
                        function="REGEXP_REPLACE",
                        output_field=django.db.models.CharField(),
                    ),
                    name="gin_trgm_ops",
                ),
                name="billing_phone_digits_gin",
            ),
        ),
    ]
