"""K-02-T05: statement integrity — a red banner (``alerts``) and a ``reports.integrity_failed``
event when the balance sheet doesn't balance or net income ≠ Δ earnings."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from structlog.testing import capture_logs

from numo9.reports import statements
from numo9.reports.engine import registry
from numo9.reports.runner import report_body
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db


def test_balanced_books_have_no_alerts() -> None:
    books = report_books()
    org = books["org"]
    sheet = registry.get("balance_sheet").run(org, {"as_of": "2026-07-31"})
    pnl = registry.get("profit_and_loss").run(
        org, {"date_from": "2026-05-01", "date_to": "2026-07-31", "compare": "previous"}
    )
    assert sheet.alerts == [] and pnl.alerts == []
    assert sheet.as_dict()["alerts"] == []
    assert statements.integrity(org, dt.date(2026, 7, 31)) == []


def _break_balances(monkeypatch: pytest.MonkeyPatch, chequing_pk: int) -> None:
    real = statements.balance_figures

    def broken(organisation: Any, dates: list[dt.date], book: str = "accounting") -> Any:
        data = real(organisation, dates, book)
        data.balances[chequing_pk] = [v + Decimal("12.34") for v in data.balances[chequing_pk]]
        return data

    monkeypatch.setattr(statements, "balance_figures", broken)


def test_unbalanced_sheet_banner_and_event(monkeypatch: pytest.MonkeyPatch) -> None:
    books = report_books()
    org = books["org"]
    _break_balances(monkeypatch, books["chequing"].pk)
    with capture_logs() as events:
        body = report_body(
            org, registry.get("balance_sheet"), {"as_of": "2026-07-31"}, today=dt.date(2026, 8, 1)
        )
    [alert] = body["alerts"]
    assert alert["code"] == "reports.integrity.unbalanced" and alert["level"] == "error"
    assert "12.34" in alert["message"]
    failed = [e for e in events if e["event"] == "reports.integrity_failed"]
    assert failed and failed[0]["report"] == "balance_sheet"
    assert failed[0]["detail"] == {"assets": "3662.34", "liabilities_and_equity": "3650.00"}


def test_earnings_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    books = report_books()
    org = books["org"]
    monkeypatch.setattr(statements, "_earnings_change", lambda *a: Decimal("3000.00"))
    with capture_logs() as events:
        result = registry.get("profit_and_loss").run(
            org, {"date_from": "2026-05-01", "date_to": "2026-07-31"}
        )
    [alert] = result.alerts
    assert alert["code"] == "reports.integrity.earnings"
    assert alert["detail"] == {"net_income": "3650.00", "earnings_change": "3000.00"}
    assert any(e["event"] == "reports.integrity_failed" for e in events)
    codes = [a["code"] for a in statements.integrity(org, dt.date(2026, 7, 31))]
    assert codes == ["reports.integrity.earnings"]
