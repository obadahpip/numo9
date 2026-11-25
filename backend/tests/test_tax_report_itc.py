"""G-05-T07 — ITC/ITR detail: purchases only, each line's recoverable and non-recoverable tax;
meals at 50 % show half recoverable, half non-recoverable, with the restriction."""

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


def test_meals_split_and_totals(books: dict[str, Any]) -> None:
    result = registry.get("itc_detail").run(books["org"], RANGE)
    rows = [r for r in result.rows if r.kind == "row"]
    assert len(rows) == 2  # purchases only: no sale appears
    meals = next(r for r in rows if r.drill and r.drill["restricted"])
    assert meals.values == [D("26.00"), D("13.00"), D("13.00")]
    assert meals.drill is not None and meals.drill["restriction"] == "50 % claimable"
    assert str(books["meals"]) in meals.label
    plain = next(r for r in rows if r is not meals)
    assert plain.values == [D("130.00"), D("130.00"), D("0.00")]
    assert plain.drill is not None and plain.drill["restriction"] == ""
    assert result.totals[0].values == [D("156.00"), D("143.00"), D("13.00")]
