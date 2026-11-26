"""C-05-T05 — finalising the conversion: refused while the difference isn't 0.00 or a control
line doesn't equal its documents; otherwise one opening journal (``is_opening``) posted
atomically and the session locked.

Acceptance: unbalanced → an error naming the difference, nothing posted, still a draft;
balanced → the journal posted (AR/AP per contact), the session finalised and closed to changes.
Integration: an opening invoice is then paid like any other and the customer's AR clears; a
refusal by the posting engine (GL lock) leaves the session a draft.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db.models import Sum

from numo9.banking.services import create_bank_account
from numo9.conversion.documents import add_opening_bill, add_opening_invoice
from numo9.conversion.finalise import ConversionRefused, finalise
from numo9.conversion.models import ConversionSession
from numo9.conversion.services import set_line
from numo9.ledger.models import JournalEntry, JournalLine
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.sales.allocations import open_balance
from numo9.sales.receipts import receive_payment
from numo9.tenancy.context import org_context
from tests.conversion_helpers import BEFORE, CONVERSION_DATE, acct, conversion_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return conversion_books()


def codes(error: ValidationError) -> set[str]:
    if hasattr(error, "error_dict"):
        return {e.code for items in error.error_dict.values() for e in items if e.code}
    return {e.code for e in error.error_list if e.code}


def balanced(books: dict[str, Any]) -> None:
    """Chequing 5 000, AR 1 500 (two customers), AP 300, shares 100, retained earnings 6 100."""
    session = books["session"]
    add_opening_invoice(
        session, contact=books["customers"]["ON"], number="INV-1", date=BEFORE, total="1000.00"
    )
    add_opening_invoice(
        session,
        contact=books["customers"]["BC"],
        number="INV-2",
        date=BEFORE,
        total="900.00",
        outstanding="500.00",
    )
    add_opening_bill(
        session, contact=books["supplier"], supplier_invoice_no="S1", date=BEFORE, total="300.00"
    )
    set_line(session, acct(books, "1010"), debit="5000.00")
    set_line(session, acct(books, "1100"), debit="1500.00")
    set_line(session, acct(books, "2000"), credit="300.00")
    set_line(session, acct(books, "3000"), credit="100.00")
    set_line(session, acct(books, "3200"), credit="6100.00")


def test_unbalanced_refused_naming_the_difference(books: dict[str, Any]) -> None:
    session = books["session"]
    set_line(session, acct(books, "1010"), debit="120450.00")
    set_line(session, acct(books, "3200"), credit="120437.50")
    with pytest.raises(ConversionRefused) as caught:
        finalise(session, books["owner"])
    assert caught.value.code == "conversion.unbalanced"
    assert "Difference 12.50" in caught.value.messages[0]
    assert caught.value.params == {
        "difference": "12.50",
        "debits": "120450.00",
        "credits": "120437.50",
    }
    with org_context(books["org"]):
        assert not JournalEntry.objects.exists()
        session.refresh_from_db()
        assert session.status == "draft" and session.opening_entry is None


def test_control_mismatch_refused(books: dict[str, Any]) -> None:
    balanced(books)
    session = books["session"]
    set_line(session, acct(books, "1100"), debit="1400.00")
    set_line(session, acct(books, "3200"), credit="6000.00")
    with pytest.raises(ConversionRefused) as caught:
        finalise(session, books["owner"])
    assert caught.value.code == "conversion.control_mismatch"
    assert "1,400.00" in caught.value.messages[0] and "1,500.00" in caught.value.messages[0]


def test_balanced_posts_one_opening_journal(books: dict[str, Any]) -> None:
    balanced(books)
    session = finalise(books["session"], books["owner"])
    with org_context(books["org"]):
        (entry,) = JournalEntry.objects.all()
        assert session.status == "finalised" and session.opening_entry_id == entry.pk
        assert session.finalised_by == books["owner"] and session.finalised_at is not None
        assert entry.is_opening and entry.status == "posted" and entry.number
        assert (entry.type, entry.journal_type, entry.date) == (
            "opening",
            "adjusting",
            CONVERSION_DATE,
        )
        assert entry.source_type == "conversion.session"
        assert entry.source_id == str(session.public_id)
        rows = [
            (line.account.code, line.debit, line.credit, getattr(line.contact, "display_name", ""))
            for line in JournalLine.objects.filter(entry=entry).select_related("account", "contact")
        ]
        assert sorted(rows) == sorted(
            [
                ("1010", Decimal("5000.00"), Decimal("0.00"), ""),
                ("1100", Decimal("500.00"), Decimal("0.00"), "BC Customer Ltd"),
                ("1100", Decimal("1000.00"), Decimal("0.00"), "ON Customer Ltd"),
                ("2000", Decimal("0.00"), Decimal("300.00"), "Cedar Supply Co."),
                ("3000", Decimal("0.00"), Decimal("100.00"), ""),
                ("3200", Decimal("0.00"), Decimal("6100.00"), ""),
            ]
        )
    # Locked: no more lines, documents or finalising.
    with pytest.raises(ValidationError) as caught:
        set_line(session, acct(books, "1020"), debit="1.00")
    assert "conversion.session.finalised" in codes(caught.value)
    with pytest.raises(ValidationError) as caught:
        add_opening_invoice(
            session, contact=books["customers"]["ON"], number="X", date=BEFORE, total="1"
        )
    assert "conversion.session.finalised" in codes(caught.value)
    with pytest.raises(ConversionRefused) as again:
        finalise(session, books["owner"])
    assert again.value.code == "conversion.session.finalised"


def test_year_start_rolls_profit_and_loss_into_retained_earnings(books: dict[str, Any]) -> None:
    session = books["session"]  # 1 Jan 2026: the first day of the fiscal year (31 Dec year end)
    set_line(session, acct(books, "1010"), debit="3000.00")
    set_line(session, acct(books, "4000"), credit="10000.00")  # last year's sales
    set_line(session, acct(books, "5000"), debit="7000.00")  # and costs
    finalise(session, books["owner"])
    with org_context(books["org"]):
        rows = sorted(
            (line.account.code, line.debit, line.credit)
            for line in JournalLine.objects.select_related("account")
        )
    assert rows == [
        ("1010", Decimal("3000.00"), Decimal("0.00")),
        ("3200", Decimal("0.00"), Decimal("3000.00")),
    ]


def test_mid_year_posts_profit_and_loss_as_entered(books: dict[str, Any]) -> None:
    session = books["session"]
    with org_context(books["org"]):
        ConversionSession._base_manager.filter(pk=session.pk).update(
            conversion_date=dt.date(2026, 4, 1)
        )
        session.refresh_from_db()
    set_line(session, acct(books, "1010"), debit="3000.00")
    set_line(session, acct(books, "4000"), credit="10000.00")
    set_line(session, acct(books, "5000"), debit="7000.00")
    finalise(session, books["owner"])
    with org_context(books["org"]):
        codes = sorted(line.account.code for line in JournalLine.objects.select_related("account"))
    assert codes == ["1010", "4000", "5000"]


def test_gl_lock_refusal_leaves_a_draft(books: dict[str, Any]) -> None:
    balanced(books)
    with org_context(books["org"]):
        lock = LockDate(organisation=books["org"], module="gl", level="everyone")
        lock.set_lock(CONVERSION_DATE)
        lock.save()
    with pytest.raises(LockedPeriod):
        finalise(books["session"], books["owner"])
    with org_context(books["org"]):
        assert not JournalEntry.objects.exists()
        session = ConversionSession.objects.get()
        assert session.status == "draft"


def test_opening_invoice_paid_after_finalise(books: dict[str, Any]) -> None:
    balanced(books)
    finalise(books["session"], books["owner"])
    customer = books["customers"]["ON"]
    bank = create_bank_account(books["org"], type="chequing", display_name="TD Chequing")
    receive_payment(customer, bank, dt.date(2026, 1, 20), Decimal("1000.00"), books["owner"])
    with org_context(books["org"]):
        invoice = customer.organisation.sales_invoice_set.get(number="INV-1")
        assert invoice.amount_paid == Decimal("1000.00")
        assert open_balance(invoice) == Decimal("0.00")
        ar = JournalLine.objects.filter(account=acct(books, "1100"), contact=customer).aggregate(
            debit=Sum("debit"), credit=Sum("credit")
        )
        assert ar["debit"] - ar["credit"] == Decimal("0.00")
