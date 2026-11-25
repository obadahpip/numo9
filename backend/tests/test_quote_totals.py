"""D-02-T03 — quote totals cover the selected lines only: an optional line counts once ticked;
of an alternative group the selected line counts (the first selected one if several; none
selected adds nothing); every line keeps its own amount; the document discount applies to what
counts."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.sales.models import QuoteLine
from numo9.sales.quotes import counted, recalculate
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
D = Decimal
HST = "sales.ON.standard"


def lines(item: Any) -> list[QuoteLine]:
    return list(item.lines.order_by("position"))


def test_totals_change_with_the_selection() -> None:
    books = sales_books()
    item = quote(
        books,
        [
            {"price": "1000", "tax": HST},
            {"price": "200", "tax": HST, "is_optional": True},
            {"price": "300", "tax": HST, "alternative_group": "finish", "selected": True},
            {"price": "500", "tax": HST, "alternative_group": "finish", "selected": False},
        ],
    )
    assert (item.subtotal, item.tax_total, item.total) == (D("1300.00"), D("169.00"), D("1469.00"))
    with org_context(books["org"]):
        base, optional, satin, gloss = lines(item)
        assert optional.amount == D("200.00") and gloss.amount == D("500.00")  # own amounts kept
        optional.selected = True
        optional.save()
        satin.selected, gloss.selected = False, True
        satin.save()
        gloss.save()
        item = recalculate(item)
    assert (item.subtotal, item.total) == (D("1700.00"), D("1921.00"))
    with org_context(books["org"]):
        gloss.selected = False
        gloss.save()
        assert recalculate(item).subtotal == D("1200.00")  # a group with none selected


def test_first_selected_alternative_counts_and_discount() -> None:
    books = sales_books()
    item = quote(
        books,
        [
            {"price": "100", "alternative_group": "a"},
            {"price": "999", "alternative_group": "a"},
            {"price": "50", "is_optional": True},
        ],
        discount_type="percent",
        discount_value=D("10"),
    )
    with org_context(books["org"]):
        assert counted(lines(item)) == [True, False, False]
        item = recalculate(item)
    assert item.discount_total == D("10.00") and item.total == D("90.00")
