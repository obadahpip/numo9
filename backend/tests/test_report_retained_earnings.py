"""K-02-T12: the statement of retained earnings / movements in equity."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import post_journal
from numo9.reports.engine import registry
from numo9.tenancy.context import org_context
from tests.journal_helpers import pay
from tests.ledger_helpers import account
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db
D = Decimal


def _values(result: Any) -> dict[str, list[Any]]:
    return {row.key: row.values for row in [*result.rows, *result.totals]}


def test_opening_income_dividends_closing_and_the_balance_sheet() -> None:
    books = report_books()
    org = books["org"]
    with org_context(org):
        dividends = account(org, "3400", "Dividends", subtype="dividends")
        post_journal(
            pay(books["chequing"], books["sales"], "800.00", dt.date(2025, 6, 1)), user=None
        )
        post_journal(pay(dividends, books["chequing"], "500.00", dt.date(2026, 7, 30)), user=None)
    result = registry.get("retained_earnings").run(
        org,
        {"date_from": "2026-01-01", "date_to": "2026-07-31", "compare": "prior_year"},
    )
    values = _values(result)
    assert values["opening"] == [D("800.00"), D("0.00")]
    assert values["net_income"] == [D("3650.00"), D("800.00")]
    assert values["dividends"] == [D("-500.00"), D("0.00")]
    assert "other" not in values
    assert values["closing"] == [D("3950.00"), D("800.00")]
    sheet: dict[str, Any] = {
        r.key: r.values[0]
        for r in registry.get("balance_sheet").run(org, {"as_of": "2026-07-31"}).rows
        if r.values
    }
    keys = ("retained_earnings", "current_year_earnings", "account:3400")
    assert sum((sheet[k] for k in keys), D("0")) == values["closing"][0]
