import uuid
from typing import Any

import django.db.models.deletion
from django.db import migrations, models


def settle_zero_total_receivables(apps: Any, schema_editor: Any) -> None:
    Receivable = apps.get_model("billing", "Receivable")
    Receivable.objects.filter(amount_minor=0, status="OPEN").update(status="PAID")


def reject_reverse_with_payments(apps: Any, schema_editor: Any) -> None:
    Payment = apps.get_model("billing", "Payment")
    if Payment.objects.exists():
        raise RuntimeError("Cannot reverse billing.0003 while immutable payment records exist.")


CREATE_RECEIVABLE_LIFECYCLE_TRIGGER = """
CREATE OR REPLACE FUNCTION billing_guard_receivable_lifecycle()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Receivables cannot be deleted.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF (NEW.amount_minor = 0 AND NEW.status = 'PAID')
           OR (NEW.amount_minor > 0 AND NEW.status = 'OPEN') THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Receivable initial state is inconsistent.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.visit_id IS DISTINCT FROM NEW.visit_id
       OR OLD.amount_minor IS DISTINCT FROM NEW.amount_minor
       OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'Receivable identity and amount are immutable.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF OLD.status = 'OPEN' AND NEW.status = 'PAID' THEN
        IF OLD.amount_minor = 0
           OR EXISTS (
               SELECT 1
               FROM billing_payment
               WHERE receivable_id = OLD.id
           ) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'A positive receivable requires a payment before settlement.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RAISE EXCEPTION 'TP-702 receivables only transition from OPEN to PAID.'
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER billing_receivable_lifecycle
BEFORE INSERT OR UPDATE OR DELETE ON billing_receivable
FOR EACH ROW EXECUTE FUNCTION billing_guard_receivable_lifecycle();
"""

DROP_RECEIVABLE_LIFECYCLE_TRIGGER = """
DROP TRIGGER IF EXISTS billing_receivable_lifecycle ON billing_receivable;
DROP FUNCTION IF EXISTS billing_guard_receivable_lifecycle();
"""

CREATE_LEDGER_INSERT_TRIGGER = """
CREATE OR REPLACE FUNCTION billing_validate_cash_ledger_entry_insert()
RETURNS trigger AS $$
DECLARE
    shift_status varchar(16);
    shift_employee_id bigint;
BEGIN
    SELECT status, employee_id
      INTO shift_status, shift_employee_id
      FROM billing_cashshift
     WHERE id = NEW.cash_shift_id
     FOR UPDATE;

    IF NOT FOUND OR shift_status <> 'OPEN' THEN
        RAISE EXCEPTION 'Cash ledger entries require an open shift.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF shift_employee_id <> NEW.created_by_id THEN
        RAISE EXCEPTION 'Cash ledger entry actor must own the shift.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER billing_cash_ledger_entry_insert_guard
BEFORE INSERT ON billing_cashledgerentry
FOR EACH ROW EXECUTE FUNCTION billing_validate_cash_ledger_entry_insert();
"""

DROP_LEDGER_INSERT_TRIGGER = """
DROP TRIGGER IF EXISTS billing_cash_ledger_entry_insert_guard
    ON billing_cashledgerentry;
DROP FUNCTION IF EXISTS billing_validate_cash_ledger_entry_insert();
"""

