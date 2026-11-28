"""Balance-sheet presentation hook (F-07-T09): overdrawn asset bank and cash accounts.

An asset bank or cash account (asset, sub-type Bank — chequing, savings, petty cash, clearing,
with or without a bank profile) whose balance at a balance-sheet date is **below zero** is not an
asset that day: it is money owed (an overdraft, or cash spent that was never put in). K-02
reclassifies it to current liabilities with a note (K-02-T04); this hook tells it which accounts,
on which dates, for how much.

``overdrawn_accounts(organisation, accounts, balances, dates)`` — from the balances the balance
sheet already read (no extra query but the bank profiles' types): ``[Overdrawn(account, column,
date, balance, account_type)]``, one per account and date it is overdrawn. Registered in
``numo9.reports.statements.OVERDRAFT_HOOKS`` by the banking app. Credit cards, lines of credit
and loans are liabilities already: never listed.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from numo9.tenancy.context import org_context

from .cash_controls import UNPROFILED_TYPE
from .models import BankAccount


@dataclass(frozen=True)
class Overdrawn:
    account: Any
    column: int
    date: dt.date
    #: The (negative) balance: debits − credits.
    balance: Decimal
    account_type: str

    @property
    def owed(self) -> Decimal:
        """The amount shown as a liability (positive)."""
        return -self.balance


def is_cash_asset(account: Any) -> bool:
    return bool(account.type == "asset" and account.subtype == "bank")


def overdrawn_accounts(
    organisation: Any,
    accounts: list[Any],
    balances: dict[int, list[Decimal]],
    dates: list[dt.date],
) -> list[Overdrawn]:
    """Every asset bank/cash account below zero at each date (module docstring)."""
    candidates = [
        a for a in accounts if is_cash_asset(a) and any(v < 0 for v in balances.get(a.pk, []))
    ]
    if not candidates:
        return []
    with org_context(organisation):
        types = dict(
            BankAccount._base_manager.filter(
                organisation_id=organisation.pk, gl_account_id__in=[a.pk for a in candidates]
            ).values_list("gl_account_id", "type")
        )
    found: list[Overdrawn] = []
    for account in candidates:
        for column, (day, value) in enumerate(zip(dates, balances[account.pk], strict=False)):
            if value < 0:
                found.append(
                    Overdrawn(account, column, day, value, types.get(account.pk, UNPROFILED_TYPE))
                )
    return found
