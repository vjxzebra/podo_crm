from importlib import import_module
from typing import Any

import django.db.models.expressions
from django.db import migrations, models


def backfill_pricing_and_payment_snapshots(apps: Any, schema_editor: Any) -> None:
    Receivable = apps.get_model("billing", "Receivable")
    Payment = apps.get_model("billing", "Payment")
    VisitPricing = apps.get_model("billing", "VisitPricing")

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            LOCK TABLE billing_receivable, billing_payment, billing_refund,
                       billing_cashledgerentry, billing_visitpricing,
                       visits_visit, visits_visitserviceline
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
                "Cannot activate pricing: service, Visit and Receivable totals differ."
            )
        cursor.execute(
            """
            SELECT visit.id
              FROM visits_visit AS visit
              LEFT JOIN billing_receivable AS receivable
                ON receivable.visit_id = visit.id
             WHERE visit.status = 'COMPLETED'
               AND (visit.completed_at IS NULL OR receivable.id IS NULL)
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot activate pricing: every completed Visit requires one Receivable."
            )
        cursor.execute(
            """
            SELECT receivable.id
              FROM billing_receivable AS receivable
              JOIN visits_visit AS visit ON visit.id = receivable.visit_id
             WHERE visit.status <> 'COMPLETED'
                OR visit.completed_at IS NULL
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot activate pricing: Receivables must belong to completed Visits."
            )
        cursor.execute(
            """
            SELECT ledger.id
              FROM billing_cashledgerentry AS ledger
              LEFT JOIN billing_payment AS payment
                ON payment.ledger_entry_id = ledger.id
             WHERE ledger.kind = 'PAYMENT'
               AND payment.id IS NULL
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError("Cannot activate pricing: an untyped PAYMENT ledger entry exists.")
        cursor.execute(
            """
            SELECT receivable.id
              FROM billing_receivable AS receivable
              LEFT JOIN billing_payment AS payment
                ON payment.receivable_id = receivable.id
              LEFT JOIN billing_cashledgerentry AS ledger
                ON ledger.id = payment.ledger_entry_id
             GROUP BY receivable.id, receivable.status, receivable.amount_minor
            HAVING (receivable.status = 'OPEN' AND COUNT(payment.id) <> 0)
                OR (
                    receivable.status IN ('PAID', 'REFUNDED')
                    AND receivable.amount_minor > 0
                    AND (
                        COUNT(payment.id) <> 1
                        OR COUNT(payment.id) FILTER (
                            WHERE ledger.kind = 'PAYMENT'
                              AND ledger.amount_minor = receivable.amount_minor
                        ) <> 1
                    )
                )
                OR (receivable.amount_minor = 0 AND COUNT(payment.id) <> 0)
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot activate pricing: Receivable settlement lacks exact typed coverage."
            )
        cursor.execute(
            """
            SELECT receivable.id
              FROM billing_receivable AS receivable
              LEFT JOIN billing_payment AS payment
                ON payment.receivable_id = receivable.id
              LEFT JOIN billing_refund AS refund
                ON refund.original_payment_id = payment.id
              LEFT JOIN billing_cashledgerentry AS ledger
                ON ledger.id = refund.ledger_entry_id
             GROUP BY receivable.id, receivable.status, receivable.amount_minor
            HAVING (
                    receivable.status = 'REFUNDED'
                    AND (
                        COUNT(refund.id) <> 1
                        OR COUNT(refund.id) FILTER (
                            WHERE ledger.kind = 'REFUND'
                              AND ledger.amount_minor = receivable.amount_minor
                        ) <> 1
                    )
                )
                OR (receivable.status <> 'REFUNDED' AND COUNT(refund.id) <> 0)
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot activate pricing: Receivable refund coverage is inconsistent."
            )
        cursor.execute(
            """
            SELECT payment.id
              FROM billing_payment AS payment
              JOIN billing_cashledgerentry AS ledger ON ledger.id = payment.ledger_entry_id
              JOIN billing_receivable AS receivable ON receivable.id = payment.receivable_id
             WHERE ledger.amount_minor <> receivable.amount_minor
                OR payment.visit_total_minor_snapshot <> receivable.amount_minor
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError("Cannot activate pricing over inconsistent legacy payment facts.")
        cursor.execute(
            """
            SELECT pricing.id
              FROM billing_visitpricing AS pricing
              LEFT JOIN billing_receivable AS receivable
                ON receivable.visit_id = pricing.visit_id
              LEFT JOIN visits_visit AS visit ON visit.id = pricing.visit_id
              LEFT JOIN (
                    SELECT visit_id, COALESCE(SUM(price_minor * quantity), 0) AS gross_minor
                      FROM visits_visitserviceline
                     GROUP BY visit_id
              ) AS services ON services.visit_id = pricing.visit_id
             WHERE receivable.id IS NULL
                OR visit.id IS NULL
                OR pricing.gross_minor <> COALESCE(services.gross_minor, 0)
                OR pricing.net_minor <> receivable.amount_minor
                OR pricing.net_minor <> visit.total_minor
                OR (
                    receivable.status = 'OPEN'
                    AND (pricing.state <> 'OPEN' OR pricing.net_minor = 0)
                )
                OR (
                    receivable.status <> 'OPEN'
                    AND pricing.state <> 'SETTLED'
                )
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot activate pricing: an existing bridge pricing row is inconsistent."
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

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
              FROM billing_payment
             WHERE (
                    gross_total_minor_snapshot IS NULL
                 OR discount_name_snapshot IS NULL
                 OR discount_source_snapshot IS NULL
                 OR discount_amount_minor_snapshot IS NULL
                 OR net_total_minor_snapshot IS NULL
                 OR pricing_snapshot_is_legacy IS NULL
             )
               AND NOT (
                    gross_total_minor_snapshot IS NULL
                AND discount_name_snapshot IS NULL
                AND discount_source_snapshot IS NULL
                AND discount_amount_minor_snapshot IS NULL
                AND net_total_minor_snapshot IS NULL
                AND pricing_snapshot_is_legacy IS NULL
             )
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot activate pricing: a Payment has partial bridge pricing snapshots."
            )
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

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
              FROM billing_receivable AS receivable
              LEFT JOIN billing_visitpricing AS pricing
                ON pricing.visit_id = receivable.visit_id
             WHERE pricing.id IS NULL
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError("Pricing backfill left a receivable without canonical pricing.")
        cursor.execute(
            """
            SELECT 1
              FROM billing_payment
             WHERE gross_total_minor_snapshot IS NULL
                OR discount_name_snapshot IS NULL
                OR discount_source_snapshot IS NULL
                OR discount_amount_minor_snapshot IS NULL
                OR net_total_minor_snapshot IS NULL
                OR pricing_snapshot_is_legacy IS NULL
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError("Payment pricing snapshot backfill is incomplete.")
        cursor.execute(
            """
            SELECT payment.id
              FROM billing_payment AS payment
              JOIN billing_receivable AS receivable
                ON receivable.id = payment.receivable_id
              JOIN billing_cashledgerentry AS ledger
                ON ledger.id = payment.ledger_entry_id
              JOIN billing_visitpricing AS pricing
                ON pricing.visit_id = receivable.visit_id
             WHERE ledger.kind <> 'PAYMENT'
                OR ledger.amount_minor <> pricing.net_minor
                OR payment.visit_total_minor_snapshot <> pricing.net_minor
                OR payment.gross_total_minor_snapshot <> pricing.gross_minor
                OR payment.discount_id_snapshot IS DISTINCT FROM pricing.discount_id
                OR payment.discount_name_snapshot IS DISTINCT FROM pricing.discount_name_snapshot
                OR payment.discount_percent_snapshot
                   IS DISTINCT FROM pricing.discount_percent_snapshot
                OR payment.discount_source_snapshot IS DISTINCT FROM pricing.discount_source
                OR payment.discount_amount_minor_snapshot <> pricing.discount_amount_minor
                OR payment.net_total_minor_snapshot <> pricing.net_minor
             LIMIT 1;
            """
        )
        if cursor.fetchone() is not None:
            raise RuntimeError(
                "Cannot activate pricing: Payment snapshots differ from canonical pricing."
            )


def reject_reverse_after_pricing_activation(apps: Any, schema_editor: Any) -> None:
    Payment = apps.get_model("billing", "Payment")
    VisitPricing = apps.get_model("billing", "VisitPricing")
    PatientLoyaltyState = apps.get_model("discounts", "PatientLoyaltyState")
    VisitLoyaltyEvent = apps.get_model("discounts", "VisitLoyaltyEvent")

    unsafe_pricing = VisitPricing.objects.filter(
        models.Q(is_legacy_backfill=False)
        | ~models.Q(version=1)
        | models.Q(discount_id__isnull=False)
        | ~models.Q(discount_name_snapshot="")
        | models.Q(discount_percent_snapshot__isnull=False)
        | ~models.Q(discount_source="")
        | ~models.Q(discount_amount_minor=0)
        | ~models.Q(net_minor=models.F("gross_minor"))
    ).exists()
    if (
        unsafe_pricing
        or Payment.objects.filter(pricing_snapshot_is_legacy=False).exists()
        or PatientLoyaltyState.objects.exists()
        or VisitLoyaltyEvent.objects.exists()
    ):
        raise RuntimeError(
            "Cannot reverse pricing after loyalty, repricing, settlement or pricing-aware payment."
        )


FORWARD_SQL = r"""
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
       OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'Receivable identity is immutable.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF OLD.amount_minor IS DISTINCT FROM NEW.amount_minor THEN
        IF OLD.status = 'OPEN'
           AND NEW.status = 'OPEN'
           AND NEW.amount_minor > 0
           AND NOT EXISTS (
               SELECT 1 FROM billing_payment WHERE receivable_id = OLD.id
           ) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Only an unpaid open receivable can be repriced.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF OLD.status = 'OPEN' AND NEW.status = 'PAID' THEN
        IF OLD.amount_minor = 0
           OR EXISTS (
               SELECT 1 FROM billing_payment WHERE receivable_id = OLD.id
           ) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'A positive receivable requires a payment before settlement.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF OLD.status = 'PAID' AND NEW.status = 'REFUNDED' THEN
        IF OLD.amount_minor > 0
           AND EXISTS (
               SELECT 1
                 FROM billing_refund AS refund
                 JOIN billing_payment AS payment ON payment.id = refund.original_payment_id
                WHERE payment.receivable_id = OLD.id
           ) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'A paid receivable requires its full typed refund.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RAISE EXCEPTION 'Receivables only transition OPEN to PAID to REFUNDED.'
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION billing_guard_visit_pricing()
RETURNS trigger AS $$
DECLARE
    service_gross bigint;
    current_name varchar(120);
    current_percent smallint;
    expected_discount bigint;
    selection_changed boolean;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Visit pricing cannot be deleted.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.is_legacy_backfill THEN
            RAISE EXCEPTION 'Legacy pricing provenance is reserved for the contract backfill.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF (NEW.net_minor = 0 AND NEW.state <> 'SETTLED')
           OR (NEW.net_minor > 0 AND NEW.state <> 'OPEN') THEN
            RAISE EXCEPTION 'New pricing lifecycle does not match its net amount.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        selection_changed := TRUE;
    ELSE
        IF OLD.state = 'SETTLED' THEN
            RAISE EXCEPTION 'Settled visit pricing is immutable.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.visit_id IS DISTINCT FROM OLD.visit_id
           OR NEW.gross_minor IS DISTINCT FROM OLD.gross_minor
           OR NEW.is_legacy_backfill IS DISTINCT FROM OLD.is_legacy_backfill
           OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'Visit pricing identity, gross and provenance are immutable.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.version <> OLD.version + 1 THEN
            RAISE EXCEPTION 'Visit pricing version must advance exactly once.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.state NOT IN ('OPEN', 'SETTLED') THEN
            RAISE EXCEPTION 'Invalid visit pricing lifecycle transition.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        selection_changed := NEW.discount_id IS DISTINCT FROM OLD.discount_id
            OR NEW.discount_name_snapshot IS DISTINCT FROM OLD.discount_name_snapshot
            OR NEW.discount_percent_snapshot IS DISTINCT FROM OLD.discount_percent_snapshot
            OR NEW.discount_source IS DISTINCT FROM OLD.discount_source
            OR NEW.applied_by_id IS DISTINCT FROM OLD.applied_by_id
            OR NEW.discount_amount_minor IS DISTINCT FROM OLD.discount_amount_minor
            OR NEW.net_minor IS DISTINCT FROM OLD.net_minor;
    END IF;

    SELECT COALESCE(SUM(price_minor * quantity), 0)
      INTO service_gross
      FROM visits_visitserviceline
     WHERE visit_id = NEW.visit_id;
    IF service_gross <> NEW.gross_minor THEN
        RAISE EXCEPTION 'Visit pricing gross must equal immutable service line totals.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF NEW.gross_minor = 0 AND NEW.discount_id IS NOT NULL THEN
        RAISE EXCEPTION 'Zero-gross pricing cannot carry a discount identity.'
            USING ERRCODE = 'integrity_constraint_violation';
    ELSIF NEW.discount_id IS NULL THEN
        IF NEW.discount_name_snapshot <> ''
           OR NEW.discount_percent_snapshot IS NOT NULL
           OR NEW.discount_source <> ''
           OR NEW.applied_by_id IS NOT NULL
           OR NEW.discount_amount_minor <> 0
           OR NEW.net_minor <> NEW.gross_minor THEN
            RAISE EXCEPTION 'No-discount pricing fields are inconsistent.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    ELSE
        IF selection_changed THEN
            SELECT name, percent
              INTO current_name, current_percent
              FROM discounts_discount
             WHERE id = NEW.discount_id AND is_active = TRUE;
            IF current_name IS NULL
               OR current_name IS DISTINCT FROM NEW.discount_name_snapshot
               OR current_percent IS DISTINCT FROM NEW.discount_percent_snapshot THEN
                RAISE EXCEPTION 'Visit pricing discount snapshots are invalid.'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
        END IF;
        expected_discount := (NEW.gross_minor * NEW.discount_percent_snapshot) / 100;
        IF NEW.discount_amount_minor <> expected_discount
           OR NEW.net_minor <> NEW.gross_minor - expected_discount THEN
            RAISE EXCEPTION 'Visit pricing discount formula is invalid.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.discount_name_snapshot = ''
           OR NEW.discount_name_snapshot IS DISTINCT FROM BTRIM(NEW.discount_name_snapshot)
           OR NEW.discount_source NOT IN ('LOYALTY', 'PODOLOGIST', 'RECEPTION') THEN
            RAISE EXCEPTION 'Visit pricing discount identity is invalid.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.discount_source = 'LOYALTY' AND NEW.applied_by_id IS NOT NULL THEN
            RAISE EXCEPTION 'Automatic loyalty pricing cannot have a manual actor.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.discount_source IN ('PODOLOGIST', 'RECEPTION')
           AND NEW.applied_by_id IS NULL THEN
            RAISE EXCEPTION 'Manual pricing requires an actor.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS billing_visit_pricing_guard ON billing_visitpricing;
CREATE TRIGGER billing_visit_pricing_guard
BEFORE INSERT OR UPDATE OR DELETE ON billing_visitpricing
FOR EACH ROW EXECUTE FUNCTION billing_guard_visit_pricing();

CREATE OR REPLACE FUNCTION billing_guard_finished_visit_service_line()
RETURNS trigger AS $$
DECLARE
    target_visit_id uuid;
    target_visit_status varchar(16);
BEGIN
    -- Service-line writers and finish share the Visit row as their
    -- serialization point. Re-parenting locks both rows in UUID order so two
    -- opposite moves cannot deadlock by acquiring source/destination in an
    -- inconsistent order.
    FOR target_visit_id IN
        SELECT id
          FROM visits_visit
         WHERE id IN (
             CASE WHEN TG_OP = 'INSERT' THEN NEW.visit_id ELSE OLD.visit_id END,
             CASE WHEN TG_OP = 'DELETE' THEN OLD.visit_id ELSE NEW.visit_id END
         )
         ORDER BY id
         FOR UPDATE
    LOOP
        SELECT status INTO target_visit_status
          FROM visits_visit
         WHERE id = target_visit_id;
        IF target_visit_status = 'COMPLETED'
           OR EXISTS (
               SELECT 1 FROM billing_visitpricing WHERE visit_id = target_visit_id
           ) THEN
            RAISE EXCEPTION 'Finished visit service lines are immutable billing facts.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    END LOOP;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS billing_finished_visit_service_line_guard
ON visits_visitserviceline;
CREATE TRIGGER billing_finished_visit_service_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON visits_visitserviceline
FOR EACH ROW EXECUTE FUNCTION billing_guard_finished_visit_service_line();

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
    pricing_state varchar(16);
    pricing_gross bigint;
    pricing_discount_id uuid;
    pricing_discount_name varchar(120);
    pricing_discount_percent smallint;
    pricing_discount_source varchar(16);
    pricing_discount_amount bigint;
    pricing_net bigint;
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Payments are append-only.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    SELECT ledger.kind, ledger.amount_minor, ledger.created_by_id,
           shift.status, shift.employee_id,
           receivable.amount_minor, receivable.status,
           visit.status, visit.public_number, visit.completed_at,
           visit.payment_handoff_requested, visit.total_minor,
           patient.id, patient.public_number,
           BTRIM(CONCAT_WS(' ', patient.first_name, patient.last_name)), patient.phone,
           visit.specialist_id,
           COALESCE(NULLIF(BTRIM(CONCAT_WS(' ', specialist.first_name, specialist.last_name)), ''), specialist.email),
           COALESCE(NULLIF(BTRIM(CONCAT_WS(' ', actor.first_name, actor.last_name)), ''), actor.email),
           actor.email,
           (
               SELECT COALESCE(jsonb_agg(jsonb_build_object(
                   'id', line.id::text,
                   'code', line.service_code,
                   'name', line.service_name,
                   'quantity', line.quantity,
                   'unit_price_minor', line.price_minor,
                   'line_total_minor', line.price_minor * line.quantity
               ) ORDER BY line.is_primary DESC, line.service_name, line.service_code, line.id), '[]'::jsonb)
                 FROM visits_visitserviceline AS line WHERE line.visit_id = visit.id
           ),
           (
               SELECT COALESCE(string_agg(line.service_code || ' ' || line.service_name, ' '
                   ORDER BY line.is_primary DESC, line.service_name, line.service_code, line.id), '')
                 FROM visits_visitserviceline AS line WHERE line.visit_id = visit.id
           ),
           pricing.state, pricing.gross_minor, pricing.discount_id,
           pricing.discount_name_snapshot, pricing.discount_percent_snapshot,
           pricing.discount_source, pricing.discount_amount_minor, pricing.net_minor
      INTO ledger_kind, ledger_amount, ledger_actor_id,
           shift_status, shift_employee_id,
           receivable_amount, receivable_status,
           visit_status, visit_public_number, visit_completed_at,
           visit_payment_handoff_requested, visit_total_minor,
           patient_id, patient_public_number, patient_name, patient_phone,
           specialist_id, specialist_name, employee_name, employee_email,
           source_services, source_services_search,
           pricing_state, pricing_gross, pricing_discount_id,
           pricing_discount_name, pricing_discount_percent,
           pricing_discount_source, pricing_discount_amount, pricing_net
      FROM billing_cashledgerentry AS ledger
      JOIN billing_cashshift AS shift ON shift.id = ledger.cash_shift_id
      JOIN billing_receivable AS receivable ON receivable.id = NEW.receivable_id
      JOIN visits_visit AS visit ON visit.id = receivable.visit_id
      JOIN billing_visitpricing AS pricing ON pricing.visit_id = visit.id
      JOIN patients_patient AS patient ON patient.id = visit.patient_id
      JOIN accounts_user AS specialist ON specialist.id = visit.specialist_id
      JOIN accounts_user AS actor ON actor.id = ledger.created_by_id
     WHERE ledger.id = NEW.ledger_entry_id;

    IF NOT FOUND
       OR ledger_kind <> 'PAYMENT'
       OR ledger_amount <> receivable_amount
       OR ledger_amount <> pricing_net
       OR receivable_amount <= 0
       OR receivable_status <> 'OPEN'
       OR pricing_state <> 'OPEN'
       OR visit_status <> 'COMPLETED'
       OR visit_completed_at IS NULL
       OR visit_total_minor <> receivable_amount
       OR shift_status <> 'OPEN'
       OR ledger_actor_id <> shift_employee_id
       OR NEW.visit_public_number_snapshot <> visit_public_number
       OR NEW.visit_completed_at_snapshot <> visit_completed_at
       OR NEW.visit_payment_handoff_requested_snapshot IS DISTINCT FROM visit_payment_handoff_requested
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
       OR jsonb_typeof(NEW.services_snapshot) <> 'array'
       OR NEW.gross_total_minor_snapshot <> pricing_gross
       OR NEW.discount_id_snapshot IS DISTINCT FROM pricing_discount_id
       OR NEW.discount_name_snapshot IS DISTINCT FROM pricing_discount_name
       OR NEW.discount_percent_snapshot IS DISTINCT FROM pricing_discount_percent
       OR NEW.discount_source_snapshot IS DISTINCT FROM pricing_discount_source
       OR NEW.discount_amount_minor_snapshot <> pricing_discount_amount
       OR NEW.net_total_minor_snapshot <> pricing_net
       OR NEW.pricing_snapshot_is_legacy THEN
        RAISE EXCEPTION 'Payment facts do not match canonical pricing and billing sources.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION billing_validate_visit_financial_aggregate()
RETURNS trigger AS $$
DECLARE
    target_visit_id uuid;
    final_visit_status varchar(16);
    final_visit_total bigint;
    final_receivable_amount bigint;
    final_pricing_net bigint;
BEGIN
    IF TG_TABLE_NAME = 'visits_visit' THEN
        target_visit_id := NEW.id;
    ELSE
        target_visit_id := NEW.visit_id;
    END IF;
    SELECT visit.status, visit.total_minor, receivable.amount_minor, pricing.net_minor
      INTO final_visit_status, final_visit_total, final_receivable_amount, final_pricing_net
      FROM visits_visit AS visit
      LEFT JOIN billing_receivable AS receivable ON receivable.visit_id = visit.id
      LEFT JOIN billing_visitpricing AS pricing ON pricing.visit_id = visit.id
     WHERE visit.id = target_visit_id;
    IF final_visit_status = 'COMPLETED' AND (
        final_visit_total IS NULL
        OR final_receivable_amount IS NULL
        OR final_pricing_net IS NULL
        OR final_visit_total <> final_receivable_amount
        OR final_visit_total <> final_pricing_net
    ) THEN
        RAISE EXCEPTION 'Visit, receivable and pricing net totals must match at commit.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER billing_visit_financial_aggregate_from_visit
AFTER INSERT OR UPDATE ON visits_visit
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION billing_validate_visit_financial_aggregate();
CREATE CONSTRAINT TRIGGER billing_visit_financial_aggregate_from_receivable
AFTER INSERT OR UPDATE ON billing_receivable
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION billing_validate_visit_financial_aggregate();
CREATE CONSTRAINT TRIGGER billing_visit_financial_aggregate_from_pricing
AFTER INSERT OR UPDATE ON billing_visitpricing
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION billing_validate_visit_financial_aggregate();

CREATE OR REPLACE FUNCTION billing_validate_pricing_lifecycle_at_commit()
RETURNS trigger AS $$
DECLARE
    target_visit_id uuid;
    final_state varchar(16);
    final_net bigint;
    final_receivable_status varchar(16);
    typed_payment_count bigint;
    typed_payment_amount bigint;
BEGIN
    IF TG_TABLE_NAME = 'billing_payment' THEN
        SELECT receivable.visit_id INTO target_visit_id
          FROM billing_receivable AS receivable
         WHERE receivable.id = NEW.receivable_id;
    ELSE
        target_visit_id := NEW.visit_id;
    END IF;
    SELECT pricing.state, pricing.net_minor, receivable.status,
           COUNT(payment.id), MAX(ledger.amount_minor)
      INTO final_state, final_net, final_receivable_status,
           typed_payment_count, typed_payment_amount
      FROM billing_visitpricing AS pricing
      JOIN billing_receivable AS receivable ON receivable.visit_id = pricing.visit_id
      LEFT JOIN billing_payment AS payment ON payment.receivable_id = receivable.id
      LEFT JOIN billing_cashledgerentry AS ledger ON ledger.id = payment.ledger_entry_id
     WHERE pricing.visit_id = target_visit_id
     GROUP BY pricing.state, pricing.net_minor, receivable.status;
    IF final_state IS NULL OR final_receivable_status IS NULL THEN
        RAISE EXCEPTION 'Pricing and receivable must exist as one canonical pair.'
            USING ERRCODE = 'integrity_constraint_violation';
    ELSIF final_state = 'OPEN' THEN
        IF final_receivable_status <> 'OPEN' OR typed_payment_count <> 0 THEN
            RAISE EXCEPTION 'Open pricing requires one unpaid open receivable.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    ELSIF final_net = 0 THEN
        IF final_receivable_status <> 'PAID' OR typed_payment_count <> 0 THEN
            RAISE EXCEPTION 'Zero settled pricing must be paid without Payment or ledger rows.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    ELSIF final_receivable_status NOT IN ('PAID', 'REFUNDED')
          OR typed_payment_count <> 1
          OR typed_payment_amount <> final_net THEN
        RAISE EXCEPTION 'Positive settled pricing requires one matching settled payment.'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER billing_pricing_lifecycle_from_pricing
AFTER INSERT OR UPDATE ON billing_visitpricing
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION billing_validate_pricing_lifecycle_at_commit();
CREATE CONSTRAINT TRIGGER billing_pricing_lifecycle_from_receivable
AFTER INSERT OR UPDATE ON billing_receivable
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION billing_validate_pricing_lifecycle_at_commit();
CREATE CONSTRAINT TRIGGER billing_pricing_lifecycle_from_payment
AFTER INSERT ON billing_payment
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION billing_validate_pricing_lifecycle_at_commit();
"""


_payment_migration = import_module("apps.billing.migrations.0003_payment_and_receivable_guards")
_refund_migration = import_module("apps.billing.migrations.0004_refund_cash_adjustments")

REVERSE_SQL = (
    r"""
DROP TRIGGER IF EXISTS billing_pricing_lifecycle_from_payment ON billing_payment;
DROP TRIGGER IF EXISTS billing_pricing_lifecycle_from_receivable ON billing_receivable;
DROP TRIGGER IF EXISTS billing_pricing_lifecycle_from_pricing ON billing_visitpricing;
DROP FUNCTION IF EXISTS billing_validate_pricing_lifecycle_at_commit();
DROP TRIGGER IF EXISTS billing_visit_financial_aggregate_from_visit ON visits_visit;
DROP TRIGGER IF EXISTS billing_visit_financial_aggregate_from_receivable ON billing_receivable;
DROP TRIGGER IF EXISTS billing_visit_financial_aggregate_from_pricing ON billing_visitpricing;
DROP FUNCTION IF EXISTS billing_validate_visit_financial_aggregate();
DROP TRIGGER IF EXISTS billing_visit_pricing_guard ON billing_visitpricing;
DROP FUNCTION IF EXISTS billing_guard_visit_pricing();
DROP TRIGGER IF EXISTS billing_finished_visit_service_line_guard
ON visits_visitserviceline;
DROP FUNCTION IF EXISTS billing_guard_finished_visit_service_line();
DROP TRIGGER IF EXISTS billing_payment_append_only ON billing_payment;
"""
    + _refund_migration.REPLACE_RECEIVABLE_LIFECYCLE_TRIGGER
    + _payment_migration.CREATE_PAYMENT_GUARD_TRIGGER
)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0009_pricing_expand"),
        ("discounts", "0002_loyalty_guards"),
    ]

    operations = [
        migrations.RunPython(
            backfill_pricing_and_payment_snapshots,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="payment",
            name="gross_total_minor_snapshot",
            field=models.PositiveBigIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="payment",
            name="discount_name_snapshot",
            field=models.CharField(blank=True, editable=False, max_length=120),
        ),
        migrations.AlterField(
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
            ),
        ),
        migrations.AlterField(
            model_name="payment",
            name="discount_amount_minor_snapshot",
            field=models.PositiveBigIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="payment",
            name="net_total_minor_snapshot",
            field=models.PositiveBigIntegerField(editable=False),
        ),
        migrations.AlterField(
            model_name="payment",
            name="pricing_snapshot_is_legacy",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "net_total_minor_snapshot",
                        django.db.models.expressions.CombinedExpression(
                            models.F("gross_total_minor_snapshot"),
                            "-",
                            models.F("discount_amount_minor_snapshot"),
                        ),
                    ),
                    ("net_total_minor_snapshot__gt", 0),
                    ("visit_total_minor_snapshot", models.F("net_total_minor_snapshot")),
                ),
                name="billing_payment_pricing_formula",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("discount_amount_minor_snapshot", 0),
                        ("discount_id_snapshot__isnull", True),
                        ("discount_name_snapshot", ""),
                        ("discount_percent_snapshot__isnull", True),
                        ("discount_source_snapshot", ""),
                    ),
                    models.Q(
                        ("discount_id_snapshot__isnull", False),
                        ("discount_percent_snapshot__gte", 1),
                        ("discount_percent_snapshot__lte", 99),
                        (
                            "discount_source_snapshot__in",
                            ["LOYALTY", "PODOLOGIST", "RECEPTION"],
                        ),
                        models.Q(("discount_name_snapshot", ""), _negated=True),
                    ),
                    _connector="OR",
                ),
                name="billing_payment_discount_snapshot_consistent",
            ),
        ),
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
        migrations.RunPython(
            migrations.RunPython.noop,
            reject_reverse_after_pricing_activation,
        ),
    ]
