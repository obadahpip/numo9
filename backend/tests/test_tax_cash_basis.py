"""G-05-T03 — cash-basis allocator: a document's tax is recognised in proportion to its payments
dated in the range (a 50 % paid invoice reports 50 % of its tax); other lines count on their
date."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from numo9.tax.cash_basis import (
    cash_basis_lines,
    recognised_lines,
    register_payment_source,
    unregister_payment_source,
)
from numo9.tenancy.context import org_context
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
D = Decimal


class FakePayments:
    """Payments by document public id: [(date, amount)]; totals from the documents."""

    def __init__(self, totals: dict[str, Decimal]) -> None:
        self.source_types: tuple[str, ...] = ("sales.invoice", "purchases.bill")
        self.totals = totals
        self.paid: dict[str, list[tuple[dt.date, Decimal]]] = {}

    def payments(
        self, organisation: Any, refs: list[str], start: dt.date, end: dt.date
    ) -> dict[str, tuple[Decimal, Decimal]]:
        return {
            ref: (
                sum((a for d, a in self.paid.get(ref, []) if start <= d <= end), D("0")),
                self.totals[ref],
            )
            for ref in refs
            if ref in self.totals
        }


@pytest.fixture
def books() -> Iterator[dict[str, Any]]:
    made = tax_books()
    totals = {str(d.public_id): d.total for d in (*made["invoices"], *made["bills"])}
    source = FakePayments(totals)
    register_payment_source(source)
    made["payments"] = source
    yield made
    unregister_payment_source(source)


def total(rows: Any, name: str = "tax", side: str | None = None) -> Decimal:
    return sum((getattr(r, name) for r in rows if side is None or r.side == side), D("0"))


def test_half_paid_invoice_reports_half_its_tax(books: dict[str, Any]) -> None:
    first = books["invoices"][0]
    books["payments"].paid[str(first.public_id)] = [(dt.date(2026, 5, 1), D("565.00"))]
    with org_context(books["org"]):
        rows = cash_basis_lines(books["org"], *Q2, side="sales")
    assert total(rows) == D("65.00") and total(rows, "basis") == D("500.00")
    assert [r.ratio for r in rows] == [D("0.5")]


def test_payments_outside_the_range_wait(books: dict[str, Any]) -> None:
    first = books["invoices"][0]
    books["payments"].paid[str(first.public_id)] = [
        (dt.date(2026, 3, 1), D("100.00")),
        (dt.date(2026, 7, 2), D("1030.00")),
    ]
    with org_context(books["org"]):
        assert cash_basis_lines(books["org"], *Q2, side="sales") == []
        q3 = cash_basis_lines(books["org"], dt.date(2026, 7, 1), dt.date(2026, 9, 30))
    assert total(q3, side="sales") == D("118.50")  # 130.00 × 1030 / 1130 = 118.4956


def test_bills_by_payment_and_recoverable_scaled(books: dict[str, Any]) -> None:
    meals, supplies = books["bills"]
    books["payments"].paid[str(meals.public_id)] = [(dt.date(2026, 6, 1), meals.total)]
    books["payments"].paid[str(supplies.public_id)] = [(dt.date(2026, 6, 1), D("282.50"))]
    with org_context(books["org"]):
        rows = cash_basis_lines(books["org"], *Q2, side="purchase")
    assert total(rows) == D("26.00") + D("32.50")
    assert total(rows, "recoverable") == D("13.00") + D("32.50")
    assert total(rows, "non_recoverable") == D("13.00")


def test_accrual_through_the_same_entry_point(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        accrued = recognised_lines(books["org"], *Q2, basis="accrual", side="sales")
        cash = recognised_lines(books["org"], *Q2, basis="cash", side="sales")
    assert total(accrued) == D("195.00") and total(cash) == D("0")
    assert accrued[0].code == "sales.ON.standard"  # the stored line's fields read through
