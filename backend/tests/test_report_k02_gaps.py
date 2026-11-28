"""K-02-T16 — the core statements' gaps (docs/xero_teardown.md §9.1–9.5; plan §gap list) on the
teardown books (REFINED: Petty Cash credited 417.22 on 3 Jun and 576.95 on 15 Jun 2026, nothing
else). The screen side is in frontend/e2e/gap-56-57-58.spec.ts and reports-balance-sheet.spec.ts.

- gap-54: one engine has the indirect *and* direct cash flow statements and a comparative
  statement of retained earnings, next to the balance sheet and the P&L; indirect = direct =
  the change in cash.
- gap-55: the statement header prints the organisation's names, never a number; an empty
  section prints 0.00 (never "–"); a financial year still running is labelled year to date.
- gap-56: Petty Cash −994.17 is a current liability "Bank overdraft — Petty Cash" 994.17 with the
  ASPE note, never a negative asset; Liabilities is printed even when empty; a contra account
  sits directly under its asset with one naming.
- gap-57: the trial balance is sorted by account code and has opening / movement / closing.
- gap-58: the journal report orders by number or date, ascending or descending.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import post_journal
from numo9.reports.engine import registry
from numo9.reports.header import header_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.assurance_helpers import refined
from tests.journal_helpers import pay
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db
D = Decimal
TODAY = dt.date(2026, 10, 26)


@pytest.fixture
def books() -> dict[str, Any]:
    return refined(registration=False, conversion=False)


def run(org: Any, report_id: str, **params: Any) -> Any:
    return registry.get(report_id).run(org, params)


def rows(result: Any) -> dict[str, Any]:
    return {row.key: row for row in [*result.rows, *result.totals]}


@pytest.mark.gap("gap-54")
def test_one_engine_indirect_and_direct_cash_flow_and_retained_earnings(
    books: dict[str, Any],
) -> None:
    org = books["org"]
    for report_id in (
        "profit_and_loss",
        "balance_sheet",
        "cash_flow",
        "cash_flow_direct",
        "retained_earnings",
    ):
        assert registry.get(report_id).category == "financial"
    period = {"date_from": "2026-01-01", "date_to": "2026-12-31"}
    indirect = rows(run(org, "cash_flow", **period))["net_change"].values
    direct = rows(run(org, "cash_flow_direct", **period))["net_change"].values
    assert indirect == direct == [D("-994.17")]
    equity = run(org, "retained_earnings", compare="prior_year", periods=1, **period)
    assert len(equity.columns) == 2  # with its comparative


@pytest.mark.gap("gap-55")
def test_header_names_zero_sections_and_year_to_date(books: dict[str, Any]) -> None:
    org = books["org"]
    report = registry.get("profit_and_loss")
    result = report.run(org, {"date_from": "2026-01-01", "date_to": "2026-12-31"})
    header = header_for(org, report, result.params, today=TODAY).as_dict()
    assert header["display_name"] == "REFINED Interiors Inc."
    assert not any(ch.isdigit() for ch in header["display_name"])
    assert header["status_label"] == "Year to date — unaudited"
    values = rows(result)
    assert values["total:revenue"].values == [D("0.00")]  # an empty section: 0.00, not "–"
    assert values["net_income"].values == [D("-994.17")]


@pytest.mark.gap("gap-56")
def test_negative_cash_is_a_liability_and_every_section_prints(books: dict[str, Any]) -> None:
    org = books["org"]
    result = run(org, "balance_sheet", as_of=TODAY.isoformat())
    values = rows(result)
    assert "account:1000" not in values  # never a negative asset
    assert values["overdraft:1000"].label == "Bank overdraft — Petty Cash"
    assert values["overdraft:1000"].values == [D("994.17")]
    assert values["note:overdraft"].label == (
        "Overdrawn bank and cash accounts are presented as current liabilities (ASPE 1510)."
    )
    for key in ("section:assets", "section:liabilities", "section:equity"):
        assert key in values
    assert values["total:assets"].values == [D("0.00")]
    assert values["total:liabilities"].values == [D("994.17")]
    assert values["current_year_earnings"].values == [D("-994.17")]
    assert values["total:liabilities_and_equity"].values == values["total:assets"].values


@pytest.mark.gap("gap-56")
def test_contra_sits_under_its_asset() -> None:
    org = Organisation.objects.create(name="Contra Ltd.")
    with org_context(org):
        cash = account(org, "1000", "Chequing", subtype="bank")
        equipment = account(org, "1500", "Equipment", subtype="fixed_asset")
        cost = account(org, "1505", "Equipment — cost", subtype="fixed_asset")
        accum = account(
            org, "1480", "Accumulated amortization — Equipment", subtype="accumulated_amortisation"
        )
        for child in (cost, accum):
            child.parent = equipment
            child.save()
        vehicles = account(org, "1490", "Vehicles", subtype="fixed_asset")
        capital = account(org, "3000", "Share capital", subtype="share_capital")
        post_journal(pay(cash, capital, "20000.00", dt.date(2026, 1, 5)), user=None)
        post_journal(pay(cost, cash, "8000.00", dt.date(2026, 1, 6)), user=None)
        post_journal(pay(vehicles, cash, "6000.00", dt.date(2026, 1, 7)), user=None)
        post_journal(pay(capital, accum, "1200.00", dt.date(2026, 6, 30)), user=None)
    result = run(org, "balance_sheet", as_of="2026-06-30")
    keys = [row.key for row in result.rows]
    start = keys.index("group:non_current_assets")
    # the contra (code 1480) right under its asset (1505), not first by code
    assert keys[start + 1 : start + 4] == ["account:1490", "account:1505", "account:1480"]
    assert rows(result)["account:1480"].values == [D("-1200.00")]
    assert rows(result)["account:1480"].label == "1480 · Accumulated amortization — Equipment"


@pytest.mark.gap("gap-57")
def test_trial_balance_sorted_by_code_with_opening_movement_closing(
    books: dict[str, Any],
) -> None:
    org = books["org"]
    result = run(org, "trial_balance", as_of="2026-10-26", date_from="2026-06-10")
    assert [c.key for c in result.columns] == [
        "opening_debit",
        "opening_credit",
        "movement_debit",
        "movement_credit",
        "closing_debit",
        "closing_credit",
    ]
    codes = [row.key.split(":")[1] for row in result.rows if row.key.startswith("account:")]
    assert codes == sorted(codes) and codes[0] == "1000"  # assets first, not expenses
    petty = rows(result)["account:1000"].values
    assert petty == [None, D("417.22"), None, D("576.95"), None, D("994.17")]


@pytest.mark.gap("gap-58")
def test_journal_report_order_and_direction(books: dict[str, Any]) -> None:
    org = books["org"]
    period = {"date_from": "2026-01-01", "date_to": "2026-12-31"}

    def order(**params: Any) -> list[str]:
        result = run(org, "journal_report", **period, **params)
        return [row.label for row in result.rows if row.key.startswith("journal:")]

    ascending = order(direction="asc")
    assert ascending[0].startswith("Journal 1 ·") and "Ontario Corporation" in ascending[0]
    assert order(direction="desc") == list(reversed(ascending))
    assert order(order="date", direction="desc")[0].startswith("Journal 2 ·")
