"""K-02-T10: general ledger detail and account transactions with running balances."""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.reports.engine import ReportError, registry
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db
D = Decimal


def test_account_transactions_running_balance() -> None:
    books = report_books()
    result = registry.get("account_transactions").run(
        books["org"], {"account": "1000", "date_from": "2026-06-01", "date_to": "2026-07-31"}
    )
    rows = result.rows
    assert rows[0].key == "section:1000"
    assert rows[1].values == [None, None, D("5000.00")]
    lines = [r for r in rows if r.key.startswith("line:")]
    assert [r.values for r in lines] == [
        [None, D("2400.00"), D("2600.00")],
        [None, D("150.00"), D("2450.00")],
        [D("1200.00"), None, D("3650.00")],
    ]
    assert "20 Jun 2026" in lines[1].label or "2026" in lines[1].label
    closing = rows[-1]
    assert closing.key == "closing:1000" and closing.values == [
        D("1200.00"),
        D("2550.00"),
        D("3650.00"),
    ]


def test_general_ledger_closing_equals_the_trial_balance() -> None:
    books = report_books()
    org = books["org"]
    gl = registry.get("general_ledger").run(
        org, {"date_from": "2026-06-01", "date_to": "2026-07-31"}
    )
    closing = {r.key.split(":")[1]: r.values[2] for r in gl.rows if r.key.startswith("closing:")}
    tb = registry.get("trial_balance").run(org, {"as_of": "2026-07-31"})
    balances = {
        r.key.split(":")[1]: (r.values[0] or D("0")) - (r.values[1] or D("0")) for r in tb.rows
    }
    assert closing == balances
    assert list(closing) == ["1000", "4000", "5400", "6100"]


def test_unknown_account() -> None:
    books = report_books()
    with pytest.raises(ReportError):
        registry.get("account_transactions").run(
            books["org"], {"account": "9999", "date_from": "2026-06-01", "date_to": "2026-07-31"}
        )
