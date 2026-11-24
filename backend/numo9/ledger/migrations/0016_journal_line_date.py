"""Journal lines carry their entry's date (K-01-T04): the report aggregation reads period
balances by (organisation, account, date, book) from one index, without joining the entries.

- ``date`` is filled by the database: a BEFORE INSERT trigger copies the entry's date onto each
  new line (every insert path — the engine, imports, the scale fixtures — gets it);
- a draft whose date changes passes the new date to its lines (AFTER UPDATE OF date on the
  entry); posted entries never change date (append-only, C-02);
- existing lines are back-filled from their entries with the append-only trigger paused for that
  one statement (the update only sets the copy of the date the entry already has).
"""

from django.db import migrations, models

from numo9.audit.pg import PostgresOnly

FORWARD = """
CREATE OR REPLACE FUNCTION ledger_journalline_fill_date() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    SELECT e.date INTO NEW.date FROM ledger_journalentry e WHERE e.id = NEW.entry_id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ledger_journalline_a_fill_date
    BEFORE INSERT ON ledger_journalline
    FOR EACH ROW EXECUTE FUNCTION ledger_journalline_fill_date();

CREATE OR REPLACE FUNCTION ledger_journalentry_date_to_lines() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE ledger_journalline SET date = NEW.date
     WHERE organisation_id = NEW.organisation_id AND entry_id = NEW.id;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ledger_journalentry_date_to_lines
    AFTER UPDATE OF date ON ledger_journalentry
    FOR EACH ROW WHEN (OLD.date IS DISTINCT FROM NEW.date)
    EXECUTE FUNCTION ledger_journalentry_date_to_lines();

ALTER TABLE ledger_journalline DISABLE TRIGGER ledger_journalline_append_only;
UPDATE ledger_journalline l SET date = e.date
  FROM ledger_journalentry e
 WHERE e.id = l.entry_id AND e.organisation_id = l.organisation_id AND l.date IS NULL;
ALTER TABLE ledger_journalline ENABLE TRIGGER ledger_journalline_append_only;
"""

BACKWARD = """
DROP TRIGGER IF EXISTS ledger_journalentry_date_to_lines ON ledger_journalentry;
DROP FUNCTION IF EXISTS ledger_journalentry_date_to_lines();
DROP TRIGGER IF EXISTS ledger_journalline_a_fill_date ON ledger_journalline;
DROP FUNCTION IF EXISTS ledger_journalline_fill_date();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0015_supplier_line_manual_match"),
        ("ledger", "0015_recurring_journal"),
        ("tenancy", "0007_organisation_demo_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="journalline",
            name="date",
            field=models.DateField(blank=True, editable=False, null=True, verbose_name="date"),
        ),
        PostgresOnly(FORWARD, BACKWARD),
        migrations.AddIndex(
            model_name="journalline",
            index=models.Index(
                fields=["organisation", "account", "date", "book"],
                name="ledger_line_account_date_idx",
            ),
        ),
    ]
