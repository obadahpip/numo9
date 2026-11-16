"""C-02-T04 — append-only trigger on posted entries/lines + Django guard.

Acceptance: UPDATE on a posted line → database error. The triggers are tested with raw SQL and
bulk queryset calls (which bypass Django), the guard with ``save()``/``delete()``:

- posted or reversed lines: no UPDATE, DELETE, INSERT, nor moving a line in or out;
- posted entries: no DELETE, no change of any column; the only change is Posted → Reversed
  touching nothing else; a reversed entry can't change at all (not even back to Posted);
- drafts and entries awaiting approval stay editable (lines added, changed, removed);
- the guard refuses the same changes earlier with ``ledger.journal.locked`` and the number.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.utils import DatabaseError
from django.utils import timezone

from numo9.ledger.models import (
    Account,
    JournalEntry,
    JournalLine,
    JournalLocked,
    JournalStatus,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

D = Decimal
INSUFFICIENT_PRIVILEGE = "42501"


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def accounts(org: Organisation) -> tuple[Account, Account]:
    return (
        account(org, "1000", "Chequing", subtype="bank", gifi_id="1001"),
        account(org, "4000", "Sales", subtype="revenue", gifi_id="8000"),
    )


def make_entry(
    org: Organisation, accounts: tuple[Account, Account], *, status: str, number: int = 1
) -> JournalEntry:
    """Lines written while the entry is a draft, then the status set — as the engine does."""
    entry = JournalEntry(organisation=org, date=dt.date(2026, 3, 31), narration="Cash sale")
    entry.save()
    cash, sales = accounts
    JournalLine(entry=entry, account=cash, line_no=1, debit=D("100.00")).save()
    JournalLine(entry=entry, account=sales, line_no=2, credit=D("100.00")).save()
    if status in (JournalStatus.POSTED, JournalStatus.REVERSED):
        JournalEntry.objects.filter(pk=entry.pk).update(
            status=JournalStatus.POSTED, number=number, posted_at=timezone.now()
        )
        if status == JournalStatus.REVERSED:
            JournalEntry.objects.filter(pk=entry.pk).update(status=JournalStatus.REVERSED)
    elif status != JournalStatus.DRAFT:
        JournalEntry.objects.filter(pk=entry.pk).update(status=status)
    entry.refresh_from_db()
    return entry


def raw(query: str, params: list[Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(query, params)


def refused_by_database(action: Any) -> str:
    with pytest.raises(DatabaseError) as caught, transaction.atomic():
        action()
    cause = caught.value.__cause__
    assert getattr(cause, "sqlstate", None) == INSUFFICIENT_PRIVILEGE, caught.value
    return str(caught.value)


LOCKED = [JournalStatus.POSTED, JournalStatus.REVERSED]


# ---- lines: the database (acceptance) ----------------------------------------------------------


@pytest.mark.parametrize("status", LOCKED)
def test_update_of_a_posted_line_is_a_database_error(
    org: Organisation, accounts: tuple[Account, Account], status: str
) -> None:
    entry = make_entry(org, accounts, status=status)
    message = refused_by_database(
        lambda: raw("UPDATE ledger_journalline SET debit = 1 WHERE entry_id = %s", [entry.pk])
    )
    assert "is posted: UPDATE of its lines is not allowed" in message
    refused_by_database(
        lambda: JournalLine.objects.filter(entry=entry).update(description="edited")
    )
    assert sorted(JournalLine.objects.filter(entry=entry).values_list("debit", flat=True)) == [
        D("0.00"),
        D("100.00"),
    ]


@pytest.mark.parametrize("status", LOCKED)
def test_posted_lines_cant_be_deleted_added_or_moved(
    org: Organisation, accounts: tuple[Account, Account], status: str
) -> None:
    entry = make_entry(org, accounts, status=status)
    cash, _ = accounts
    refused_by_database(
        lambda: raw("DELETE FROM ledger_journalline WHERE entry_id = %s", [entry.pk])
    )
    refused_by_database(lambda: JournalLine.objects.filter(entry=entry).delete())
    refused_by_database(
        lambda: raw(
            "INSERT INTO ledger_journalline (organisation_id, entry_id, line_no, account_id, "
            "debit, credit, book, tracking, description, tax_code, created_at, updated_at) "
            "VALUES (%s, %s, 3, %s, 5, 0, 'both', '{}', '', '', now(), now())",
            [org.pk, entry.pk, cash.pk],
        )
    )
    draft = make_entry(org, accounts, status=JournalStatus.DRAFT)
    # Out of a posted entry into a draft, and from a draft into a posted entry.
    refused_by_database(
        lambda: JournalLine.objects.filter(entry=entry, line_no=1).update(entry=draft)
    )
    refused_by_database(
        lambda: JournalLine.objects.filter(entry=draft, line_no=1).update(entry=entry)
    )
    assert JournalLine.objects.filter(entry=entry).count() == 2


# ---- entries: the database ---------------------------------------------------------------------


@pytest.mark.parametrize("status", LOCKED)
def test_posted_entries_cant_be_deleted_or_changed(
    org: Organisation, accounts: tuple[Account, Account], status: str
) -> None:
    entry = make_entry(org, accounts, status=status)
    refused_by_database(lambda: raw("DELETE FROM ledger_journalentry WHERE id = %s", [entry.pk]))
    for change in (
        {"narration": "edited"},
        {"date": dt.date(2026, 4, 1)},
        {"number": 99},
        {"status": JournalStatus.DRAFT},
        {"deleted_at": timezone.now()},
        {"status": JournalStatus.REVERSED, "narration": "and edited"},
    ):
        refused_by_database(
            lambda change=change: JournalEntry.objects.filter(pk=entry.pk).update(**change)
        )
    entry.refresh_from_db()
    assert (entry.narration, entry.number, entry.status) == ("Cash sale", 1, status)


def test_posted_to_reversed_is_the_only_change(
    org: Organisation, accounts: tuple[Account, Account]
) -> None:
    entry = make_entry(org, accounts, status=JournalStatus.POSTED)
    JournalEntry.objects.filter(pk=entry.pk).update(
        status=JournalStatus.REVERSED, updated_at=timezone.now()
    )
    entry.refresh_from_db()
    assert entry.status == JournalStatus.REVERSED
    # Reversed is final.
    refused_by_database(
        lambda: JournalEntry.objects.filter(pk=entry.pk).update(status=JournalStatus.POSTED)
    )


@pytest.mark.parametrize("status", [JournalStatus.DRAFT, JournalStatus.AWAITING_APPROVAL])
def test_drafts_and_awaiting_approval_stay_editable(
    org: Organisation, accounts: tuple[Account, Account], status: str
) -> None:
    entry = make_entry(org, accounts, status=status)
    cash, _ = accounts
    JournalLine.objects.filter(entry=entry, line_no=1).update(debit=D("120.00"))
    line = JournalLine.objects.get(entry=entry, line_no=2)
    line.credit = D("120.00")
    line.save()
    JournalLine(entry=entry, account=cash, line_no=3, debit=D("1.00")).save()
    JournalLine.objects.get(entry=entry, line_no=3).delete()
    entry.narration = "Corrected"
    entry.save()
    assert JournalLine.objects.filter(entry=entry).count() == 2
    JournalLine.objects.filter(entry=entry).delete()
    entry.delete()
    assert not JournalEntry.objects.filter(pk=entry.pk).exists()


# ---- the Django guard ----------------------------------------------------------------------------


@pytest.mark.parametrize("status", LOCKED)
def test_guard_refuses_line_changes_with_a_readable_error(
    org: Organisation, accounts: tuple[Account, Account], status: str
) -> None:
    entry = make_entry(org, accounts, status=status, number=7)
    line = JournalLine.objects.get(entry=entry, line_no=1)
    line.description = "edited"
    with pytest.raises(JournalLocked) as error:
        line.save()
    assert error.value.code == "ledger.journal.locked"
    assert error.value.messages == [
        "Journal 7 is posted: it can't be changed or deleted. Reverse it instead."
    ]
    with pytest.raises(JournalLocked):
        line.delete()
    cash, _ = accounts
    with pytest.raises(JournalLocked):
        JournalLine(entry=entry, account=cash, line_no=9, debit=D("1")).save()


def test_guard_refuses_moving_a_line_out_of_a_posted_entry(
    org: Organisation, accounts: tuple[Account, Account]
) -> None:
    posted = make_entry(org, accounts, status=JournalStatus.POSTED)
    draft = make_entry(org, accounts, status=JournalStatus.DRAFT)
    line = JournalLine.objects.get(entry=posted, line_no=1)
    line.entry = draft
    with pytest.raises(JournalLocked):
        line.save()


@pytest.mark.parametrize("status", LOCKED)
def test_guard_refuses_entry_changes_and_deletion(
    org: Organisation, accounts: tuple[Account, Account], status: str
) -> None:
    entry = make_entry(org, accounts, status=status)
    entry.narration = "edited"
    with pytest.raises(JournalLocked):
        entry.save()
    entry.refresh_from_db()
    with pytest.raises(JournalLocked):
        entry.delete()
    with pytest.raises(JournalLocked):
        entry.soft_delete()


def test_guard_allows_posted_to_reversed_and_audits_it(
    org: Organisation, accounts: tuple[Account, Account]
) -> None:
    from numo9.audit.models import AuditEvent

    entry = make_entry(org, accounts, status=JournalStatus.POSTED)
    entry.status = JournalStatus.REVERSED
    entry.save()
    entry.refresh_from_db()
    assert entry.status == JournalStatus.REVERSED
    event = AuditEvent.objects.filter(action="ledger.journalentry.updated").order_by("-id").first()
    assert event is not None and event.changes["status"] == ["posted", "reversed"]
    entry.status = JournalStatus.POSTED
    with pytest.raises(JournalLocked):
        entry.save()


def test_even_an_unchanged_save_of_a_posted_entry_is_refused(
    org: Organisation, accounts: tuple[Account, Account]
) -> None:
    entry = make_entry(org, accounts, status=JournalStatus.POSTED)
    with pytest.raises(JournalLocked):
        entry.save()  # would rewrite updated_at
    refused_by_database(
        lambda: JournalEntry.objects.filter(pk=entry.pk).update(updated_at=timezone.now())
    )
