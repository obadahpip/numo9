"""Ledger aggregation for reports (K-01-T04): period balances by account, one query.

    with snapshot():
        movements = period_movements([june, may], book="accounting")
        closing = balances_at([dt.date(2026, 6, 30)], book="accounting")

- ``period_movements(ranges, book, tracking=…, accounts=…)`` → ``{account_id: [net per range]}``:
  the net movement (debits − credits) of each account in each date range — one grouped query
  with a conditional sum per range, over the lines dated from the earliest start to the latest
  end;
- ``balances_at(dates, book, …)`` → ``{account_id: [balance at each date]}``: the cumulative
  balance on each date (everything dated on or before it) — the balance sheet's figures;
- only **posted and reversed** entries count (a reversal posts its own entry, so the two net to
  zero); drafts and entries awaiting approval never do;
- lines are read by ``(organisation, account, date, book)`` — index
  ``ledger_line_account_date_idx`` on the line's own copy of its entry's date (migration
  ``ledger.0016``) — and the book filter is ``book ∈ (both, <book>)`` (K-01-T03).

``snapshot()`` runs a report's queries in one **repeatable-read** transaction, so postings made
while a report runs (other connections) never mix into it: every query sees the same ledger.
Inside an existing transaction (a request already in one, the test suite) the isolation level
can't change any more; the block then runs in that transaction, which is already one snapshot
under PostgreSQL's default for a single statement and consistent with itself.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from django.db import connection, transaction
from django.db.models import Case, DecimalField, F, Q, Sum, When
from django.db.models.functions import Coalesce

from .parameters import DateRange, book_filter, tracking_filter

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=18, decimal_places=2)


@contextmanager
def snapshot() -> Iterator[None]:
    """Repeatable-read for the block (module docstring)."""
    if connection.in_atomic_block:
        yield
        return
    # The level must be set before the transaction's first query (the tenant context runs one
    # as the transaction opens), so it is the session's default for the block, then restored.
    with connection.cursor() as cursor:
        cursor.execute("SHOW default_transaction_isolation")
        previous = cursor.fetchone()[0]
        cursor.execute("SET default_transaction_isolation = 'repeatable read'")
    try:
        with transaction.atomic():
            yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('default_transaction_isolation', %s, false)", [previous]
            )


def _lines(
    book: str,
    tracking: dict[str, list[str]] | None,
    accounts: Iterable[int] | None,
) -> Any:
    from numo9.ledger.models import LOCKED_STATUSES, JournalLine

    rows = JournalLine.objects.filter(
        book__in=book_filter(book), entry__status__in=LOCKED_STATUSES
    ).filter(tracking_filter(tracking))
    if accounts is not None:
        rows = rows.filter(account_id__in=list(accounts))
    return rows


def _net() -> Any:
    return F("debit") - F("credit")


def period_movements(
    ranges: Sequence[DateRange],
    *,
    book: str = "accounting",
    tracking: dict[str, list[str]] | None = None,
    accounts: Iterable[int] | None = None,
) -> dict[int, list[Decimal]]:
    if not ranges:
        return {}
    first = min(r.start for r in ranges)
    last = max(r.end for r in ranges)
    sums = {
        f"p{i}": Coalesce(
            Sum(
                Case(
                    When(Q(date__gte=r.start, date__lte=r.end), then=_net()),
                    default=ZERO,
                    output_field=MONEY,
                )
            ),
            ZERO,
            output_field=MONEY,
        )
        for i, r in enumerate(ranges)
    }
    rows = (
        _lines(book, tracking, accounts)
        .filter(date__gte=first, date__lte=last)
        .values("account_id")
        .annotate(**sums)
    )
    return {row["account_id"]: [row[f"p{i}"] for i in range(len(ranges))] for row in rows}


def balances_at(
    dates: Sequence[dt.date],
    *,
    book: str = "accounting",
    tracking: dict[str, list[str]] | None = None,
    accounts: Iterable[int] | None = None,
) -> dict[int, list[Decimal]]:
    if not dates:
        return {}
    sums = {
        f"b{i}": Coalesce(
            Sum(Case(When(date__lte=day, then=_net()), default=ZERO, output_field=MONEY)),
            ZERO,
            output_field=MONEY,
        )
        for i, day in enumerate(dates)
    }
    rows = (
        _lines(book, tracking, accounts)
        .filter(date__lte=max(dates))
        .values("account_id")
        .annotate(**sums)
    )
    return {row["account_id"]: [row[f"b{i}"] for i in range(len(dates))] for row in rows}
