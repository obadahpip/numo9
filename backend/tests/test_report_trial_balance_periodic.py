"""K-02-T06: the trial balance with opening, movement and closing debit and credit columns."""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.reports.engine import registry
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db
D = Decimal


def test_opening_movement_closing() -> None:
    books = report_books()
    result = registry.get("trial_balance").run(
        books["org"], {"date_from": "2026-06-01", "as_of": "2026-07-31"}
    )
    assert [c.key for c in result.columns] == [
        "opening_debit",
        "opening_credit",
        "movement_debit",
        "movement_credit",
        "closing_debit",
        "closing_credit",
    ]
    values = {row.key: row.values for row in result.rows}
    assert list(values) == ["account:1000", "account:4000", "account:5400", "account:6100"]
    assert values["account:1000"] == [
        D("5000.00"),
        None,
        D("1200.00"),
        D("2550.00"),
        D("3650.00"),
        None,
    ]
    assert values["account:4000"] == [None, D("5000.00"), None, D("1200.00"), None, D("6200.00")]
    assert values["account:6100"] == [None, None, D("150.00"), None, D("150.00"), None]
    [total] = result.totals
    t = total.values
    assert t[0] == t[1] == D("5000.00")
    assert t[2] == t[3] == D("3750.00")
    assert t[4] == t[5] == D("6200.00")


def test_without_a_start_date_it_stays_the_balance_list() -> None:
    books = report_books()
    result = registry.get("trial_balance").run(books["org"], {"as_of": "2026-07-31"})
    assert [c.key for c in result.columns] == ["debit", "credit"]
