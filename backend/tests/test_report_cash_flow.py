"""K-02-T07: the cash flow statement, indirect method."""

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


def _books() -> dict[str, Any]:
    books = report_books()
    org = books["org"]
    with org_context(org):
        books["equipment"] = account(org, "1600", "Equipment", subtype="fixed_asset")
        books["contra"] = account(
            org, "1610", "Accumulated amortization", subtype="accumulated_amortisation"
        )
        books["amort"] = account(org, "6800", "Amortization", subtype="amortisation")
        books["loan"] = account(org, "2500", "Bank loan", subtype="non_current_liability")
        books["payable"] = account(org, "2000", "Accounts payable", subtype="current_liability")
        day = dt.date(2026, 7, 15)
        post_journal(pay(books["chequing"], books["loan"], "8000.00", day), user=None)
        post_journal(pay(books["equipment"], books["chequing"], "6000.00", day), user=None)
        post_journal(pay(books["amort"], books["contra"], "500.00", day), user=None)
        post_journal(pay(books["ar"], books["sales"], "700.00", day), user=None)
        post_journal(pay(books["office"], books["payable"], "90.00", day), user=None)
    return books


def test_sections_and_net_change_equal_the_cash_movement() -> None:
    books = _books()
    result = registry.get("cash_flow").run(
        books["org"], {"date_from": "2026-05-01", "date_to": "2026-07-31"}
    )
    values = _values(result)
    # NI: 6,200 + 700 − 2,550 − 500 − 90 = 3,760
    assert values["net_income"] == [D("3760.00")]
    assert values["amortisation"] == [D("500.00")]
    assert values["account:1200"] == [D("-700.00")]
    assert values["account:2000"] == [D("90.00")]
    assert values["total:operating"] == [D("3650.00")]
    assert values["total:investing"] == [D("-6000.00")]
    assert values["total:financing"] == [D("8000.00")]
    assert values["net_change"] == [D("5650.00")]
    assert values["cash_opening"] == [D("0.00")]
    assert values["cash_closing"] == [D("5650.00")]
    assert result.alerts == []


def test_comparisons_and_balance_check() -> None:
    books = _books()
    result = registry.get("cash_flow").run(
        books["org"],
        {"date_from": "2026-07-01", "date_to": "2026-07-31", "compare": "previous", "periods": 1},
    )
    values = _values(result)
    assert values["net_change"] == [D("3200.00"), D("-2550.00")]
    assert values["cash_opening"] == [D("2450.00"), D("5000.00")]
    assert values["cash_closing"] == [D("5650.00"), D("2450.00")]
    assert result.alerts == []


def test_direct_method_equals_the_indirect_total() -> None:
    books = _books()
    org = books["org"]
    with org_context(org):
        # a transfer between two cash accounts is no flow
        post_journal(
            pay(books["petty"], books["chequing"], "100.00", dt.date(2026, 7, 20)), user=None
        )
    params = {"date_from": "2026-05-01", "date_to": "2026-07-31"}
    direct = _values(registry.get("cash_flow_direct").run(org, params))
    indirect = _values(registry.get("cash_flow").run(org, params))
    assert direct["flow:customers"] == [D("6200.00")]
    assert direct["flow:suppliers"] == [D("-2550.00")]
    assert direct["total:investing"] == [D("-6000.00")]
    assert direct["total:financing"] == [D("8000.00")]
    assert direct["net_change"] == indirect["net_change"] == [D("5650.00")]
    assert "flow:payroll" not in direct


def test_cash_definition_setting() -> None:
    from django.core.exceptions import ValidationError

    from numo9.banking.services import create_bank_account
    from numo9.orgsettings.models import validate_cash_definition
    from numo9.orgsettings.service import get_settings
    from numo9.reports.cashflow import cash_account_ids, cash_types

    books = report_books()
    org = books["org"]
    card = create_bank_account(org, type="credit_card", display_name="Visa")
    with org_context(org):
        assert cash_types(org) == ("chequing", "savings", "cash")
        post_journal(pay(books["office"], card.gl_account, "40.00", dt.date(2026, 7, 2)), user=None)
        assert card.gl_account_id not in cash_account_ids(org)
        params = {"date_from": "2026-07-01", "date_to": "2026-07-31"}
        before = _values(registry.get("cash_flow").run(org, params))
        settings = get_settings(org)
        settings.cash_definition = ["chequing", "savings", "cash", "credit_card"]
        settings.save()
        assert card.gl_account_id in cash_account_ids(org)
        after = _values(registry.get("cash_flow").run(org, params))
    assert after["net_change"][0] == before["net_change"][0] - D("40.00")
    for bad in ([], ["chequing", "chequing"], ["wallet"], "chequing"):
        with pytest.raises(ValidationError):
            validate_cash_definition(bad)
