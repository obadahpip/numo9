"""G-05-T08 — tax-to-GL tie-out: each control account's GL movement against the tax lines;
difference 0.00 on clean books; a journal posted straight to GST/HST payable is the difference
and is named."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import reverse
from numo9.reports.engine import registry
from numo9.tenancy.context import org_context
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
D = Decimal
RANGE = {"date_from": Q2[0].isoformat(), "date_to": Q2[1].isoformat()}


@pytest.fixture
def books() -> dict[str, Any]:
    return tax_books()


def rows(result: Any) -> dict[str, Any]:
    return {r.key: r for r in result.rows}


def test_injected_journal_is_the_difference_and_is_named(books: dict[str, Any]) -> None:
    result = registry.get("tax_tie_out").run(books["org"], RANGE)
    gst = rows(result)["control:gst_hst_payable"]
    assert gst.values == [D("205.00"), D("195.00"), D("10.00")]
    assert gst.drill is not None and gst.drill["ties"] is False
    (journal,) = gst.drill["journals"]
    assert journal["narration"] == "GST correction" and journal["amount"] == "10.00"
    itc = rows(result)["control:itc_receivable"]
    assert itc.values == [D("143.00"), D("143.00"), D("0.00")]
    assert result.totals[0].values[2] == D("10.00")
    assert [a["code"] for a in result.alerts] == ["tax.tie_out.difference"]
    assert result.alerts[0]["level"] == "error"


def test_clean_books_tie(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        reverse(books["direct"], user=books["owner"])  # take the stray journal out
    result = registry.get("tax_tie_out").run(books["org"], RANGE)
    assert all(r.values[2] == D("0.00") for r in result.rows)
    assert [a["code"] for a in result.alerts] == ["tax.tie_out.ties"]
    gst = rows(result)["control:gst_hst_payable"]
    assert gst.values[0] == gst.values[1] == D("195.00")
    # both the stray journal and its reversal stay listed (they net to zero)
    assert gst.drill is not None and len(gst.drill["journals"]) == 2
