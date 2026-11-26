"""G-03-T05 — drill-down of the return's lines: each line lists its source documents; the sum of
the list equals the line."""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.tax.return_lines import DRILL_LINES, drill_down, regular_lines
from numo9.tenancy.context import org_context
from tests.tax_report_helpers import june_books

pytestmark = pytest.mark.django_db
D = Decimal


def test_every_line_drills_to_documents_summing_to_it() -> None:
    books = june_books()
    period = books["period"]
    with org_context(books["org"]):
        lines = regular_lines(period)
        for line in DRILL_LINES:
            documents = drill_down(period, line)
            assert sum((D(d["amount"]) for d in documents), D("0")) == lines[line], line
        sales = drill_down(period, "101")
        purchases = drill_down(period, "106")
    numbers = {d["number"] for d in sales}
    assert numbers == {books["invoices"][0].number, books["invoices"][1].number}  # not the exempt
    assert all(d["url"].startswith(f"/o/{books['org'].public_id}/") for d in sales)
    assert sorted(D(d["amount"]) for d in purchases) == [D("5.00"), D("6.50"), D("52.00")]
    assert drill_down(period, "109") == []  # a sum of lines, not of documents
