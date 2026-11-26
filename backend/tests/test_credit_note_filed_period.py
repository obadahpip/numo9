"""D-06-T06 — a credit note dated in a filed GST/HST period: refused naming the period and its
confirmation number; approved with ``late_adjustment=True`` it posts on its own date and its tax
lowers the next open return (line 107); the AR lock is refused naming the lock, late or not."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.orgsettings.models import LockDate, TaxRegistration
from numo9.sales.credit_notes import approve
from numo9.sales.models import CreditNote, CreditNoteLine
from numo9.sales.period_checks import PeriodRefused
from numo9.tax import returns
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod, LateAdjustment
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, sales_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
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
    returns.file(returns.review(made, books["adviser"]), books["owner"], confirmation_no="GH-9")
    books["june"] = june
    return books


def credit_note(books: dict[str, Any], day: dt.date = DAY) -> CreditNote:
    from numo9.sales.credit_notes import recalculate

    org = books["org"]
    with org_context(org):
        note = CreditNote(organisation=org, contact=books["customers"]["ON"], date=day)
        note.save()
        CreditNoteLine(
            organisation=org,
            document=note,
            position=0,
            description="Returned chair",
            quantity=D("1"),
            unit_price=D("100.00"),
            account=books["revenue"],
            tax_code=code_for("sales.ON.standard", "sales", day, org),
        ).save()
    return recalculate(note)


def test_a_filed_period_is_refused_naming_it(books: dict[str, Any]) -> None:
    note = credit_note(books)
    with pytest.raises(PeriodRefused) as refused:
        approve(note, books["owner"])
    assert refused.value.code == "sales.invoice.filed_period"
    message = str(refused.value.messages[0])
    assert "GST/HST period 1 Jun 2026 – 30 Jun 2026, filed (confirmation GH-9)" in message
    with org_context(books["org"]):
        note.refresh_from_db()
    assert (note.status, note.number) == ("draft", "")


def test_late_adjustment_posts_and_lowers_the_next_return(books: dict[str, Any]) -> None:
    done = approve(credit_note(books), books["owner"], late_adjustment=True)
    assert done.status == "approved" and done.journal_entry.date == DAY
    with org_context(books["org"]):
        (row,) = LateAdjustment.objects.all()
        assert (row.filed_period, row.line, row.amount) == (books["june"], "107", D("13.00"))
        assert row.target_period.start == dt.date(2026, 7, 1)


def test_the_ar_lock_is_refused_even_late(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        LockDate(organisation=books["org"], module="ar", level="everyone", date=DAY).save()
    with pytest.raises(PeriodRefused) as refused:
        approve(credit_note(books), books["owner"], late_adjustment=True)
    assert refused.value.code == "sales.invoice.locked"
