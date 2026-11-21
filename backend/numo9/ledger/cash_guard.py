"""Cash-balance guard (C-03-T07): would this journal drive a bank or cash account below zero?

``projections(checked, organisation, today=…)`` — for each bank/cash account (asset accounts of
sub-type Bank: chequing, savings, petty cash…) the journal takes money out of, the account's
ledger balance **including the journal**:

- ``at_date`` — at the end of the journal's date;
- ``at_today`` — today (or at the journal's date when it is in the future);
- ``lowest`` / ``lowest_on`` — the lowest end-of-day balance from the journal's date on, every
  posted entry dated later (future-dated ones too) counted: a backdated journal can push a past
  day below zero while today's balance is positive — that day is what matters.

Ledger balance = posted lines (posted and reversed entries; a reversal is an entry of its own) in
the accounting view (lines in both books or the accounting book), debits minus credits. A
projection ``goes_negative`` when its lowest point is below zero; ``message()`` names it the way
the journal screen shows it: "Petty Cash would be −994.17 on 15 Jun 2026".

What happens then — blocked for people who aren't advisers, a warning with a stored reason for
advisers — is the posting rule of C-03-T08.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import dateformat, timezone
from django.utils.translation import gettext as _

from .models import (
    LOCKED_STATUSES,
    Account,
    AccountSubtype,
    AccountType,
    Book,
    JournalLine,
)
from .validation import ValidatedJournal, format_amount

ZERO = Decimal("0.00")
ACCOUNTING_VIEW = (Book.BOTH, Book.ACCOUNTING)


def is_cash(account: Account) -> bool:
    return account.type == AccountType.ASSET and account.subtype == AccountSubtype.BANK


def format_signed(amount: Decimal) -> str:
    """``−994.17`` (a real minus sign, as on screen)."""
    text = format_amount(amount)
    return "−" + text[1:] if text.startswith("-") else text


def format_day(day: dt.date) -> str:
    """``15 Jun 2026`` (month in the active language)."""
    return dateformat.format(day, "j M Y")


@dataclass(frozen=True)
class Projection:
    account: Account
    change: Decimal
    at_date: Decimal
    on: dt.date
    at_today: Decimal
    today: dt.date
    lowest: Decimal
    lowest_on: dt.date

    @property
    def goes_negative(self) -> bool:
        return self.lowest < 0

    def message(self) -> str:
        return _("%(account)s would be %(amount)s on %(date)s") % {
            "account": self.account.name,
            "amount": format_signed(self.lowest),
            "date": format_day(self.lowest_on),
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "account": {"id": str(self.account.public_id), "label": str(self.account)},
            "change": f"{self.change:.2f}",
            "at_date": f"{self.at_date:.2f}",
            "date": self.on.isoformat(),
            "at_today": f"{self.at_today:.2f}",
            "today": self.today.isoformat(),
            "lowest": f"{self.lowest:.2f}",
            "lowest_on": self.lowest_on.isoformat(),
            "message": self.message(),
        }


def _posted(account: Account) -> Any:
    return JournalLine.objects.filter(
        account=account, book__in=ACCOUNTING_VIEW, entry__status__in=sorted(LOCKED_STATUSES)
    )


def _net(rows: Any) -> Decimal:
    totals = rows.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return (totals["debit"] or ZERO) - (totals["credit"] or ZERO)


def balance(account: Account, as_of: dt.date) -> Decimal:
    """The account's ledger balance at the end of ``as_of`` (debits − credits)."""
    return _net(_posted(account).filter(entry__date__lte=as_of))


def _changes(checked: ValidatedJournal) -> dict[int, tuple[Account, Decimal]]:
    changes: dict[int, tuple[Account, Decimal]] = {}
    for line in checked.lines:
        if line.book not in ACCOUNTING_VIEW or not is_cash(line.account):
            continue
        account, change = changes.get(line.account.pk, (line.account, ZERO))
        changes[line.account.pk] = (account, change + line.debit - line.credit)
    return changes


def projections(
    checked: ValidatedJournal, organisation: Any = None, *, today: dt.date | None = None
) -> list[Projection]:
    """The cash accounts the journal takes money out of, with their projected balances."""
    today = today or timezone.localdate()
    date = checked.spec.date
    result: list[Projection] = []
    for account, change in _changes(checked).values():
        if change >= 0:
            continue  # money in can't drive an account below zero
        at_date = balance(account, date) + change
        when = max(today, date)
        at_today = (balance(account, when) if when != date else at_date - change) + change
        lowest, lowest_on = at_date, date
        running = at_date
        later = (
            _posted(account)
            .filter(entry__date__gt=date)
            .values("entry__date")
            .order_by("entry__date")
            .annotate(debit=Sum("debit"), credit=Sum("credit"))
        )
        for day in later:
            running += (day["debit"] or ZERO) - (day["credit"] or ZERO)
            if running < lowest:
                lowest, lowest_on = running, day["entry__date"]
        result.append(
            Projection(account, change, at_date, date, at_today, today, lowest, lowest_on)
        )
    return result


def shortfalls(
    checked: ValidatedJournal, organisation: Any = None, *, today: dt.date | None = None
) -> list[Projection]:
    """The projections that go below zero."""
    return [p for p in projections(checked, organisation, today=today) if p.goes_negative]
