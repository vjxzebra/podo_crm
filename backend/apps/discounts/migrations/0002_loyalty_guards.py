from django.db import migrations


def reject_reverse_after_loyalty_usage(apps, schema_editor):  # type: ignore[no-untyped-def]
    PatientLoyaltyState = apps.get_model("discounts", "PatientLoyaltyState")
    VisitLoyaltyEvent = apps.get_model("discounts", "VisitLoyaltyEvent")

    if PatientLoyaltyState.objects.exists() or VisitLoyaltyEvent.objects.exists():
        raise RuntimeError(
            "Cannot reverse discounts.0002 after loyalty state or events were created."
        )


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION discounts_protect_discount_catalog()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Discounts cannot be deleted; deactivate them instead.'
            USING ERRCODE = '23514', CONSTRAINT = 'discounts_discount_no_delete';
    END IF;

    IF OLD.is_active = TRUE
       AND NEW.is_active = FALSE
       AND EXISTS (
           SELECT 1
           FROM discounts_loyaltypolicy
           WHERE key = 'default'
             AND is_active = TRUE
             AND discount_id = OLD.id
       ) THEN
        RAISE EXCEPTION 'The active loyalty discount cannot be deactivated.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_active_loyalty_discount_active';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS discounts_discount_catalog_guard ON discounts_discount;
CREATE TRIGGER discounts_discount_catalog_guard
BEFORE UPDATE OR DELETE ON discounts_discount
FOR EACH ROW EXECUTE FUNCTION discounts_protect_discount_catalog();

CREATE OR REPLACE FUNCTION discounts_protect_loyalty_policy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'The singleton loyalty policy cannot be deleted.'
            USING ERRCODE = '23514', CONSTRAINT = 'discounts_loyalty_policy_no_delete';
    END IF;
    IF NEW.key <> 'default' THEN
        RAISE EXCEPTION 'The loyalty policy key must be default.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_policy_singleton_key';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.key IS DISTINCT FROM OLD.key THEN
        RAISE EXCEPTION 'The singleton loyalty policy identity is immutable.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_policy_singleton_key';
    END IF;
    IF TG_OP = 'UPDATE'
       AND OLD.started_at IS NOT NULL
       AND NEW.started_at IS DISTINCT FROM OLD.started_at THEN
        RAISE EXCEPTION 'Loyalty program start time is immutable after activation.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_started_at_immutable';
    END IF;
    IF NEW.is_active THEN
        PERFORM 1
        FROM discounts_discount
        WHERE id = NEW.discount_id
          AND is_active = TRUE
        FOR KEY SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Active loyalty policy requires an active discount.'
                USING ERRCODE = '23514',
                      CONSTRAINT = 'discounts_active_loyalty_discount_active';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS discounts_loyalty_policy_guard ON discounts_loyaltypolicy;
CREATE TRIGGER discounts_loyalty_policy_guard
BEFORE INSERT OR UPDATE OR DELETE ON discounts_loyaltypolicy
FOR EACH ROW EXECUTE FUNCTION discounts_protect_loyalty_policy();

CREATE OR REPLACE FUNCTION discounts_protect_loyalty_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.completed_count <> 0 OR NEW.version <> 1 THEN
            RAISE EXCEPTION 'Loyalty state must start at zero with version one.'
                USING ERRCODE = '23514',
                      CONSTRAINT = 'discounts_loyalty_state_initial';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Loyalty state cannot be deleted.'
            USING ERRCODE = '23514', CONSTRAINT = 'discounts_loyalty_state_no_delete';
    END IF;
    IF NEW.patient_id IS DISTINCT FROM OLD.patient_id
       OR NEW.completed_count <> OLD.completed_count + 1
       OR NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'Loyalty state must advance by exactly one successful finish.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_state_forward_only';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS discounts_loyalty_state_guard ON discounts_patientloyaltystate;
CREATE TRIGGER discounts_loyalty_state_guard
BEFORE INSERT OR UPDATE OR DELETE ON discounts_patientloyaltystate
FOR EACH ROW EXECUTE FUNCTION discounts_protect_loyalty_state();