CREATE_PAYMENT_GUARD_TRIGGER = """
CREATE OR REPLACE FUNCTION billing_guard_payment()
RETURNS trigger AS $$
DECLARE
    ledger_kind varchar(16);
    ledger_amount bigint;
    ledger_actor_id bigint;
    shift_status varchar(16);
    shift_employee_id bigint;
    receivable_amount bigint;
    receivable_status varchar(16);
    visit_status varchar(16);
    visit_public_number varchar(24);
    visit_completed_at timestamptz;
    visit_payment_handoff_requested boolean;
    visit_total_minor bigint;
    patient_id uuid;
    patient_public_number varchar(24);
    patient_name varchar(255);
    patient_phone varchar(32);
    specialist_id bigint;
    specialist_name varchar(255);
    employee_name varchar(255);
    employee_email varchar(254);
    source_services jsonb;
    source_services_search text;
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Payments are append-only.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    SELECT ledger.kind,
           ledger.amount_minor,
           ledger.created_by_id,
           shift.status,
           shift.employee_id,
           receivable.amount_minor,
           receivable.status,
           visit.status,
           visit.public_number,
           visit.completed_at,
           visit.payment_handoff_requested,
           visit.total_minor,
           patient.id,
           patient.public_number,
           BTRIM(CONCAT_WS(' ', patient.first_name, patient.last_name)),
           patient.phone,
           visit.specialist_id,
           COALESCE(
               NULLIF(BTRIM(CONCAT_WS(' ', specialist.first_name, specialist.last_name)), ''),
               specialist.email
           ),
           COALESCE(
               NULLIF(BTRIM(CONCAT_WS(' ', actor.first_name, actor.last_name)), ''),
               actor.email
           ),
           actor.email,
           (
               SELECT COALESCE(
                   jsonb_agg(
                       jsonb_build_object(
                           'id', line.id::text,
                           'code', line.service_code,
                           'name', line.service_name,
                           'quantity', line.quantity,
                           'unit_price_minor', line.price_minor,
                           'line_total_minor', line.price_minor * line.quantity
                       )
                       ORDER BY line.is_primary DESC,
                                line.service_name,
                                line.service_code,
                                line.id
                   ),
                   '[]'::jsonb
               )
               FROM visits_visitserviceline AS line
               WHERE line.visit_id = visit.id
           ),
           (
               SELECT COALESCE(
                   string_agg(
                       line.service_code || ' ' || line.service_name,
                       ' '
                       ORDER BY line.is_primary DESC,
                                line.service_name,
                                line.service_code,
                                line.id
                   ),
                   ''
               )
               FROM visits_visitserviceline AS line
               WHERE line.visit_id = visit.id
           )
      INTO ledger_kind,
           ledger_amount,
           ledger_actor_id,
           shift_status,
           shift_employee_id,
           receivable_amount,
           receivable_status,
           visit_status,
           visit_public_number,
           visit_completed_at,
           visit_payment_handoff_requested,
           visit_total_minor,
           patient_id,
           patient_public_number,
           patient_name,
           patient_phone,
           specialist_id,
           specialist_name,
           employee_name,
           employee_email,
           source_services,
           source_services_search
      FROM billing_cashledgerentry AS ledger
      JOIN billing_cashshift AS shift ON shift.id = ledger.cash_shift_id
      JOIN billing_receivable AS receivable ON receivable.id = NEW.receivable_id
      JOIN visits_visit AS visit ON visit.id = receivable.visit_id
      JOIN patients_patient AS patient ON patient.id = visit.patient_id
      JOIN accounts_user AS specialist ON specialist.id = visit.specialist_id
      JOIN accounts_user AS actor ON actor.id = ledger.created_by_id
     WHERE ledger.id = NEW.ledger_entry_id;

    IF NOT FOUND
       OR ledger_kind <> 'PAYMENT'
       OR ledger_amount <> receivable_amount
       OR receivable_amount <= 0
       OR receivable_status <> 'OPEN'
       OR visit_status <> 'COMPLETED'
       OR visit_completed_at IS NULL
       OR visit_total_minor IS NULL
       OR visit_total_minor <> receivable_amount
       OR shift_status <> 'OPEN'
       OR ledger_actor_id <> shift_employee_id
       OR NEW.visit_public_number_snapshot <> visit_public_number
       OR NEW.visit_completed_at_snapshot <> visit_completed_at
       OR NEW.visit_payment_handoff_requested_snapshot
            IS DISTINCT FROM visit_payment_handoff_requested
       OR NEW.visit_total_minor_snapshot <> visit_total_minor
       OR NEW.patient_id_snapshot <> patient_id
       OR NEW.patient_public_number_snapshot <> patient_public_number
       OR NEW.patient_name_snapshot <> patient_name
       OR NEW.patient_phone_snapshot <> patient_phone
       OR NEW.specialist_id_snapshot <> specialist_id
       OR NEW.specialist_name_snapshot <> specialist_name
       OR NEW.employee_name_snapshot <> employee_name
       OR NEW.employee_email_snapshot <> employee_email
       OR NEW.services_snapshot <> source_services
       OR NEW.services_search_snapshot <> source_services_search
       OR jsonb_typeof(NEW.services_snapshot) <> 'array' THEN
        RAISE EXCEPTION 'Payment facts do not match the immutable billing source.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER billing_payment_append_only
BEFORE INSERT OR UPDATE OR DELETE ON billing_payment
FOR EACH ROW EXECUTE FUNCTION billing_guard_payment();
"""

DROP_PAYMENT_GUARD_TRIGGER = """
DROP TRIGGER IF EXISTS billing_payment_append_only ON billing_payment;
DROP FUNCTION IF EXISTS billing_guard_payment();
"""

