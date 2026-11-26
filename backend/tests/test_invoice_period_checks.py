"""D-03a-T04 — lock and period checks at approve and void, with named messages: a date on or
before the AR lock is refused naming the lock and the invoice uses no number; a date in a filed
GST/HST period is refused naming the period and its confirmation number (posted knowingly as a
late adjustment it approves); a void dated in a filed period is refused the same way."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.orgsettings.models import LockDate, TaxRegistration
from numo9.sales.models import Invoice
from numo9.sales.period_checks import PeriodRefused
from numo9.sales.posting import approve, void
from numo9.tax import returns
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    return books


def _file_june(books: dict[str, Any]) -> FilingPeriod:
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
        june = FilingPeriod.objects.get(registration=reg, start=dt.date(2026, 6, 1))
    made = returns.prepare(june, books["owner"])
    returns.file(returns.review(made, books["adviser"]), books["owner"], confirmation_no="GH-77")
    return june


def test_the_ar_lock_is_named_and_no_number_is_used(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ar", level="everyone", date=DAY).save()
    invoice = draft(books, [("1", "100.00", "sales.ON.standard")])
    with pytest.raises(PeriodRefused) as refused:
        approve(invoice, books["owner"])
    error = refused.value
    assert error.code == "sales.invoice.locked"
    assert error.params == {"lock": {"module": "ar", "level": "everyone", "date": "2026-06-15"}}
    message = str(error.messages[0])
    assert "dated 15 Jun 2026" in message
    assert "Sales and accounts receivable lock date (15 Jun 2026, everyone)" in message
    with org_context(books["org"]):
        invoice.refresh_from_db()
    assert (invoice.status, invoice.number, invoice.journal_entry) == ("draft", "", None)
    later = draft(books, [("1", "100.00", "sales.ON.standard")], date=dt.date(2026, 6, 16))
    assert approve(later, books["owner"]).number  # after the lock: approved


def test_a_filed_gst_period_is_named(books: dict[str, Any]) -> None:
    _file_june(books)
    taxed = draft(books, [("1", "100.00", "sales.ON.standard")])
    with pytest.raises(PeriodRefused) as refused:
        approve(taxed, books["owner"])
    assert refused.value.code == "sales.invoice.filed_period"
    message = str(refused.value.messages[0])
    assert "GST/HST period 1 Jun 2026 – 30 Jun 2026, filed (confirmation GH-77)" in message
    with org_context(books["org"]):
        assert Invoice.objects.get(pk=taxed.pk).number == ""
    with returns.late_adjustments():  # posted knowingly: its tax goes to July's return
        assert approve(taxed, books["owner"]).status == "approved"


def test_a_void_into_a_filed_period_is_named(books: dict[str, Any]) -> None:
    invoice = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["owner"])
    _file_june(books)
    with pytest.raises(PeriodRefused) as refused:
        void(invoice, books["owner"])
    assert refused.value.code == "sales.invoice.filed_period"
    assert str(refused.value.messages[0]).startswith(f"{invoice.number} can't be voided")
    done = void(invoice, books["owner"], date=dt.date(2026, 7, 2))  # dated in the open July
    assert done.status == "void"