CREATE OR REPLACE FUNCTION discounts_validate_loyalty_state_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.completed_count > 0 AND NOT EXISTS (
        SELECT 1
        FROM discounts_visitloyaltyevent
        WHERE patient_id = NEW.patient_id
          AND sequence_number = NEW.completed_count
    ) THEN
        RAISE EXCEPTION 'Loyalty counter advance requires its successful visit event.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_state_requires_event';
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS discounts_loyalty_state_event_guard
ON discounts_patientloyaltystate;
CREATE CONSTRAINT TRIGGER discounts_loyalty_state_event_guard
AFTER INSERT OR UPDATE ON discounts_patientloyaltystate
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION discounts_validate_loyalty_state_event();

CREATE OR REPLACE FUNCTION discounts_validate_loyalty_event()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    visit_patient uuid;
    state_count bigint;
    policy_active boolean;
    policy_every_n integer;
    policy_discount uuid;
    policy_started_at timestamptz;
    current_name varchar(120);
    current_percent smallint;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Loyalty events are append-only.'
            USING ERRCODE = '23514', CONSTRAINT = 'discounts_loyalty_event_append_only';
    END IF;

    SELECT patient_id INTO visit_patient
    FROM visits_visit
    WHERE id = NEW.visit_id;
    IF visit_patient IS NULL OR visit_patient IS DISTINCT FROM NEW.patient_id THEN
        RAISE EXCEPTION 'Loyalty event patient must match the visit patient.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_event_visit_patient';
    END IF;

    SELECT completed_count INTO state_count
    FROM discounts_patientloyaltystate
    WHERE patient_id = NEW.patient_id;
    IF state_count IS NULL OR state_count <> NEW.sequence_number THEN
        RAISE EXCEPTION 'Loyalty event sequence must match the patient counter.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_event_sequence_state';
    END IF;

    SELECT is_active, every_n, discount_id, started_at
      INTO policy_active, policy_every_n, policy_discount, policy_started_at
    FROM discounts_loyaltypolicy
    WHERE key = 'default';
    IF policy_active IS DISTINCT FROM TRUE
       OR policy_every_n <> NEW.every_n_snapshot
       OR policy_discount IS DISTINCT FROM NEW.discount_id
       OR policy_started_at IS DISTINCT FROM NEW.policy_started_at_snapshot THEN
        RAISE EXCEPTION 'Loyalty event snapshots must match the active policy.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_event_policy_snapshot';
    END IF;

    SELECT name, percent INTO current_name, current_percent
    FROM discounts_discount
    WHERE id = NEW.discount_id AND is_active = TRUE;
    IF current_name IS NULL
       OR current_name IS DISTINCT FROM NEW.discount_name_snapshot
       OR current_percent IS DISTINCT FROM NEW.discount_percent_snapshot THEN
        RAISE EXCEPTION 'Loyalty event discount snapshots are invalid.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_event_discount_snapshot';
    END IF;

    IF NEW.eligible IS DISTINCT FROM (NEW.sequence_number % NEW.every_n_snapshot = 0) THEN
        RAISE EXCEPTION 'Loyalty event eligibility does not match the ordinal.'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'discounts_loyalty_event_eligibility';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS discounts_loyalty_event_guard ON discounts_visitloyaltyevent;
CREATE TRIGGER discounts_loyalty_event_guard
BEFORE INSERT OR UPDATE OR DELETE ON discounts_visitloyaltyevent
FOR EACH ROW EXECUTE FUNCTION discounts_validate_loyalty_event();
"""


REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS discounts_loyalty_event_guard ON discounts_visitloyaltyevent;
DROP FUNCTION IF EXISTS discounts_validate_loyalty_event();
DROP TRIGGER IF EXISTS discounts_loyalty_state_event_guard
ON discounts_patientloyaltystate;
DROP FUNCTION IF EXISTS discounts_validate_loyalty_state_event();
DROP TRIGGER IF EXISTS discounts_loyalty_state_guard ON discounts_patientloyaltystate;
DROP FUNCTION IF EXISTS discounts_protect_loyalty_state();
DROP TRIGGER IF EXISTS discounts_loyalty_policy_guard ON discounts_loyaltypolicy;
DROP FUNCTION IF EXISTS discounts_protect_loyalty_policy();
DROP TRIGGER IF EXISTS discounts_discount_catalog_guard ON discounts_discount;
DROP FUNCTION IF EXISTS discounts_protect_discount_catalog();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("discounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
        migrations.RunPython(
            migrations.RunPython.noop,
            reject_reverse_after_loyalty_usage,
        ),
    ]
