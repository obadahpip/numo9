"""G-03-T03 — the GST/HST return's lines (regular method) from the posted tax lines by tax-point
date and basis — the worked example of the line-mapping spec; line 103 = the GST/HST collected,
109 = 105 − 108; line 105 = the tax summary's collected total."""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.reports.engine import registry
from numo9.tax import returns
from numo9.tax.return_lines import regular_lines
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.tax_report_helpers import JUNE, june_books

pytestmark = pytest.mark.django_db
D = Decimal


def test_the_worked_example() -> None:
    books = june_books()
    with org_context(books["org"]):
        lines = regular_lines(books["period"])
    assert {k: str(v) for k, v in lines.items()} == {
        "101": "1200.00",
        "103": "130.00",
        "104": "0.00",
        "105": "130.00",
        "106": "63.50",
        "107": "0.00",
        "108": "63.50",
        "109": "66.50",
        "110": "0.00",
        "111": "0.00",
        "112": "0.00",
        "113A": "66.50",
        "113B": "0.00",
        "113C": "66.50",
        "114": "0.00",
        "115": "66.50",
    }
    summary = registry.get("tax_summary").run(
        books["org"],
        {"date_from": JUNE[0].isoformat(), "date_to": JUNE[1].isoformat(), "kind": "gst_hst"},
    )
    assert summary.totals[0].values[1] == lines["105"]  # line 105 = the tax report


def test_refund_when_no_taxable_sale() -> None:
    books = june_books(with_inv_0001=False)
    with org_context(books["org"]):
        lines = regular_lines(books["period"])
    assert (lines["101"], lines["103"], lines["109"], lines["114"], lines["115"]) == (
        D("200.00"),
        D("0.00"),
        D("-63.50"),
        D("63.50"),
        D("0.00"),
    )


def test_entries_feed_their_lines_and_the_return_stores_them() -> None:
    books = june_books()
    preparer = people(books["org"])["adviser"]
    draft = returns.prepare(books["period"], preparer)
    assert draft.lines["109"] == "66.50" and draft.lines["entries"] == {}
    again = returns.recalculate(
        draft, preparer, entries={"110": "20.00", "111": "6.50", "107": "1"}
    )
    assert (again.lines["107"], again.lines["112"], again.lines["113C"], again.lines["115"]) == (
        "1.00",
        "26.50",
        "39.00",
        "39.00",
    )
    assert again.lines["entries"] == {"110": "20.00", "111": "6.50", "107": "1.00"}
    kept = returns.recalculate(again, preparer)  # entries are kept on a recalculation
    assert kept.lines["115"] == "39.00"


def test_only_a_draft_is_recalculated() -> None:
    from numo9.tax.models import TaxError

    books = june_books()
    who = people(books["org"])
    draft = returns.prepare(books["period"], who["adviser"])
    reviewed = returns.review(draft, who["owner"])
    with pytest.raises(TaxError) as caught:
        returns.recalculate(reviewed, who["owner"])
    assert caught.value.code == "tax.return.status"
