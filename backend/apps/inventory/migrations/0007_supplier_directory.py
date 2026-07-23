import uuid
from typing import Any

import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower


def link_legacy_suppliers(apps: Any, schema_editor: Any) -> None:
    MaterialLot = apps.get_model("inventory", "MaterialLot")
    Supplier = apps.get_model("inventory", "Supplier")
    aliases: dict[str, Any] = {}
    for lot in MaterialLot.objects.exclude(supplier_name="").order_by("created_at", "id"):
        name = lot.supplier_name.strip()
        if not name:
            continue
        key = name.casefold()
        supplier = aliases.get(key)
        if supplier is None:
            supplier = Supplier.objects.filter(name__iexact=name).first()
            if supplier is None:
                supplier = Supplier.objects.create(name=name)
            aliases[key] = supplier
        lot.supplier_id = supplier.pk
        lot.save(update_fields=("supplier",))


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_global_search_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
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
                ("name", models.CharField(max_length=180)),
                ("contact_name", models.CharField(blank=True, max_length=180)),
                ("phone", models.CharField(blank=True, max_length=32)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("address", models.CharField(blank=True, max_length=300)),
                ("note", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-is_active", "name", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                Lower("name"),
                name="inventory_supplier_name_ci_unique",
            ),
        ),
        migrations.AddField(
            model_name="materiallot",
            name="supplier",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lots",
                to="inventory.supplier",
            ),
        ),
        migrations.RunPython(link_legacy_suppliers, migrations.RunPython.noop),
    ]
