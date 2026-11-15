"""C-02-T02 — JournalEntry + JournalLine models, numeric(18,2), check constraints.

Acceptance: constraint violations raise. The database refuses a negative debit or credit, a line
with both sides, a line with neither side, an amount beyond numeric(18,2), an unknown book, a
duplicate line number, a duplicate journal number, a posted entry without number or posting time,
a draft with a number, an unknown status and an entry reversing itself. Also: amounts come back
as Decimal with two places, the line's organisation follows its entry, the partition-ready
composite primary key and its sequence, row-level security on both tables.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.db import DataError, IntegrityError, connection, transaction
from django.utils import timezone

from numo9.ledger.models import (
    Account,
    Book,
    JournalEntry,
    JournalLine,
    JournalStatus,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from numo9.tenancy.rls import POLICY
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def cash(org: Organisation) -> Account:
    return account(org, "1000", "Chequing", subtype="bank", gifi_id="1001")


@pytest.fixture
def sales(org: Organisation) -> Account:
    return account(org, "4000", "Sales", subtype="revenue", gifi_id="8000")


def entry(org: Organisation, **fields: Any) -> JournalEntry:
    item = JournalEntry(organisation=org, date=dt.date(2026, 3, 31), **fields)
    item.save()
    return item


def line(entry_: JournalEntry, account_: Account, line_no: int = 1, **fields: Any) -> JournalLine:
    item = JournalLine(entry=entry_, account=account_, line_no=line_no, **fields)
    item.save()
    return item


def refused(build: Any, error: type[Exception] = IntegrityError) -> str:
    with pytest.raises(error) as caught, transaction.atomic():
        build()
    return str(caught.value)


# ---- lines -----------------------------------------------------------------------------------


def test_a_valid_entry_with_lines(org: Organisation, cash: Account, sales: Account) -> None:
    draft = entry(org, narration="Cash sale")
    line(draft, cash, 1, debit=D("113.00"))
    line(draft, sales, 2, credit=D("113.00"), book=Book.BOTH)
    lines = list(JournalLine.objects.filter(entry=draft))
    assert [(item.debit, item.credit) for item in lines] == [
        (D("113.00"), D("0.00")),
        (D("0.00"), D("113.00")),
    ]
    assert all(item.organisation_id == org.pk for item in lines)
    assert [item.amount for item in lines] == [D("113.00"), D("-113.00")]
    assert draft.status == JournalStatus.DRAFT and draft.number is None


def test_negative_amounts_are_refused(org: Organisation, cash: Account) -> None:
    draft = entry(org)
    assert "ledger_line_debit_not_negative" in refused(lambda: line(draft, cash, debit=D("-1")))
    assert "ledger_line_credit_not_negative" in refused(
        lambda: line(draft, cash, credit=D("-0.01"))
    )


def test_exactly_one_side_per_line(org: Organisation, cash: Account) -> None:
    draft = entry(org)
    assert "ledger_line_one_side" in refused(lambda: line(draft, cash, debit=D("1"), credit=D("1")))
    assert "ledger_line_one_side" in refused(lambda: line(draft, cash))


def test_numeric_18_2(org: Organisation, cash: Account) -> None:
    draft = entry(org)
    biggest = line(draft, cash, 1, debit=D("9999999999999999.99"))
    biggest.refresh_from_db()
    assert biggest.debit == D("9999999999999999.99")
    # 17 digits before the point don't fit numeric(18, 2).
    refused(lambda: line(draft, cash, 2, debit=D("10000000000000000.00")), DataError)
    column = [
        row
        for row in connection.introspection.get_table_description(
            connection.cursor(), "ledger_journalline"
        )
        if row.name in {"debit", "credit"}
    ]
    assert {(row.name, row.precision, row.scale) for row in column} == {
        ("debit", 18, 2),
        ("credit", 18, 2),
    }


def test_unknown_book_and_duplicate_line_number(org: Organisation, cash: Account) -> None:
    draft = entry(org)
    assert "ledger_line_book_valid" in refused(lambda: line(draft, cash, debit=D("1"), book="x"))
    line(draft, cash, 1, debit=D("1"))
    assert "ledger_line_no_unique" in refused(lambda: line(draft, cash, 1, credit=D("1")))


def test_composite_primary_key_and_sequence(org: Organisation, cash: Account) -> None:
    draft = entry(org)
    first = line(draft, cash, 1, debit=D("1"))
    second = line(draft, cash, 2, credit=D("1"))
    assert first.pk == (org.pk, first.id)
    assert second.id > first.id
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
            "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = 'ledger_journalline'::regclass "
            "AND i.indisprimary ORDER BY array_position(i.indkey, a.attnum)"
        )
        assert [row[0] for row in cursor.fetchall()] == ["organisation_id", "id"]
        cursor.execute("SELECT pg_get_serial_sequence('ledger_journalline', 'id')")
        assert cursor.fetchone() == ("public.ledger_journalline_id_seq",)


# ---- entries -----------------------------------------------------------------------------------


def posted(org: Organisation, number: int | None = 1, **fields: Any) -> JournalEntry:
    return entry(
        org, status=JournalStatus.POSTED, number=number, posted_at=timezone.now(), **fields
    )


def test_journal_numbers_are_unique_per_organisation(org: Organisation) -> None:
    posted(org, 1)
    assert "ledger_journal_number_unique_per_org" in refused(lambda: posted(org, 1))
    other = Organisation.objects.create(name="Birch Garage")
    with org_context(other):
        posted(other, 1)  # the same number in another organisation


def test_posted_entries_have_number_and_time_and_drafts_none(org: Organisation) -> None:
    assert "ledger_journal_number_when_posted" in refused(lambda: posted(org, None))
    assert "ledger_journal_number_when_posted" in refused(
        lambda: entry(org, status=JournalStatus.POSTED, number=5)
    )
    assert "ledger_journal_number_when_posted" in refused(lambda: entry(org, number=5))
    assert "ledger_journal_number_when_posted" in refused(
        lambda: entry(org, status=JournalStatus.AWAITING_APPROVAL, number=5)
    )
    entry(org, status=JournalStatus.AWAITING_APPROVAL)


def test_unknown_status_book_scope_and_empty_type(org: Organisation) -> None:
    # Any unknown status is refused; the status check names it when the number rule can't.
    refused(lambda: entry(org, status="void"))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s",
            ["ledger_journal_status_valid"],
        )
        (definition,) = cursor.fetchone()
    assert all(f"'{status}'" in definition for status in JournalStatus.values)
    assert "ledger_journal_book_scope_valid" in refused(lambda: entry(org, book_scope="x"))
    assert "ledger_journal_type_required" in refused(lambda: entry(org, type=""))


def test_reversal_link(org: Organisation) -> None:
    original = posted(org, 1)
    reversal = posted(org, 2, reversal_of=original, type="reversal")
    assert original.reversed_by == reversal
    # One reversal per entry (one-to-one) and never itself.
    refused(lambda: posted(org, 3, reversal_of=original))
    assert "ledger_journal_not_own_reversal" in refused(
        lambda: JournalEntry.objects.filter(pk=reversal.pk).update(reversal_of=reversal.pk)
    )


def test_entry_changes_are_audited(org: Organisation) -> None:
    from numo9.audit.models import AuditEvent

    draft = entry(org, narration="Opening")
    draft.narration = "Opening balances"
    draft.save()
    assert list(
        AuditEvent.objects.filter(object_type="ledger.JournalEntry")
        .order_by("id")
        .values_list("action", flat=True)
    ) == ["ledger.journalentry.created", "ledger.journalentry.updated"]


def test_entries_and_lines_are_organisation_scoped(
    org: Organisation, cash: Account, sales: Account
) -> None:
    draft = entry(org)
    line(draft, cash, 1, debit=D("5"))
    other = Organisation.objects.create(name="Birch Garage")
    with org_context(other):
        assert JournalEntry.objects.count() == 0
        assert JournalLine.objects.count() == 0


@pytest.mark.parametrize("table", ["ledger_journalentry", "ledger_journalline"])
def test_row_level_security(table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s", [table]
        )
        assert cursor.fetchall() == [(True, True)]
        cursor.execute("SELECT policyname FROM pg_policies WHERE tablename = %s", [table])
        assert cursor.fetchall() == [(POLICY,)]


def test_posted_lines_make_an_account_have_postings(org: Organisation, cash: Account) -> None:
    from numo9.ledger.postings import has_postings

    draft = entry(org)
    line(draft, cash, 1, debit=D("1"))
    assert has_postings(cash) is False  # draft lines are not transactions
    done = posted(org, 1)
    line(done, cash, 1, debit=D("1"))
    assert has_postings(cash) is True
