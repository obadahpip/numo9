"""G-05-T04 — the tax summary report in the K-01 engine: per side, component and code; totals
per component equal the sum of the tax lines; net tax = collected − recoverable."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.reports.engine import ReportError, registry
from numo9.tax.models import TaxLine
from numo9.tenancy.context import org_context
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
D = Decimal
RANGE = {"date_from": Q2[0].isoformat(), "date_to": Q2[1].isoformat()}


@pytest.fixture
def books() -> dict[str, Any]:
    return tax_books()


def run(books: dict[str, Any], **params: Any) -> Any:
    return registry.get("tax_summary").run(books["org"], {**RANGE, **params})


def test_summary_rows_and_totals(books: dict[str, Any]) -> None:
    result = run(books)
    by_key = {r.key: r for r in result.rows}
    sales = by_key["code:sales:hst_on:sales.ON.standard"]
    purchases = by_key["code:purchase:hst_on:purchase.ON.standard"]
    assert sales.values == [D("1500.00"), D("195.00"), D("0"), D("0")]
    assert purchases.values == [D("1200.00"), D("156.00"), D("143.00"), D("13.00")]
    assert [r.kind for r in result.rows][:2] == ["section", "section"]
    totals = {r.key: r.values for r in result.totals}
    assert totals["total:net"][1] == D("195.00") - D("143.00")
    # totals per component = the sum of the stored lines
    with org_context(books["org"]):
        lines = TaxLine.objects.filter(date__gte=Q2[0], date__lte=Q2[1], side="sales")
        assert totals["total:sales"][1] == sum((r.tax for r in lines), D("0"))
    assert sales.drill is not None and sales.drill["report"] == "tax_detail"
    assert sales.drill["code"] == "sales.ON.standard" and sales.drill["basis"] == "accrual"
    assert result.as_dict()["totals"][2]["values"][1] == "52.00"


def test_filters_and_basis(books: dict[str, Any]) -> None:
    only_sales = run(books, side="sales")
    assert all(not r.key.startswith("code:purchase") for r in only_sales.rows)
    assert run(books, kind="qst").rows == []
    cash = run(books, basis="cash")  # no payments recorded yet: nothing recognised
    assert [r for r in cash.rows if r.kind == "row"] == []


def test_a_range_is_needed(books: dict[str, Any]) -> None:
    with pytest.raises(ReportError) as caught:
        registry.get("tax_summary").run(books["org"], {})
    assert caught.value.code == "tax.reports.range"


def test_filing_period_sets_the_range(books: dict[str, Any]) -> None:
    import datetime as dt

    from numo9.orgsettings.models import TaxRegistration
    from numo9.tax.filing_service import switch_frequency

    with org_context(books["org"]):
        reg = TaxRegistration.objects.get()
    periods, _w = switch_frequency(reg, "quarterly", dt.date(2026, 1, 1), today=dt.date(2026, 6, 1))
    q2 = next(p for p in periods if p.start == Q2[0])
    result = registry.get("tax_summary").run(books["org"], {"period": str(q2.public_id)})
    assert result.totals[0].values[1] == D("195.00")


def test_tax_period_presets(books: dict[str, Any]) -> None:
    import datetime as dt

    from freezegun import freeze_time

    from numo9.orgsettings.models import TaxRegistration
    from numo9.tax.filing_service import switch_frequency
    from numo9.tax.models import FilingPeriod

    with org_context(books["org"]):
        reg = TaxRegistration.objects.get()
    switch_frequency(reg, "quarterly", dt.date(2026, 1, 1), today=dt.date(2026, 6, 1))
    with org_context(books["org"]):
        FilingPeriod.objects.filter(start=dt.date(2026, 1, 1)).update(status="filed")
    with freeze_time("2026-05-20"):
        current = registry.get("tax_summary").run(books["org"], {"period": "current"})
        filed = registry.get("tax_summary").run(books["org"], {"period": "last_filed"})
    assert current.totals[0].values[1] == D("195.00")
    assert filed.totals[0].values[1] == D("0")
