"""E-04-T04 — tax split of receipts: the amount includes the tax; net + tax = the receipt to the
cent; partial ITC by the category account (Meals and entertainment 50 %); mileage and receipts
without a code have no tax."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.models import Account
from numo9.purchases.expense_tax import claim_tax, receipt_split
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.expense_helpers import DAY, add_line, add_trip, expense_org, make_claim

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    org, who = expense_org()
    with org_context(org):
        meals = Account.objects.get(itc_restriction_pct=D("50"))
        office = Account.objects.filter(type="expense", itc_restriction_pct__isnull=True).order_by(
            "code"
        )[0]
    return {
        "org": org,
        "claim": make_claim(org, who["owner"]),
        "meals": meals,
        "office": office,
        "on": code_for("purchase.ON.standard", "purchase", DAY, org),
        "qc": code_for("purchase.QC.standard", "purchase", DAY, org),
    }


def test_hst_receipt_fully_claimable(books: dict[str, Any]) -> None:
    line = add_line(
        books["claim"],
        merchant="Staples",
        account=books["office"],
        tax_code=books["on"],
        amount=D("56.50"),
    )
    with org_context(books["org"]):
        split = receipt_split(line)
    assert (split.net, split.tax, split.claimable, split.cost) == (
        D("50.00"),
        D("6.50"),
        D("6.50"),
        D("0.00"),
    )
    assert split.expense == D("50.00")


def test_meals_receipt_half_itc(books: dict[str, Any]) -> None:
    line = add_line(
        books["claim"],
        merchant="Bistro 21",
        account=books["meals"],
        tax_code=books["on"],
        amount=D("56.50"),
    )
    with org_context(books["org"]):
        split = receipt_split(line)
    assert (split.claimable, split.cost, split.expense) == (D("3.25"), D("3.25"), D("53.25"))
    assert split.as_dict()["components"][0]["claimable"] == "3.25"


def test_quebec_receipt_gst_and_qst(books: dict[str, Any]) -> None:
    line = add_line(
        books["claim"],
        merchant="Café Rive",
        account=books["office"],
        tax_code=books["qc"],
        amount=D("114.98"),
    )
    with org_context(books["org"]):
        split = receipt_split(line)
    assert split.net == D("100.00")
    assert sorted(c.amount for c in split.line_tax.components) == [D("5.00"), D("9.98")]
    assert split.net + split.tax == D("114.98")


@pytest.mark.parametrize("amount", ["0.01", "1.13", "9.99", "123.45", "1000.00"])
def test_inclusive_split_always_adds_back(books: dict[str, Any], amount: str) -> None:
    line = add_line(books["claim"], account=books["office"], tax_code=books["on"], amount=D(amount))
    with org_context(books["org"]):
        split = receipt_split(line)
    assert split.net + split.tax == D(amount)
    assert split.claimable + split.cost == split.tax


def test_no_code_and_mileage_have_no_tax(books: dict[str, Any]) -> None:
    foreign = add_line(
        books["claim"], merchant="Hotel NYC", account=books["office"], amount=D("200")
    )
    trip = add_trip(books["claim"], "100", amount=D("73.00"))
    with org_context(books["org"]):
        assert receipt_split(foreign).tax == 0
        assert receipt_split(trip).expense == D("73.00")
        add_line(books["claim"], account=books["meals"], tax_code=books["on"], amount=D("56.50"))
        total = claim_tax(books["claim"])
    assert total.gross == D("329.50")
    assert total.claimable == D("3.25")
    assert total.expense + total.claimable == total.gross
