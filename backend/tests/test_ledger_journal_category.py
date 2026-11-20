"""C-03-T01 — the journal type of every journal: ``JournalEntry.journal_type``
(``JournalCategory``: General, Adjusting, Reclass, Tax adjustment; system types Closing, Payroll,
Depreciation, never offered to people).

Acceptance: the migration applies and rolls back; existing journals default to General (a row
written without the column gets General from the database); the type is posted, kept on a draft
and carried to the reversal; the database refuses an unknown type.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from numo9.ledger.models import (
    SELECTABLE_CATEGORIES,
    SYSTEM_CATEGORIES,
    JournalCategory,
    JournalEntry,
)
from numo9.ledger.services import post_journal, reverse, save_draft
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def spec(org: Organisation, **fields: object) -> JournalSpec:
    bank = account(org, "1000", "Chequing", subtype="bank")
    rent = account(org, "5400", "Rent")
    return JournalSpec(
        date=dt.date(2026, 6, 15),
        lines=(LineSpec(rent, debit=Decimal("100.00")), LineSpec(bank, credit=Decimal("100.00"))),
        **fields,  # type: ignore[arg-type]
    )


def test_selectable_and_system_types() -> None:
    assert SELECTABLE_CATEGORIES == ("general", "adjusting", "reclass", "tax_adjustment")
    assert {"closing", "payroll", "depreciation"} == SYSTEM_CATEGORIES


def test_type_defaults_to_general_and_is_carried() -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        entry = post_journal(spec(org))
        assert entry.journal_type == JournalCategory.GENERAL
        adjusting = post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 16),
                lines=entry_lines(org),
                journal_type=JournalCategory.ADJUSTING,
            )
        )
        assert JournalEntry.objects.get(pk=adjusting.pk).journal_type == "adjusting"
        reversal = reverse(adjusting)
        assert reversal.journal_type == "adjusting"
        draft = save_draft(
            JournalSpec(date=dt.date(2026, 6, 17), lines=entry_lines(org), journal_type="reclass")
        )
        assert JournalEntry.objects.get(pk=draft.pk).journal_type == "reclass"


def entry_lines(org: Organisation) -> tuple[LineSpec, ...]:
    from numo9.ledger.models import Account

    rent = Account.objects.get(code="5400")
    bank = Account.objects.get(code="1000")
    return (LineSpec(rent, debit=Decimal("10.00")), LineSpec(bank, credit=Decimal("10.00")))


def test_database_default_and_check() -> None:
    org = Organisation.objects.create(name="Old Code Inc.")
    with org_context(org):
        entry = save_draft(JournalSpec(date=dt.date(2026, 6, 15), lines=spec(org).lines))
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = 'ledger_journalentry' AND column_name = 'journal_type'"
            )
            assert "general" in cursor.fetchone()[0]
        with pytest.raises(IntegrityError), transaction.atomic():
            JournalEntry._base_manager.filter(pk=entry.pk).update(journal_type="festive")


@pytest.mark.django_db(transaction=True)
def test_migration_rolls_back_and_forward() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("ledger", "0007_demo_wipe")])
    columns = {
        c.name
        for c in connection.introspection.get_table_description(
            connection.cursor(), "ledger_journalentry"
        )
    }
    assert "journal_type" not in columns
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())
    columns = {
        c.name
        for c in connection.introspection.get_table_description(
            connection.cursor(), "ledger_journalentry"
        )
    }
    assert "journal_type" in columns
