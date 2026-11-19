"""Demo organisations may be wiped (U-07-T06): the append-only triggers let a DELETE through
for one organisation only when the transaction names it in ``numo9.demo_wipe`` **and** it is a
demo organisation (``tenancy_organisation.is_demo``). Real books stay append-only: no setting
unlocks a non-demo organisation, and ``numo9.demo.reset`` sets it with ``set_config(…, true)``
(transaction-local) around its own deletes only.
"""

from django.db import migrations

from numo9.audit.pg import PostgresOnly

FORWARD = """
CREATE OR REPLACE FUNCTION ledger_journalentry_refuse_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE'
       AND current_setting('numo9.demo_wipe', true) = OLD.organisation_id::text
       AND EXISTS (SELECT 1 FROM tenancy_organisation o
                    WHERE o.id = OLD.organisation_id AND o.is_demo) THEN
        RETURN OLD;
    END IF;
    IF OLD.status IN ('posted', 'reversed') THEN
        IF TG_OP = 'UPDATE'
           AND OLD.status = 'posted' AND NEW.status = 'reversed'
           AND (to_jsonb(NEW) - 'status' - 'updated_at')
               = (to_jsonb(OLD) - 'status' - 'updated_at') THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'journal entry % (number %) is %: % is not allowed',
                OLD.id, OLD.number, OLD.status, TG_OP
            USING ERRCODE = 'insufficient_privilege',
                  HINT = 'Posted journals are append-only: reverse the entry instead (C-02).';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION ledger_journalline_refuse_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    locked_entry bigint;
BEGIN
    IF TG_OP = 'DELETE'
       AND current_setting('numo9.demo_wipe', true) = OLD.organisation_id::text
       AND EXISTS (SELECT 1 FROM tenancy_organisation o
                    WHERE o.id = OLD.organisation_id AND o.is_demo) THEN
        RETURN OLD;
    END IF;
    SELECT e.id INTO locked_entry
      FROM ledger_journalentry e
     WHERE e.status IN ('posted', 'reversed')
       AND e.id IN (
           CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN OLD.entry_id END,
           CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN NEW.entry_id END
       )
     LIMIT 1;
    IF locked_entry IS NOT NULL THEN
        RAISE EXCEPTION 'journal entry % is posted: % of its lines is not allowed',
                locked_entry, TG_OP
            USING ERRCODE = 'insufficient_privilege',
                  HINT = 'Posted journals are append-only: reverse the entry instead (C-02).';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
"""

BACKWARD = """
CREATE OR REPLACE FUNCTION ledger_journalentry_refuse_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IN ('posted', 'reversed') THEN
        IF TG_OP = 'UPDATE'
           AND OLD.status = 'posted' AND NEW.status = 'reversed'
           AND (to_jsonb(NEW) - 'status' - 'updated_at')
               = (to_jsonb(OLD) - 'status' - 'updated_at') THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'journal entry % (number %) is %: % is not allowed',
                OLD.id, OLD.number, OLD.status, TG_OP
            USING ERRCODE = 'insufficient_privilege',
                  HINT = 'Posted journals are append-only: reverse the entry instead (C-02).';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION ledger_journalline_refuse_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    locked_entry bigint;
BEGIN
    SELECT e.id INTO locked_entry
      FROM ledger_journalentry e
     WHERE e.status IN ('posted', 'reversed')
       AND e.id IN (
           CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN OLD.entry_id END,
           CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN NEW.entry_id END
       )
     LIMIT 1;
    IF locked_entry IS NOT NULL THEN
        RAISE EXCEPTION 'journal entry % is posted: % of its lines is not allowed',
                locked_entry, TG_OP
            USING ERRCODE = 'insufficient_privilege',
                  HINT = 'Posted journals are append-only: reverse the entry instead (C-02).';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0006_partition_journal_lines"),
        ("tenancy", "0007_organisation_demo_fields"),
    ]

    operations = [PostgresOnly(sql=FORWARD, reverse_sql=BACKWARD)]
