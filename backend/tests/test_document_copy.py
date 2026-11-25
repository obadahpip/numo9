"""D-03a-T10 — copy to invoice / quote: a new draft with the same header and identical lines (item,
description, quantity, price, discount, account, tax code, flag, tracking); invoice → invoice,
invoice → quote, quote → invoice (the counted lines only), quote → quote (options kept)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.sales.copying import copy_document
from numo9.sales.models import Invoice, Quote
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db
DAY = dt.date(2026, 7, 2)
FIELDS = (
    "description",
    "quantity",
    "unit_price",
    "discount_type",
    "discount_value",
    "account_id",
    "tax_code_id",
    "tax_overridden",
    "tracking",
)


def rows(document: Any) -> list[tuple[Any, ...]]:
    return [tuple(getattr(line, f) for f in FIELDS) for line in document.lines.order_by("position")]


@pytest.fixture
def books() -> dict[str, Any]:
    from tests.journal_helpers import people

    books = sales_books()
    books["owner"] = people(books["org"])["owner"]
    return books


def test_invoice_to_invoice_and_quote(books: dict[str, Any]) -> None:
    source = draft(
        books,
        [("3", "250.00", "sales.ON.standard"), ("1", "120.00", "")],
        reference="PO-7781",
        notes="Thanks",
    )
    source = approve(source, books["owner"])
    invoice = copy_document(source, "invoice", books["owner"], date=DAY)
    assert isinstance(invoice, Invoice)
    assert (invoice.status, invoice.number, invoice.date) == ("draft", "", DAY)
    assert (invoice.reference, invoice.notes, invoice.contact_id) == (
        "PO-7781",
        "Thanks",
        source.contact_id,
    )
    with org_context(books["org"]):
        assert rows(invoice) == rows(source)
        assert invoice.total == source.total
    as_quote = copy_document(source, "quote", books["owner"], date=DAY)
    assert (
        isinstance(as_quote, Quote) and as_quote.number == "QU-0001" and as_quote.status == "draft"
    )
    assert as_quote.expiry_date == DAY + dt.timedelta(days=30)
    with org_context(books["org"]):
        assert rows(as_quote) == rows(source)
        assert AuditEvent.objects.filter(action="sales.invoice.copied").count() == 1


def test_quote_to_invoice_counts_and_quote_to_quote_keeps_options(books: dict[str, Any]) -> None:
    source = quote(
        books,
        [
            {"price": "1000", "tax": "sales.ON.standard"},
            {"price": "200", "is_optional": True},
            {"price": "300", "alternative_group": "A"},
            {"price": "350", "alternative_group": "A", "selected": False},
        ],
        title="Fit-out",
    )
    invoice = copy_document(source, "invoice", books["owner"], date=DAY)
    with org_context(books["org"]):
        assert [line.unit_price for line in invoice.lines.order_by("position")] == [
            Decimal("1000"),
            Decimal("300"),
        ]
        assert invoice.total == source.total
    again = copy_document(source, "quote", books["owner"], date=DAY)
    with org_context(books["org"]):
        assert rows(again) == rows(source)
        flags = [
            (x.is_optional, x.alternative_group, x.selected)
            for x in again.lines.order_by("position")
        ]
    assert flags == [(False, "", True), (True, "", False), (False, "A", True), (False, "A", False)]
    assert (again.title, again.number) == ("Fit-out", "QU-0002")
