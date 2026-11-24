"""E-02-T09 — voiding a bill and lock checks: the journal is reversed (the bill nets to zero in
the ledger), Void, number kept, PO billed quantities back, supplier invoice number free again,
audited with the reason; drafts, paid bills and released holdbacks can't be voided; a date in a
locked period is refused **naming the lock** and changes nothing."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalLine
from numo9.orgsettings.locks import LockedPeriod
from numo9.orgsettings.models import LockDate
from numo9.purchases.bill_posting import BillRefused, approve, release_holdback, void
from numo9.purchases.models import Bill, BillStatus, HoldbackType
from numo9.purchases.uniqueness import number_conflict
from numo9.tenancy.context import org_context
from tests.bill_helpers import DAY, bill, bill_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return bill_books()


def test_void_reverses_and_keeps_the_number(books: dict[str, Any]) -> None:
    posted = approve(bill(books, [("1", "400.00")], supplier_invoice_no="V-1"), books["owner"])
    done = void(posted, books["owner"], reason="Entered twice")
    assert (done.status, done.number) == (BillStatus.VOID, "BILL-0001")
    with org_context(books["org"]):
        totals = JournalLine.objects.filter(
            entry__in=[done.journal_entry, done.void_entry], account=books["expense"]
        ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
        assert totals["debit"] == totals["credit"] == Decimal("400.00")
        event = AuditEvent.objects.get(action="purchases.bill.voided")
        assert event.meta["reason"] == "Entered twice"
        assert number_conflict(books["supplier"], "V-1") is None  # free again
    again = approve(bill(books, [("1", "400.00")], supplier_invoice_no="V-1"), books["owner"])
    assert again.number == "BILL-0002"


def test_what_cant_be_voided(books: dict[str, Any]) -> None:
    draft = bill(books, [("1", "10.00")], supplier_invoice_no="V-2")
    with pytest.raises(BillRefused) as refused:
        void(draft, books["owner"])
    assert refused.value.code == "purchases.bill.not_voidable"
    paid = approve(bill(books, [("1", "10.00")], supplier_invoice_no="V-3"), books["owner"])
    with org_context(books["org"]):
        Bill._base_manager.filter(pk=paid.pk).update(amount_paid=Decimal("5.00"))
    with pytest.raises(BillRefused):
        void(paid, books["owner"])
    held = approve(
        bill(
            books,
            [("1", "100.00")],
            supplier_invoice_no="V-4",
            holdback_type=HoldbackType.AMOUNT,
            holdback_value=Decimal("10"),
        ),
        books["owner"],
    )
    release_holdback(held, books["owner"], date=DAY)
    with pytest.raises(BillRefused) as released:
        void(held, books["owner"])
    assert "holdback" in str(released.value.messages[0])


def test_a_locked_date_is_refused_naming_the_lock(books: dict[str, Any]) -> None:
    posted = approve(bill(books, [("1", "10.00")], supplier_invoice_no="V-5"), books["owner"])
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ap", level="everyone", date=DAY).save()
    with pytest.raises(LockedPeriod) as locked:
        void(posted, books["owner"])
    assert locked.value.violation.as_dict() == {
        "module": "ap",
        "level": "everyone",
        "date": "2026-06-15",
    }
    assert "The Purchases and accounts payable lock date is 2026-06-15" in str(locked.value.detail)
    with org_context(books["org"]):
        posted.refresh_from_db()
    assert posted.status == BillStatus.AWAITING_PAYMENT and posted.void_entry is None
    later = void(posted, books["owner"], date=dt.date(2026, 6, 20))
    assert later.void_entry is not None and later.void_entry.date == dt.date(2026, 6, 20)
    with pytest.raises(LockedPeriod):  # a new bill before the lock can't be approved either
        approve(bill(books, [("1", "10.00")], supplier_invoice_no="V-6"), books["owner"])
