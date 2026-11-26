"""NEG_CASH (K-09-T06): a bank or cash account whose balance went below zero.

The running end-of-day balance of every bank/cash account (asset, sub-type Bank) over its posted
lines in the accounting book — the cash guard's ledger view (C-03-T07). F-07's running-minimum
projector is not on main yet: this is the same computation over the posted lines (its lowest
point, the day it was reached, the first negative day and today's balance), to be swapped for
the projector when it lands.

**Fix** (``fix_source``): a draft journal dated the first negative day for the shortfall
(−lowest) — **Dr the account / Cr a funded bank** (another bank account whose balance today
covers it: a transfer) or, when none can (or ``shareholder_loan``), **Dr the account / Cr
Shareholder Loan** (the account coded ``shareholder_loan_account``, else the first liability
named "Shareholder loan"). Teardown: Dr 1000 Petty Cash 994.17 / Cr 2900 Shareholder Loan.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.ledger.cash_guard import format_day, format_signed
from numo9.ledger.models import Account, AccountType

from ..models import ExceptionFinding, Severity
from .base import Context, FixProposal, Hit, Param, Rule, fix_line, register
from .common import ACCOUNT, ZERO, cash_accounts, daily_movements


def history(account: Account, today: dt.date) -> dict[str, Any] | None:
    """Lowest end-of-day balance, its day, the first negative day and today's balance."""
    running = ZERO
    lowest: Decimal | None = None
    lowest_on: dt.date | None = None
    first_negative: dt.date | None = None
    today_balance = ZERO
    for day, movement in daily_movements(account):
        running += movement
        if day <= today:
            today_balance = running
        if lowest is None or running < lowest:
            lowest, lowest_on = running, day
        if running < 0 and first_negative is None:
            first_negative = day
    if lowest is None or lowest_on is None:
        return None
    return {
        "lowest": lowest,
        "lowest_on": lowest_on,
        "first_negative_on": first_negative,
        "today_balance": today_balance,
    }


def balance_today(account: Account, today: dt.date) -> Decimal:
    return sum((m for _day, m in daily_movements(account, today)), ZERO)


@register
class NegativeCash(Rule):
    code = "NEG_CASH"
    name = gettext_lazy("Negative cash or bank balance")
    description = gettext_lazy(
        "A bank or cash account's balance went below zero: money was spent that was never in it."
    )
    explanation = gettext_lazy(
        "%(account)s went below zero: %(lowest)s on %(lowest_on)s (today %(today_balance)s). "
        "Cash on hand can't be negative: money was spent from it that was never put in."
    )
    default_severity = Severity.CRITICAL
    incremental = True
    has_fix = True
    money_keys = ("lowest", "today_balance", "shortfall")
    date_keys = ("lowest_on", "first_negative_on")
    params = {
        "fix_source": Param(
            "choice",
            "auto",
            gettext_lazy("Fix source"),
            choices=("auto", "transfer", "shareholder_loan"),
        ),
        "shareholder_loan_account": Param(
            "str", "2900", gettext_lazy("Shareholder loan account code")
        ),
    }

    def evaluate(self, ctx: Context) -> Iterable[Hit]:
        accounts = cash_accounts()
        if ctx.scope is not None:
            accounts = accounts.filter(public_id__in=sorted(ctx.scope.accounts))
        for account in accounts:
            found = history(account, ctx.today)
            if found is None or found["lowest"] >= 0:
                continue
            yield Hit(
                ACCOUNT,
                str(account.public_id),
                str(account),
                found["lowest"],
                {
                    "account": account.name,
                    "code": account.code,
                    "lowest": f"{found['lowest']:.2f}",
                    "lowest_on": found["lowest_on"].isoformat(),
                    "first_negative_on": found["first_negative_on"].isoformat(),
                    "today_balance": f"{found['today_balance']:.2f}",
                    "shortfall": f"{-found['lowest']:.2f}",
                },
            )

    # ---- fix ------------------------------------------------------------------------------

    def _loan_account(self, ctx: Context) -> Account | None:
        code = ctx.params["shareholder_loan_account"]
        found: Account | None = Account.objects.filter(code=code).first() if code else None
        if found is None:
            found = (
                Account.objects.filter(type=AccountType.LIABILITY)
                .filter(
                    Q(name_i18n__icontains="shareholder loan")
                    | Q(name_i18n__icontains="shareholder's loan")
                )
                .order_by("code")
                .first()
            )
        return found

    def _funded_bank(self, account: Account, shortfall: Decimal, ctx: Context) -> Any:
        best: tuple[Decimal, Account] | None = None
        for other in cash_accounts().exclude(pk=account.pk):
            balance = balance_today(other, ctx.today)
            if balance >= shortfall and (best is None or balance > best[0]):
                best = (balance, other)
        return best

    def propose_fix(self, finding: ExceptionFinding, ctx: Context) -> FixProposal | None:
        account = Account.objects.filter(public_id=finding.subject_id).first()
        if account is None:
            return None
        found = history(account, ctx.today)
        if found is None or found["lowest"] >= 0 or found["first_negative_on"] is None:
            return None
        shortfall = -found["lowest"]
        date = found["first_negative_on"]
        source = ctx.params["fix_source"]
        bank = self._funded_bank(account, shortfall, ctx)
        loan = self._loan_account(ctx)
        shown = {
            "account": account.name,
            "lowest": format_signed(found["lowest"]),
            "lowest_on": format_day(found["lowest_on"]),
            "shortfall": format_signed(shortfall),
            "date": format_day(date),
        }
        transfer: FixProposal | None = None
        owner: FixProposal | None = None
        if bank is not None:
            balance, other = bank
            transfer = FixProposal(
                "journal",
                _(
                    "%(account)s fell to %(lowest)s on %(lowest_on)s. %(bank)s has "
                    "%(balance)s today: transferring %(shortfall)s on %(date)s brings "
                    "%(account)s back to zero at its lowest point."
                )
                % {**shown, "bank": other.name, "balance": format_signed(balance)},
                date=date,
                narration=_("Transfer to %(account)s") % {"account": account.name},
                lines=[
                    fix_line(account, debit=shortfall),
                    fix_line(other, credit=shortfall),
                ],
            )
        if loan is not None:
            why = (
                _(
                    "%(account)s fell to %(lowest)s on %(lowest_on)s and no other bank "
                    "account can cover it: the owner most likely paid personally, so the "
                    "entry credits %(loan)s for %(shortfall)s on %(date)s."
                )
                if bank is None
                else _(
                    "If the owner paid personally, the entry credits %(loan)s for "
                    "%(shortfall)s on %(date)s instead of a transfer."
                )
            )
            owner = FixProposal(
                "journal",
                why % {**shown, "loan": loan.name},
                date=date,
                narration=_("Owner funded %(account)s") % {"account": account.name},
                lines=[fix_line(account, debit=shortfall), fix_line(loan, credit=shortfall)],
            )
        ordered = [owner, transfer] if source == "shareholder_loan" else [transfer, owner]
        options = [option for option in ordered if option is not None]
        if not options:
            return None
        primary, *others = options
        primary.alternatives = [o.as_dict() for o in others]
        return primary
