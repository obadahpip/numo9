"""Posted journals are append-only at the database (C-02-T04, ADR-0003 §3).

Two row triggers raise ``insufficient_privilege`` (they hold for raw SQL, bulk ``update()`` /
``delete()``, superusers and — on the partitioned parent of C-02-T03 — every partition):

- ``ledger_journalentry_append_only`` (``BEFORE UPDATE OR DELETE``): a posted or reversed entry
  can't be deleted, and the only change allowed is **Posted → Reversed** touching nothing but
  ``status`` (and ``updated_at``, which every save sets). Draft and awaiting-approval entries stay
  editable;
- ``ledger_journalline_append_only`` (``BEFORE INSERT OR UPDATE OR DELETE``): a line can't be
  added to, changed in, moved into or out of, or deleted from a posted or reversed entry. The
  engine (C-02-T08) inserts the lines while the entry is a draft, then posts it.

Privileges are not revoked (unlike ``audit_event``): drafts must stay editable.
``TRUNCATE`` is not a row operation (the test runner empties tables between transactional tests).
"""

from django.db import migrations

from numo9.audit.pg import PostgresOnly

FORWARD = """
CREATE FUNCTION ledger_journalentry_refuse_change() RETURNS trigger
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

CREATE TRIGGER ledger_journalentry_append_only
    BEFORE UPDATE OR DELETE ON ledger_journalentry
    FOR EACH ROW EXECUTE FUNCTION ledger_journalentry_refuse_change();

CREATE FUNCTION ledger_journalline_refuse_change() RETURNS trigger
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

CREATE TRIGGER ledger_journalline_append_only
    BEFORE INSERT OR UPDATE OR DELETE ON ledger_journalline
    FOR EACH ROW EXECUTE FUNCTION ledger_journalline_refuse_change();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS ledger_journalline_append_only ON ledger_journalline;
DROP FUNCTION IF EXISTS ledger_journalline_refuse_change();
DROP TRIGGER IF EXISTS ledger_journalentry_append_only ON ledger_journalentry;
DROP FUNCTION IF EXISTS ledger_journalentry_refuse_change();
"""


class Migration(migrations.Migration):
    dependencies = [("ledger", "0003_journal_entry_line")]

    operations = [PostgresOnly(sql=FORWARD, reverse_sql=BACKWARD)]
