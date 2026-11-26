"""D-02-T09 — convert to invoice: an accepted quote becomes a draft invoice whose lines are the
quote's counted lines (the selected options) **line by line identical**; a deposit invoice raised
on acceptance is deducted as a last, untaxed credit line (the invoice total = the quote total less
the deposit); the quote is Invoiced and linked; a quote not accepted, or converted twice, is
refused; a voided deposit isn't deducted."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.sales import quotes as q
from numo9.sales.posting import approve, void
from numo9.sales.quote_invoicing import convert_to_invoice
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
TODAY = dt.date.today()
SAME = (
    "item_id",
    "description",
    "quantity",
    "unit_price",
    "discount_type",
    "discount_value",
    "account_id",
    "tax_code_id",
    "tax_overridden",
    "tracking",
    "net",
    "tax_amount",
    "amount",
)


def accepted(books: dict[str, Any], **fields: Any) -> Any:
    tax = "sales.ON.standard"
    item = quote(
        books,
        [
            {"description": "Cabinets", "quantity": "3", "price": "400", "tax": tax},
            {"description": "Install", "price": "150", "tax": tax, "is_optional": True},
            {"description": "Haul-away", "price": "80", "tax": tax, "is_optional": True},
            {"description": "Oak", "price": "900", "tax": tax, "alternative_group": "wood"},
            {"description": "Walnut", "price": "1300", "tax": tax, "alternative_group": "wood"},
        ],
        date=TODAY,
        expiry=TODAY + dt.timedelta(days=10),
        **fields,
    )
    with org_context(books["org"]):
        for line in item.lines.all():
            line.selected = line.description in ("Cabinets", "Install", "Walnut")
            line.save()
    q.recalculate(item)
    return q.accept(q.send(item))


def test_lines_identical_and_quote_invoiced() -> None:
    books = sales_books()
    item = accepted(books)
    invoice = convert_to_invoice(item, None)
    with org_context(books["org"]):
        item.refresh_from_db()
        lines = list(item.lines.order_by("position"))
        quote_lines = [line for line, take in zip(lines, q.counted(lines), strict=True) if take]
        invoice_lines = list(invoice.lines.order_by("position"))
        assert [line.description for line in quote_lines] == ["Cabinets", "Install", "Walnut"]
        assert len(invoice_lines) == len(quote_lines)
        for mine, theirs in zip(quote_lines, invoice_lines, strict=True):
            assert {f: getattr(mine, f) for f in SAME} == {f: getattr(theirs, f) for f in SAME}
        assert (invoice.status, invoice.contact_id, invoice.total) == (
            "draft",
            item.contact_id,
            item.total,
        )
        assert invoice.total == Decimal("2994.50")  # (1200 + 150 + 1300) × 1.13 = 2650 + 344.50 HST
    assert (item.status, item.invoice_id) == ("invoiced", invoice.pk)
    with pytest.raises(q.QuoteRefused) as twice:
        convert_to_invoice(item, None)
    assert twice.value.code == "sales.quote.not_accepted"
    draft = quote(books, [("1", "10", "sales.ON.standard")])
    with pytest.raises(q.QuoteRefused):
        convert_to_invoice(draft, None)


def test_deposit_deducted_as_a_credit_line() -> None:
    books = sales_books()
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    item = accepted(books, deposit_type="percent", deposit_value=Decimal("25"))
    with org_context(books["org"]):
        deposit = item.deposit_invoice
    assert deposit is not None and deposit.total == Decimal("748.63")  # 25 % of 2994.50
    deposit = approve(deposit, owner)
    invoice = convert_to_invoice(item, owner)
    with org_context(books["org"]):
        lines = list(invoice.lines.select_related("account").order_by("position"))
        last = lines[-1]
        assert len(lines) == 4
        assert last.description == f"Less deposit, invoice {deposit.number}"
        assert (last.unit_price, last.tax_code_id, last.tax_amount) == (
            Decimal("-748.63"),
            None,
            Decimal("0"),
        )
        assert last.account is not None and last.account.code == "2300"
        assert invoice.tax_total == Decimal("344.50")  # the full tax of the work
        assert invoice.total == Decimal("2994.50") - Decimal("748.63")
    posted = approve(invoice, owner)
    assert posted.status == "approved"


def test_voided_deposit_not_deducted() -> None:
    books = sales_books()
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    item = accepted(books, deposit_type="amount", deposit_value=Decimal("100"))
    with org_context(books["org"]):
        deposit = item.deposit_invoice
    void(approve(deposit, owner), owner, reason="Waived")
    invoice = convert_to_invoice(item, owner)
    with org_context(books["org"]):
        assert invoice.total == Decimal("2994.50") and invoice.lines.count() == 3
