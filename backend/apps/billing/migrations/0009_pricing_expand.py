import uuid
from typing import Any

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def bridge_backfill_neutral_pricing(apps: Any, schema_editor: Any) -> None:
    """Make the expand schema readable by both the legacy and bridge images."""

    Receivable = apps.get_model("billing", "Receivable")
    Payment = apps.get_model("billing", "Payment")
    VisitPricing = apps.get_model("billing", "VisitPricing")

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            LOCK TABLE billing_receivable, billing_payment, billing_cashledgerentry,
                       billing_visitpricing, visits_visit, visits_visitserviceline
            IN SHARE ROW EXCLUSIVE MODE;
            """
        )
        cursor.execute(
            """
            SELECT receivable.id
              FROM billing_receivable AS receivable
              JOIN visits_visit AS visit ON visit.id = receivable.visit_id
              LEFT JOIN (
                    SELECT visit_id, COALESCE(SUM(price_minor * quantity), 0) AS gross_minor
                      FROM visits_visitserviceline
                     GROUP BY visit_id
              ) AS services ON services.visit_id = visit.id
             WHERE visit.total_minor IS DISTINCT FROM receivable.amount_minor
                OR COALESCE(services.gross_minor, 0) <> receivable.amount_minor
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot expand pricing: service, Visit and Receivable totals differ."
            )

    for receivable in Receivable.objects.order_by("created_at", "pk").iterator():
        is_settled = receivable.status != "OPEN" or receivable.amount_minor == 0
        VisitPricing.objects.get_or_create(
            visit_id=receivable.visit_id,
            defaults={
                "gross_minor": receivable.amount_minor,
                "discount_id": None,
                "discount_name_snapshot": "",
                "discount_percent_snapshot": None,
                "discount_source": "",
                "applied_by_id": None,
                "discount_amount_minor": 0,
                "net_minor": receivable.amount_minor,
                "is_legacy_backfill": True,
                "version": 1,
                "state": "SETTLED" if is_settled else "OPEN",
                "settled_at": receivable.updated_at if is_settled else None,
            },
        )

    # The legacy append-only guard predates these nullable expand columns.
    # Disable only that trigger for the locked, deterministic snapshot backfill.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE billing_payment DISABLE TRIGGER billing_payment_append_only")
    Payment.objects.filter(gross_total_minor_snapshot__isnull=True).update(
        gross_total_minor_snapshot=models.F("visit_total_minor_snapshot"),
        discount_id_snapshot=None,
        discount_name_snapshot="",
        discount_percent_snapshot=None,
        discount_source_snapshot="",
        discount_amount_minor_snapshot=0,
        net_total_minor_snapshot=models.F("visit_total_minor_snapshot"),
        pricing_snapshot_is_legacy=True,
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE billing_payment ENABLE TRIGGER billing_payment_append_only")


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0008_cash_drawer_contract"),
        ("discounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VisitPricing",
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
                ("gross_minor", models.PositiveBigIntegerField(editable=False)),
                (
                    "discount_name_snapshot",
                    models.CharField(blank=True, editable=False, max_length=120),
                ),
                (
                    "discount_percent_snapshot",
                    models.PositiveSmallIntegerField(blank=True, editable=False, null=True),
                ),
                (
                    "discount_source",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LOYALTY", "Програма лояльності"),
                            ("PODOLOGIST", "Подолог"),
                            ("RECEPTION", "Рецепція"),
                        ],
                        editable=False,
                        max_length=16,
                    ),
                ),
                (
                    "discount_amount_minor",
                    models.PositiveBigIntegerField(default=0, editable=False),
                ),
                ("net_minor", models.PositiveBigIntegerField(editable=False)),
                ("is_legacy_backfill", models.BooleanField(default=False, editable=False)),
                ("version", models.PositiveIntegerField(default=1)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("OPEN", "Очікує розрахунку"),
                            ("SETTLED", "Зафіксовано"),
                        ],
                        max_length=16,
                    ),
                ),
                ("settled_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "applied_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="applied_visit_discounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "discount",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="visit_pricings",
                        to="discounts.discount",
                    ),
                ),
                (
                    "visit",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pricing",
                        to="visits.visit",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "id"),
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("version__gt", 0)),
                        name="billing_pricing_version_positive",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("discount_amount_minor__lte", models.F("gross_minor"))),
                        name="billing_pricing_discount_lte_gross",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "net_minor",
                                models.F("gross_minor") - models.F("discount_amount_minor"),
                            )
                        ),
                        name="billing_pricing_net_formula",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("applied_by__isnull", True),
                                ("discount__isnull", True),
                                ("discount_amount_minor", 0),
                                ("discount_name_snapshot", ""),
                                ("discount_percent_snapshot__isnull", True),
                                ("discount_source", ""),
                            ),
                            models.Q(
                                ("discount__isnull", False),
                                ("discount_percent_snapshot__gte", 1),
                                ("discount_percent_snapshot__lte", 99),
                                (
                                    "discount_source__in",
                                    ["LOYALTY", "PODOLOGIST", "RECEPTION"],
                                ),
                                ("gross_minor__gt", 0),
                            ),
                            _connector="OR",
                        ),
                        name="billing_pricing_discount_consistent",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("settled_at__isnull", True), ("state", "OPEN")),
                            models.Q(("settled_at__isnull", False), ("state", "SETTLED")),
                            _connector="OR",
                        ),
                        name="billing_pricing_state_consistent",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="payment",
            name="gross_total_minor_snapshot",
            field=models.PositiveBigIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="discount_id_snapshot",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="discount_name_snapshot",
            field=models.CharField(blank=True, editable=False, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="discount_percent_snapshot",
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="discount_source_snapshot",
            field=models.CharField(
                blank=True,
                choices=[
                    ("LOYALTY", "Програма лояльності"),
                    ("PODOLOGIST", "Подолог"),
                    ("RECEPTION", "Рецепція"),
                ],
                editable=False,
                max_length=16,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="discount_amount_minor_snapshot",
            field=models.PositiveBigIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="net_total_minor_snapshot",
            field=models.PositiveBigIntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="pricing_snapshot_is_legacy",
            field=models.BooleanField(editable=False, null=True),
        ),
        migrations.RunPython(
            bridge_backfill_neutral_pricing,
            migrations.RunPython.noop,
        ),
    ]