CREATE_PAYMENT_AGGREGATE_TRIGGER = """
CREATE OR REPLACE FUNCTION billing_validate_payment_aggregate_at_commit()
RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM billing_payment AS payment
          JOIN billing_receivable AS receivable
            ON receivable.id = payment.receivable_id
         WHERE payment.ledger_entry_id = NEW.id
           AND receivable.status = 'PAID'
    ) THEN
        RAISE EXCEPTION 'PAYMENT ledger rows require one settled typed payment.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER billing_payment_ledger_typed
AFTER INSERT ON billing_cashledgerentry
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
WHEN (NEW.kind = 'PAYMENT')
EXECUTE FUNCTION billing_validate_payment_aggregate_at_commit();

CREATE OR REPLACE FUNCTION billing_validate_payment_settlement_at_commit()
RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM billing_payment AS payment
          JOIN billing_receivable AS receivable
            ON receivable.id = payment.receivable_id
         WHERE payment.id = NEW.id
           AND receivable.status = 'PAID'
    ) THEN
        RAISE EXCEPTION 'Typed payments require a settled receivable.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER billing_payment_receivable_settled
AFTER INSERT ON billing_payment
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION billing_validate_payment_settlement_at_commit();
"""

DROP_PAYMENT_AGGREGATE_TRIGGER = """
DROP TRIGGER IF EXISTS billing_payment_ledger_typed ON billing_cashledgerentry;
DROP TRIGGER IF EXISTS billing_payment_receivable_settled ON billing_payment;
DROP FUNCTION IF EXISTS billing_validate_payment_aggregate_at_commit();
DROP FUNCTION IF EXISTS billing_validate_payment_settlement_at_commit();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_cash_shift_ledger_foundation"),
    ]

    operations = [
        migrations.RunPython(
            settle_zero_total_receivables,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="receivable",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(amount_minor=0, status="PAID")
                    | models.Q(
                        amount_minor__gt=0,
                        status__in=("OPEN", "PAID", "REFUNDED"),
                    )
                ),
                name="billing_receivable_amount_status_consistent",
            ),
        ),
        migrations.CreateModel(
            name="Payment",
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
                ("comment", models.TextField(blank=True, editable=False)),
                ("patient_id_snapshot", models.UUIDField(editable=False)),
                (
                    "patient_public_number_snapshot",
                    models.CharField(editable=False, max_length=24),
                ),
                (
                    "patient_name_snapshot",
                    models.CharField(editable=False, max_length=255),
                ),
                (
                    "patient_phone_snapshot",
                    models.CharField(editable=False, max_length=32),
                ),
                (
                    "visit_public_number_snapshot",
                    models.CharField(editable=False, max_length=24),
                ),
                ("visit_completed_at_snapshot", models.DateTimeField(editable=False)),
                (
                    "visit_payment_handoff_requested_snapshot",
                    models.BooleanField(editable=False),
                ),
                (
                    "visit_total_minor_snapshot",
                    models.PositiveBigIntegerField(editable=False),
                ),
                (
                    "specialist_id_snapshot",
                    models.PositiveBigIntegerField(editable=False),
                ),
                (
                    "specialist_name_snapshot",
                    models.CharField(editable=False, max_length=255),
                ),
                (
                    "employee_name_snapshot",
                    models.CharField(editable=False, max_length=255),
                ),
                (
                    "employee_email_snapshot",
                    models.EmailField(editable=False, max_length=254),
                ),
                ("services_snapshot", models.JSONField(default=list, editable=False)),
                ("services_search_snapshot", models.TextField(editable=False)),
                (
                    "ledger_entry",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_records",
                        to="billing.cashledgerentry",
                    ),
                ),
                (
                    "receivable",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_records",
                        to="billing.receivable",
                    ),
                ),
            ],
            options={
                "ordering": ("-id",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("ledger_entry",),
                        name="billing_payment_ledger_unique",
                    ),
                    models.UniqueConstraint(
                        fields=("receivable",),
                        name="billing_payment_receivable_unique",
                    ),
                    models.CheckConstraint(
                        condition=(
                            ~models.Q(patient_public_number_snapshot="")
                            & ~models.Q(patient_name_snapshot="")
                            & ~models.Q(visit_public_number_snapshot="")
                            & ~models.Q(specialist_name_snapshot="")
                            & ~models.Q(employee_name_snapshot="")
                            & ~models.Q(employee_email_snapshot="")
                            & ~models.Q(services_search_snapshot="")
                        ),
                        name="billing_payment_snapshot_identity_nonempty",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            CREATE_RECEIVABLE_LIFECYCLE_TRIGGER,
            DROP_RECEIVABLE_LIFECYCLE_TRIGGER,
        ),
        migrations.RunSQL(
            CREATE_LEDGER_INSERT_TRIGGER,
            DROP_LEDGER_INSERT_TRIGGER,
        ),
        migrations.RunSQL(
            CREATE_PAYMENT_GUARD_TRIGGER,
            DROP_PAYMENT_GUARD_TRIGGER,
        ),
        migrations.RunSQL(
            CREATE_PAYMENT_AGGREGATE_TRIGGER,
            DROP_PAYMENT_AGGREGATE_TRIGGER,
        ),
        migrations.RunPython(
            migrations.RunPython.noop,
            reject_reverse_with_payments,
        ),
    ]
