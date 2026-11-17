"""C-02-T10 — ``reverse()`` service. Acceptance: reversal of a reversal is refused; nets to 0.

Covers: the mirror entry (debits ↔ credits, same books, contacts, tracking, tax codes), its own
number, type ``reversal``, link both ways, same source, default and chosen dates, narration; the
original becomes Reversed (status only, append-only kept) with an audit event; each book's trial
balance nets to zero; reversing twice, reversing a reversal, reversing a draft are refused; the
reversal date is checked against the lock (and nothing changes when refused); the original is
row-locked (two reversals in parallel: one wins).
"""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Iterator
from decimal import Decimal

import pytest
from django.db import connection

from numo9.audit.models import AuditEvent
from numo9.ledger.models import Account, Book, JournalEntry, JournalStatus
from numo9.ledger.services import (
    IllegalTransition,
    post_journal,
    reverse,
    save_draft,
)
from numo9.ledger.trial_balance import trial_balance
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.ledger_helpers import account

DATE = dt.date(2026, 4, 15)


@pytest.fixture
def org(db: None) -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def acc(org: Organisation) -> dict[str, Account]:
    with org_context(org):
        return {
            "ar": account(org, "1100", "Accounts receivable", subtype="current_asset"),
            "sales": account(org, "4000", "Sales", subtype="revenue"),
            "gst": account(org, "2200", "GST/HST payable", subtype="current_liability"),
            "amort": account(org, "6400", "Amortization", subtype="amortisation"),
            "accum": account(
                org, "1810", "Accumulated amortization", subtype="accumulated_amortisation"
            ),
        }


def invoice(org: Organisation, acc: dict[str, Account]) -> JournalEntry:
    customer = contact(org, "Érable Distribution inc.")
    return post_journal(
        JournalSpec(
            date=DATE,
            type="sales",
            narration="Invoice INV-0042",
            source_type="sales.Invoice",
            source_id="inv-42",
            lines=(
                LineSpec(acc["ar"], debit=Decimal("1130.00"), contact=customer),
                LineSpec(acc["sales"], credit=Decimal("1000.00"), tracking={"region": "east"}),
                LineSpec(acc["gst"], credit=Decimal("130.00"), tax_code="HST-ON"),
                LineSpec(acc["amort"], debit=Decimal("40.00"), book=Book.TAX),
                LineSpec(acc["accum"], credit=Decimal("40.00"), book=Book.TAX),
            ),
        ),
        user=None,
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_mirror_entry_nets_to_zero(org: Organisation, acc: dict[str, Account]) -> None:
    original = invoice(org, acc)
    reversal = reverse(original, user=None)
    assert reversal.number == 2 and reversal.type == "reversal"
    assert reversal.reversal_of == original and reversal.date == DATE
    assert (reversal.source_type, reversal.source_id) == ("sales.Invoice", "inv-42")
    assert reversal.narration == "Reversal of JE-000001"
    original.refresh_from_db()
    assert original.status == JournalStatus.REVERSED and original.reversed_by == reversal
    mirrored = [
        (line.account.code, line.debit, line.credit, line.book, line.contact_id, line.tax_code)
        for line in reversal.lines.order_by("line_no").select_related("account")
    ]
    assert mirrored == [
        (
            line.account.code,
            line.credit,
            line.debit,
            line.book,
            line.contact_id,
            line.tax_code,
        )
        for line in original.lines.order_by("line_no").select_related("account")
    ]
    assert reversal.lines.get(line_no=2).tracking == {"region": "east"}
    for book in ("accounting", "tax"):
        tb = trial_balance(book, include_zero=True)
        assert tb.balanced and all(row.balance == 0 for row in tb.rows)
    event = AuditEvent.objects.get(action="ledger.journalentry.reversed")
    assert event.object_id == str(original.public_id)
    assert event.meta["reversed_by"] == "JE-000002"


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_reversal_of_reversal_and_twice_are_refused(
    org: Organisation, acc: dict[str, Account]
) -> None:
    original = invoice(org, acc)
    reversal = reverse(original, user=None)
    with pytest.raises(IllegalTransition) as again:
        reverse(original, user=None)
    assert again.value.code == "ledger.journal.illegal_transition"
    with pytest.raises(IllegalTransition) as nested:
        reverse(reversal, user=None)
    assert nested.value.code == "ledger.journal.reversal_of_reversal"
    assert JournalEntry.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_a_draft_cant_be_reversed(acc: dict[str, Account]) -> None:
    draft = save_draft(
        JournalSpec(
            date=DATE,
            lines=(
                LineSpec(acc["ar"], debit=Decimal("5.00")),
                LineSpec(acc["sales"], credit=Decimal("5.00")),
            ),
        )
    )
    with pytest.raises(IllegalTransition):
        reverse(draft, user=None)


@pytest.mark.django_db
@pytest.mark.usefixtures("_active")
def test_reversal_date_and_lock(org: Organisation, acc: dict[str, Account]) -> None:
    original = invoice(org, acc)
    LockDate(organisation=org, module="gl", level="everyone", date=DATE).save()
    with pytest.raises(LockedPeriod):
        reverse(original, user=None)  # dated like the original: locked
    original.refresh_from_db()
    assert original.status == JournalStatus.POSTED and JournalEntry.objects.count() == 1
    reversal = reverse(original, date=dt.date(2026, 5, 1), narration="Wrong customer", user=None)
    assert reversal.date == dt.date(2026, 5, 1) and reversal.narration == "Wrong customer"
    assert reversal.number == 2  # the refused attempt used no number


@pytest.mark.django_db(transaction=True)
def test_two_reversals_in_parallel_one_wins(org: Organisation, acc: dict[str, Account]) -> None:
    with org_context(org):
        original = invoice(org, acc)
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt() -> None:
        try:
            with org_context(org):
                barrier.wait()
                reverse(JournalEntry.objects.get(pk=original.pk), user=None)
            outcomes.append("reversed")
        except IllegalTransition:
            outcomes.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["refused", "reversed"]
    with org_context(org):
        assert JournalEntry.objects.filter(type="reversal").count() == 1
