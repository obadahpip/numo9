"""D-03b-T10 — lock rules of a revision: an invoice dated in a filed GST/HST period can't be
revised without unlocking the period or setting ``late_adjustment`` — refused naming the period
and its confirmation, nothing written — even when the revision moves its date to an open period
(the reversal posts on the old date); the AR lock refuses, naming the lock, late or not."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.models import JournalEntry
from numo9.orgsettings.models import LockDate, TaxRegistration
from numo9.sales.models import InvoiceRevision
from numo9.sales.period_checks import PeriodRefused
from numo9.sales.posting import approve
from numo9.sales.revise import revise
from numo9.sales.revisions import build_revision
from numo9.tax import returns
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db
D = Decimal


def file_june(books: dict[str, Any]) -> FilingPeriod:
    """A monthly GST/HST registration whose June return is filed (confirmation GH-9)."""
    org = books["org"]
    with org_context(org):
        reg = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2026, 1, 1),
        )
        reg.save()
    switch_frequency(reg, "monthly", dt.date(2026, 1, 1), today=dt.date(2026, 6, 1))
    with org_context(org):
        june: FilingPeriod = FilingPeriod.objects.get(registration=reg, start=dt.date(2026, 6, 1))
    made = returns.prepare(june, books["owner"])
    returns.file(returns.review(made, books["adviser"]), books["owner"], confirmation_no="GH-9")
    return june


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["invoice"] = approve(
        draft(books, [("10", "100.00", "sales.ON.standard")]), books["owner"]
    )  # 15 Jun 2026: 1,000.00 + HST 130.00, then June is filed
    books["june"] = file_june(books)
    return books


def opened(books: dict[str, Any], **header: Any) -> Any:
    with org_context(books["org"]):
        books["invoice"].refresh_from_db()
        draft_ = build_revision(books["invoice"])
    draft_.lines[0]["quantity"] = D("9")
    draft_.header.update(header)
    draft_.reason = "Nine hours, not ten"
    return draft_


def nothing_written(books: dict[str, Any], version: int) -> None:
    invoice = books["invoice"]
    with org_context(books["org"]):
        invoice.refresh_from_db()
        assert (invoice.version, invoice.total) == (version, D("1130.00"))
        assert not InvoiceRevision.objects.filter(invoice=invoice, revision__gt=0).exists()
        assert not JournalEntry.objects.filter(reversal_of=invoice.journal_entry).exists()


def test_a_filed_period_without_the_flag_is_refused_naming_it(books: dict[str, Any]) -> None:
    version = books["invoice"].version
    with pytest.raises(PeriodRefused) as refused:
        revise(books["invoice"], opened(books), books["owner"])
    assert refused.value.code == "sales.invoice.filed_period"
    assert (refused.value.params or {})["period"]["start"] == "2026-06-01"
    message = str(refused.value.messages[0])
    assert "can't be revised" in message
    assert "GST/HST period 1 Jun 2026 – 30 Jun 2026, filed (confirmation GH-9)" in message
    assert "unlock the period" in message and "late adjustment" in message
    nothing_written(books, version)


def test_moving_out_of_the_filed_period_is_refused_too(books: dict[str, Any]) -> None:
    """The new date is open, but the reversal posts on 15 Jun — inside the filed period."""
    version = books["invoice"].version
    with pytest.raises(PeriodRefused) as refused:
        revise(
            books["invoice"],
            opened(books, date=dt.date(2026, 7, 10), due_date=dt.date(2026, 8, 9)),
            books["owner"],
        )
    assert refused.value.code == "sales.invoice.filed_period"
    assert "1 Jun 2026 – 30 Jun 2026" in str(refused.value.messages[0])
    nothing_written(books, version)


def test_the_ar_lock_refuses_even_as_a_late_adjustment(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ar", level="everyone", date=DAY).save()
    version = books["invoice"].version
    with pytest.raises(PeriodRefused) as refused:
        revise(books["invoice"], opened(books), books["owner"], late_adjustment=True)
    assert refused.value.code == "sales.invoice.locked"
    assert "can't be revised" in str(refused.value.messages[0])
    assert (refused.value.params or {})["lock"]["module"] == "ar"
    nothing_written(books, version)
