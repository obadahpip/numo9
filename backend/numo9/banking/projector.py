"""Minimum-running-balance projector (F-07-T02).

``minimum_running_balance(account, date, delta, today=…)`` — given a ledger account (a bank or
cash account), a date and a change (``delta``: debits − credits a posting would add on that day),
the account's end-of-day balances **from that date onward** with the change included, and their
lowest point:

- ``at_date`` — the balance at the end of ``date`` with the change;
- ``lowest`` / ``lowest_on`` — the lowest end-of-day balance on ``date`` or any later day with a
  posting (future-dated entries count): a back-dated spend checks every later day, so a day that
  is already a trough goes negative even when today's balance stays positive;
- ``first_negative_on`` — the first such day below zero (``None`` when none);
- ``at_today`` — today's balance (with the change once its date has come); the worst case of
  the date and today is ``lowest``, which covers both.

One SQL statement: the posted lines (posted and reversed entries — a reversal is an entry of its
own) in the accounting view (books ``both`` and ``accounting``), summed per day, then a window
``SUM() OVER (ORDER BY day)`` for the running balance; the troughs are read from that window. The
ledger view is the cash guard's (C-03-T07) and the bank balance's (F-01-T06).

Performance: one index range scan over the account's lines (``account``, ``entry``) — the plan's
mitigation for very large accounts (a daily balance snapshot) can replace the ``days`` CTE
without changing this interface.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import connection
from django.utils import timezone

from numo9.ledger.models import LOCKED_STATUSES, Account, Book, JournalEntry, JournalLine
from numo9.tenancy.context import org_context

ZERO = Decimal("0.00")
ACCOUNTING_VIEW = (Book.BOTH, Book.ACCOUNTING)


@dataclass(frozen=True)
class RunningMinimum:
    account: Account
    date: dt.date
    delta: Decimal
    at_date: Decimal
    lowest: Decimal
    lowest_on: dt.date
    first_negative_on: dt.date | None
    at_today: Decimal
    today: dt.date

    @property
    def goes_negative(self) -> bool:
        return self.lowest < 0

    @property
    def shortfall(self) -> Decimal:
        """How much would have to come in to keep the lowest point at zero."""
        return -self.lowest if self.lowest < 0 else ZERO


def _sql() -> str:
    lines = JournalLine._meta.db_table
    entries = JournalEntry._meta.db_table
    return f"""
        WITH days AS (
            SELECT e.date AS day, SUM(l.debit - l.credit) AS net
              FROM {lines} l
              JOIN {entries} e ON e.id = l.entry_id
             WHERE l.organisation_id = %(org)s
               AND l.account_id = %(account)s
               AND l.book = ANY(%(books)s)
               AND e.status = ANY(%(statuses)s)
             GROUP BY e.date
        ),
        running AS (
            SELECT day, SUM(net) OVER (ORDER BY day ROWS UNBOUNDED PRECEDING) AS balance
              FROM days
        ),
        trough AS (
            SELECT day, balance FROM running
             WHERE day > %(date)s
             ORDER BY balance ASC, day ASC
             LIMIT 1
        )
        SELECT
            COALESCE((SELECT balance FROM running WHERE day <= %(date)s
                       ORDER BY day DESC LIMIT 1), 0) AS before,
            (SELECT day FROM trough) AS trough_on,
            (SELECT balance FROM trough) AS trough,
            (SELECT MIN(day) FROM running
              WHERE day > %(date)s AND balance + %(delta)s < 0) AS negative_on,
            COALESCE((SELECT balance FROM running WHERE day <= %(today)s
                       ORDER BY day DESC LIMIT 1), 0) AS at_today
    """  # noqa: S608 — table names from the models; every value is a parameter


def minimum_running_balance(
    account: Account, date: dt.date, delta: Any = ZERO, *, today: dt.date | None = None
) -> RunningMinimum:
    """The account's lowest end-of-day balance from ``date`` on, ``delta`` included."""
    change = Decimal(str(delta)).quantize(Decimal("0.01"))
    today = today or timezone.localdate()
    with org_context(account.organisation), connection.cursor() as cursor:
        cursor.execute(
            _sql(),
            {
                "org": account.organisation_id,
                "account": account.pk,
                "books": list(ACCOUNTING_VIEW),
                "statuses": sorted(LOCKED_STATUSES),
                "date": date,
                "delta": change,
                "today": today,
            },
        )
        before, trough_on, trough, negative_on, at_today = cursor.fetchone()
    at_date = Decimal(before) + change
    lowest, lowest_on = at_date, date
    if trough is not None and Decimal(trough) + change < lowest:
        lowest, lowest_on = Decimal(trough) + change, trough_on
    first_negative = date if at_date < 0 else negative_on
    today_balance = Decimal(at_today) + (change if today >= date else ZERO)
    return RunningMinimum(
        account=account,
        date=date,
        delta=change,
        at_date=at_date,
        lowest=lowest,
        lowest_on=lowest_on,
        first_negative_on=first_negative,
        at_today=today_balance,
        today=today,
    )
