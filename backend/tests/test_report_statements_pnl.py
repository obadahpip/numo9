"""K-02-T02: the profit and loss statement on the report engine."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.reports.engine import registry
from numo9.tenancy.context import org_context
from tests.ledger_helpers import account
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db


def _run(org: Any, **params: Any) -> Any:
    return registry.get("profit_and_loss").run(org, params)


def _values(result: Any) -> dict[str, list[Any]]:
    return {row.key: row.values for row in [*result.rows, *result.totals]}


def test_sections_and_net_income() -> None:
    books = report_books()
    result = _run(books["org"], date_from="2026-05-01", date_to="2026-07-31")
    values = _values(result)
    assert values["account:4000"] == [Decimal("6200.00")]
    assert values["total:revenue"] == [Decimal("6200.00")]
    assert values["gross_profit"] == [Decimal("6200.00")]
    assert values["total:operating_expenses"] == [Decimal("2550.00")]
    assert values["operating_income"] == [Decimal("3650.00")]
    assert values["net_income"] == [Decimal("3650.00")]
    keys = [row.key for row in result.rows]
    assert (
        keys.index("section:revenue")
        < keys.index("gross_profit")
        < keys.index("section:operating_expenses")
        < keys.index("operating_income")
        < keys.index("income_before_tax")
    )


def test_cost_of_sales_other_items_and_taxes() -> None:
    books = report_books()
    org = books["org"]
    import datetime as dt

    from numo9.ledger.services import post_journal
    from tests.journal_helpers import pay

    with org_context(org):
        cogs = account(org, "5000", "Purchases", subtype="cost_of_sales")
        interest = account(org, "4500", "Interest income", subtype="other_income")
        loss = account(org, "6900", "Loss on disposal", subtype="other_expense")
        tax = account(org, "9000", "Income tax expense", subtype="income_tax")
        day = dt.date(2026, 7, 10)
        post_journal(pay(cogs, books["chequing"], "1000.00", day), user=None)
        post_journal(pay(books["chequing"], interest, "50.00", day), user=None)
        post_journal(pay(loss, books["chequing"], "100.00", day), user=None)
        post_journal(pay(tax, books["chequing"], "300.00", day), user=None)
    values = _values(_run(org, date_from="2026-05-01", date_to="2026-07-31"))
    assert values["gross_profit"] == [Decimal("5200.00")]
    assert values["operating_income"] == [Decimal("2650.00")]
    assert values["income_before_tax"] == [Decimal("2600.00")]
    assert values["net_income"] == [Decimal("2300.00")]


def test_comparisons_and_drill_columns() -> None:
    books = report_books()
    result = _run(
        books["org"], date_from="2026-07-01", date_to="2026-07-31", compare="previous", periods=2
    )
    assert len(result.columns) == 3
    values = _values(result)
    assert values["net_income"] == [Decimal("1200.00"), Decimal("-2550.00"), Decimal("5000.00")]
    rent = next(row for row in result.rows if row.key == "account:5400")
    assert [c["from"].isoformat() for c in rent.drill["columns"]] == [
        "2026-07-01",
        "2026-06-01",
        "2026-05-01",
    ]


def test_empty_organisation_prints_sections() -> None:
    from numo9.tenancy.models import Organisation

    org = Organisation.objects.create(name="Empty Ltd.")
    result = _run(org, date_from="2026-01-01", date_to="2026-12-31")
    values = _values(result)
    assert values["net_income"] == [Decimal("0.00")]
    assert "section:revenue" in values
