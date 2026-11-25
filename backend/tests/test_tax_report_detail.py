"""G-05-T05 — tax detail by document: one row per document and component, with its number,
customer or supplier and a drill-down link to the document; totals equal the summary's."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.reports.engine import registry
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
D = Decimal
RANGE = {"date_from": Q2[0].isoformat(), "date_to": Q2[1].isoformat()}


@pytest.fixture
def books() -> dict[str, Any]:
    return tax_books()


def test_rows_per_document_with_the_drill_down(books: dict[str, Any]) -> None:
    result = registry.get("tax_detail").run(books["org"], RANGE)
    rows = [r for r in result.rows if r.kind == "row"]
    assert len(rows) == 4
    first = rows[0]
    invoice = books["invoices"][0]
    assert first.label == f"2026-04-10 · {invoice.number} · Maple Leaf Supply Ltd."
    assert first.values == [D("1000.00"), D("130.00"), D("0"), D("0")]
    assert first.drill is not None
    assert (
        first.drill["url"]
        == f"/o/{books['org'].public_id}/sales/invoices/{invoice.public_id}/email"
    )
    assert first.drill["type"] == "sales.invoice" and first.drill["codes"] == "sales.ON.standard"
    meals = next(r for r in rows if "Cedar Supply" in r.label and r.values[3])
    assert meals.values == [D("200.00"), D("26.00"), D("13.00"), D("13.00")]
    summary = registry.get("tax_summary").run(books["org"], RANGE)
    tax = summary.totals[0].values[1] + summary.totals[1].values[1]  # type: ignore[operator]
    assert result.totals[0].values[1] == tax


def test_narrowed_to_a_code_and_side(books: dict[str, Any]) -> None:
    result = registry.get("tax_detail").run(
        books["org"], {**RANGE, "side": "purchase", "code": "purchase.ON.standard"}
    )
    assert [r.values[2] for r in result.rows if r.kind == "row"] == [D("13.00"), D("130.00")]
    assert result.totals[0].values[2] == D("143.00")


def test_a_voided_document_drops_out_of_the_list(books: dict[str, Any]) -> None:
    from numo9.sales.posting import void

    void(books["invoices"][1], books["owner"], reason="Twice")
    result = registry.get("tax_detail").run(books["org"], {**RANGE, "side": "sales"})
    assert [r.values[1] for r in result.rows if r.kind == "row"] == [D("130.00")]
