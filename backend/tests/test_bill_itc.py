"""E-02-T04 — bills on the purchase-side calculator with partial ITC: 50 % meals — half the tax
to ITC, half to the expense; the tax code's own restriction; an organisation not registered for
GST/HST on the bill date claims nothing (all tax is cost); the posting preview balances."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.models import Account, SystemRole
from numo9.orgsettings.models import TaxRegistration
from numo9.purchases.bills import bill_preview, gst_registered, itc_split
from numo9.tenancy.context import org_context
from tests.bill_helpers import DAY, bill, bill_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    with org_context(books["org"]):
        TaxRegistration(
            organisation=books["org"],
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
        books["meals"] = Account.objects.get(itc_restriction_pct=Decimal("50"))
    return books


def lines_by_account(preview: Any) -> dict[str, tuple[Decimal, Decimal]]:
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for line in preview.lines:
        debit, credit = out.get(line.account.code, (Decimal("0"), Decimal("0")))
        out[line.account.code] = (debit + line.debit, credit + line.credit)
    return out


def test_meals_at_50_percent_half_tax_to_itc_half_to_expense(books: dict[str, Any]) -> None:
    meals = bill(books, [("1", "200.00")], tax="purchase.ON.standard", account=books["meals"])
    assert itc_split(meals) == [{"tax": "26.00", "claimable": "13.00", "cost": "13.00"}]
    shown = bill_preview(meals)
    with org_context(books["org"]):
        by_code = lines_by_account(shown)
        ap = Account.objects.get(system_role=SystemRole.AP)
    assert by_code[books["meals"].code] == (Decimal("213.00"), Decimal("0"))  # net + cost
    assert by_code[ap.code] == (Decimal("0"), Decimal("226.00"))
    itc = [code for code, (debit, _c) in by_code.items() if debit == Decimal("13.00")]
    assert len(itc) == 1  # the ITC control account takes the claimable half
    assert sum(line.debit for line in shown.lines) == sum(line.credit for line in shown.lines)


def test_full_itc_on_an_ordinary_expense(books: dict[str, Any]) -> None:
    plain = bill(books, [("2", "50.00")], tax="purchase.ON.standard")
    assert itc_split(plain) == [{"tax": "13.00", "claimable": "13.00", "cost": "0.00"}]


def test_restricted_tax_code(books: dict[str, Any]) -> None:
    half = bill(books, [("1", "100.00")], tax="purchase.ON.standard.itc50")
    assert itc_split(half) == [{"tax": "13.00", "claimable": "6.50", "cost": "6.50"}]


def test_no_itc_before_the_registration(books: dict[str, Any]) -> None:
    early = dt.date(2019, 6, 1)
    assert gst_registered(books["org"], DAY) and not gst_registered(books["org"], early)
    before = bill(books, [("1", "100.00")], tax="purchase.ON.standard", date=early)
    assert itc_split(before) == [{"tax": "13.00", "claimable": "0.00", "cost": "13.00"}]
    with org_context(books["org"]):
        by_code = lines_by_account(bill_preview(before))
    assert by_code[books["expense"].code] == (Decimal("113.00"), Decimal("0"))
