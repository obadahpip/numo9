"""G-05-T06 — tax audit report: every tax line with code, rate, basis, tax and who posted it;
flags on the fixture — override, late adjustment, journal source, restricted ITC, superseded."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.reports.engine import registry
from numo9.sales.models import InvoiceLine
from numo9.sales.posting import approve, void
from numo9.tenancy.context import org_context
from tests.sales_helpers import draft
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
D = Decimal
RANGE = {"date_from": Q2[0].isoformat(), "date_to": Q2[1].isoformat()}


@pytest.fixture
def books() -> dict[str, Any]:
    books = tax_books()
    org = books["org"]
    # an overridden code on an invoice line (G-02)
    made = draft(books["sales"], [("1", "100.00", "sales.ON.standard")], date=dt.date(2026, 6, 2))
    with org_context(org):
        InvoiceLine.objects.filter(document=made).update(tax_overridden=True)
    books["overridden"] = approve(made, books["owner"])
    # a voided invoice: superseded (its posting and its reversal)
    void(books["invoices"][1], books["owner"], reason="Twice")
    # a manual journal with a tax code, posted as a late adjustment
    with org_context(org):
        post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 20),
                late_adjustment=True,
                lines=[
                    LineSpec(books["expense"], debit=D("40.00"), tax_code="purchase.ON.standard"),
                    LineSpec(books["revenue"], credit=D("40.00")),
                ],
            ),
            user=books["owner"],
        )
    return books


def test_lines_with_their_flags(books: dict[str, Any]) -> None:
    result = registry.get("tax_audit").run(books["org"], RANGE)
    rows = result.rows
    flags = [set(r.drill["flags"]) for r in rows if r.drill]
    assert {"override"} in flags
    assert sum(1 for f in flags if "superseded" in f) == 2
    assert {"restricted_itc"} in flags
    assert {"journal_source", "late_adjustment"} in flags
    first = rows[0]
    assert first.values[0] == D("13.0000") and first.values[2] == D("130.00")
    assert first.drill is not None and first.drill["posted_by"]
    assert "sales.ON.standard" in first.label and first.label.startswith("2026-04-10 · JE-")
    total_tax = result.totals[0].values[2]
    assert total_tax == sum((r.values[2] or D("0") for r in rows), D("0"))


def test_plain_lines_have_no_flags(books: dict[str, Any]) -> None:
    result = registry.get("tax_audit").run(
        books["org"], {"date_from": "2026-05-05", "date_to": "2026-05-05"}
    )
    assert [r.drill["flags"] for r in result.rows if r.drill] == [[]]
