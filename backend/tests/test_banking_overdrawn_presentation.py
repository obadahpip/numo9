"""F-07-T09 — balance-sheet presentation hook: overdrawn asset bank and cash accounts are flagged
for K-02's reclassification.

Acceptance: K-02 receives the overdrawn list — running the balance sheet calls the hook and its
figures (``BalanceData.overdrawn``) name Petty Cash at −994.17 on the date (teardown: 417.22 on
3 Jun and 576.95 on 15 Jun credited to an empty float), per comparison column. Also: a funded
chequing account and a credit card (a liability) are never listed; an account overdrawn on one
date only is listed for that date; the bank profile's type comes along (Cash), a ledger bank
account without a profile counts as Cash.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.banking.presentation import overdrawn_accounts
from numo9.banking.services import attach_bank_account, create_bank_account
from numo9.ledger.services import post_journal
from numo9.reports import statements
from numo9.reports.engine import registry
from numo9.reports.statements import balance_figures
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        attach_bank_account(accounts["petty"], type="cash", display_name="Petty Cash")
        visa = create_bank_account(org, type="credit_card", display_name="TD Visa")
        accounts["visa"] = visa.gl_account
        post_journal(pay(accounts["chequing"], accounts["sales"], "5000.00", dt.date(2026, 5, 1)))
        post_journal(pay(accounts["office"], accounts["petty"], "417.22", dt.date(2026, 6, 3)))
        post_journal(pay(accounts["office"], accounts["petty"], "576.95", dt.date(2026, 6, 15)))
        post_journal(pay(accounts["office"], accounts["visa"], "250.00", dt.date(2026, 6, 20)))
    return {"org": org, "accounts": accounts}


def test_balance_sheet_receives_the_overdrawn_list(
    books: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[dt.date]] = []

    def spy(organisation: Any, accounts: Any, balances: Any, dates: Any) -> Any:
        calls.append(list(dates))
        return overdrawn_accounts(organisation, accounts, balances, dates)

    monkeypatch.setattr(statements, "OVERDRAFT_HOOKS", [spy])
    org = books["org"]
    with org_context(org):
        registry.get("balance_sheet").run(org, {"as_of": "2026-06-30"})
    assert calls == [[dt.date(2026, 6, 30)]]


def test_the_list_names_petty_cash_per_date(books: dict[str, Any]) -> None:
    org = books["org"]
    dates = [dt.date(2026, 6, 30), dt.date(2026, 6, 10), dt.date(2026, 5, 31)]
    with org_context(org):
        data = balance_figures(org, dates)
    found = [(o.account.code, o.column, o.date, o.balance, o.account_type) for o in data.overdrawn]
    assert found == [
        ("1010", 0, dt.date(2026, 6, 30), D("-994.17"), "cash"),
        ("1010", 1, dt.date(2026, 6, 10), D("-417.22"), "cash"),
    ]
    assert data.overdrawn[0].owed == D("994.17")


def test_unprofiled_bank_account_counts_as_cash(books: dict[str, Any]) -> None:
    org = books["org"]
    accounts = books["accounts"]
    with org_context(org):
        post_journal(pay(accounts["office"], accounts["chequing"], "6000.00", dt.date(2026, 6, 25)))
        data = balance_figures(org, [dt.date(2026, 6, 30)])
    shown = {o.account.code: (o.balance, o.account_type) for o in data.overdrawn}
    assert shown == {"1000": (D("-1000.00"), "cash"), "1010": (D("-994.17"), "cash")}
