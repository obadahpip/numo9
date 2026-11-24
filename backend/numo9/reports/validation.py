"""Statement data validation (K-02-T15): the same figure through two reports must agree.

``validate_statements(organisation, start, end, book)`` → a list of failures (empty when the
books are consistent), each ``{"check", "column", "expected", "actual"}``:

- ``balance_sheet_balances`` — total assets = total liabilities and equity at ``end``;
- ``net_income_equals_change_in_earnings`` — the P&L's net income for ``start``–``end`` = the
  change in retained and current-year earnings on the balance sheet (dividends and entries
  posted straight to the retained earnings account — opening balances — left out);
- ``trial_balance_equals_general_ledger`` — each account's trial balance at ``end`` = its
  closing balance in the general ledger detail from ``start``;
- ``cash_flow_equals_change_in_cash`` — net change in cash (indirect and direct methods) = cash
  at ``end`` − cash the day before ``start``.

Run by ``manage.py validate_statements`` (every organisation, or ``--org``) and the
``data_validation`` tests on the fixture organisations.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from .engine import registry

ZERO = Decimal("0.00")


def _rows(result: Any) -> dict[str, Any]:
    return {row.key: row for row in [*result.rows, *result.totals]}


def _fail(check: str, column: str, expected: Decimal, actual: Decimal) -> dict[str, str]:
    return {
        "check": check,
        "column": column,
        "expected": f"{expected:.2f}",
        "actual": f"{actual:.2f}",
    }


def validate_statements(
    organisation: Any, start: dt.date, end: dt.date, book: str = "accounting"
) -> list[dict[str, str]]:
    from numo9.tenancy.context import org_context

    from .cashflow import cash_balances
    from .statements import balance_figures

    period = {"date_from": start, "date_to": end, "book": book}
    failures: list[dict[str, str]] = []
    sheet = _rows(registry.get("balance_sheet").run(organisation, {"as_of": end, "book": book}))
    assets = sheet["total:assets"].values[0] or ZERO
    other = sheet["total:liabilities_and_equity"].values[0] or ZERO
    if assets != other:
        failures.append(_fail("balance_sheet_balances", end.isoformat(), assets, other))

    pnl = _rows(registry.get("profit_and_loss").run(organisation, period))
    income = pnl["net_income"].values[0] or ZERO
    with org_context(organisation):
        data = balance_figures(organisation, [start - dt.timedelta(days=1), end], book)
    change = (data.retained[1] + data.current_year[1]) - (data.retained[0] + data.current_year[0])
    if income != change:
        failures.append(_fail("net_income_equals_change_in_earnings", "", change, income))

    tb = registry.get("trial_balance").run(organisation, {"as_of": end, "book": book})
    balances = {
        row.key.split(":", 1)[1]: (row.values[0] or ZERO) - (row.values[1] or ZERO)
        for row in tb.rows
    }
    gl = registry.get("general_ledger").run(organisation, period)
    closing = {
        row.key.split(":", 1)[1]: row.values[2] or ZERO
        for row in gl.rows
        if row.key.startswith("closing:")
    }
    for code in sorted(set(balances) | set(closing)):
        a, b = balances.get(code, ZERO), closing.get(code, ZERO)
        if a != b:
            failures.append(_fail("trial_balance_equals_general_ledger", code, a, b))

    with org_context(organisation):
        before, after = cash_balances(organisation, [start - dt.timedelta(days=1), end], book)
    for report in ("cash_flow", "cash_flow_direct"):
        flow = _rows(registry.get(report).run(organisation, period))["net_change"].values[0]
        if (flow or ZERO) != after - before:
            failures.append(
                _fail("cash_flow_equals_change_in_cash", report, after - before, flow or ZERO)
            )
    return failures
