"""K-02-T03: the balance sheet on the report engine."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import post_journal
from numo9.reports.engine import registry
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import pay
from tests.ledger_helpers import account
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db


def _run(org: Any, **params: Any) -> Any:
    return registry.get("balance_sheet").run(org, params)


def _values(result: Any) -> dict[str, list[Any]]:
    return {row.key: row.values for row in [*result.rows, *result.totals]}


def test_sections_always_printed_for_an_empty_organisation() -> None:
    org = Organisation.objects.create(name="Empty Ltd.")
    values = _values(_run(org, as_of="2026-07-31"))
    for key in ("section:assets", "section:liabilities", "section:equity"):
        assert key in values
    assert values["total:assets"] == [Decimal("0.00")]
    assert values["total:liabilities_and_equity"] == [Decimal("0.00")]


def test_balances_and_current_year_earnings() -> None:
    books = report_books()
    values = _values(_run(books["org"], as_of="2026-07-31"))
    assert values["account:1000"] == [Decimal("3650.00")]
    assert values["total:assets"] == [Decimal("3650.00")]
    assert values["current_year_earnings"] == [Decimal("3650.00")]
    assert values["retained_earnings"] == [Decimal("0.00")]
    assert values["total:liabilities_and_equity"] == [Decimal("3650.00")]


def test_retained_earnings_from_earlier_years_and_comparisons() -> None:
    books = report_books()
    org = books["org"]
    with org_context(org):
        loan = account(org, "2500", "Bank loan", subtype="non_current_liability")
        post_journal(
            pay(books["chequing"], books["sales"], "800.00", dt.date(2025, 6, 1)), user=None
        )
        post_journal(pay(books["chequing"], loan, "10000.00", dt.date(2026, 7, 1)), user=None)
    result = _run(org, as_of="2026-07-31", compare="prior_year", periods=1)
    values = _values(result)
    assert len(result.columns) == 2
    assert values["retained_earnings"] == [Decimal("800.00"), Decimal("0.00")]
    assert values["current_year_earnings"] == [Decimal("3650.00"), Decimal("800.00")]
    assert values["account:2500"] == [Decimal("10000.00"), Decimal("0.00")]
    assert values["total:assets"] == values["total:liabilities_and_equity"]


def test_contra_account_under_its_asset_and_previous_month_ends() -> None:
    org = Organisation.objects.create(name="Contra Ltd.")
    with org_context(org):
        bank = account(org, "1000", "Chequing", subtype="bank")
        group = account(org, "1600", "Equipment", subtype="fixed_asset")
        equipment = account(org, "1601", "Equipment — cost", subtype="fixed_asset", parent=group)
        vehicles = account(org, "1700", "Vehicles", subtype="fixed_asset")
        contra = account(
            org,
            "1610",
            "Accumulated amortization",
            subtype="accumulated_amortisation",
            parent=group,
        )
        expense = account(org, "6800", "Amortization", subtype="amortisation")
        post_journal(pay(equipment, bank, "5000.00", dt.date(2026, 4, 1)), user=None)
        post_journal(pay(vehicles, bank, "9000.00", dt.date(2026, 4, 1)), user=None)
        post_journal(pay(expense, contra, "1200.00", dt.date(2026, 6, 30)), user=None)
    result = _run(org, as_of="2026-06-30", compare="previous", periods=2)
    assert [c.label for c in result.columns][1:] and len(result.columns) == 3
    keys = [row.key for row in result.rows]
    assert keys.index("account:1601") + 1 == keys.index("account:1610")
    values = _values(result)
    assert values["account:1610"][0] == Decimal("-1200.00")
    assert values["total:non_current_assets"][0] == Decimal("12800.00")
    assert values["total:assets"] == values["total:liabilities_and_equity"]
