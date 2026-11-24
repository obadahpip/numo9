"""K-01-T04 — performance: a 12-month aggregation (period movements per month, plus closing
balances) of a 100,000-line organisation in under one second, while another organisation's
20,000 lines are never read. Same fixture as the trial balance test (C-02-T17): entries inserted
as drafts, their lines (dated by the database from the entry), then posted.
"""

from __future__ import annotations

import datetime as dt
import time
from decimal import Decimal

import pytest
from django.db import connection

from numo9.reports.aggregation import balances_at, period_movements, snapshot
from numo9.reports.parameters import DateRange
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.test_ledger_trial_balance_performance import (
    ENTRIES,
    LINES_PER_ENTRY,
    OTHER_ENTRIES,
    _chart,
    _fill,
)

pytestmark = pytest.mark.django_db
BUDGET_SECONDS = 1.0
MONTHS = [
    DateRange(
        dt.date(2026, m, 1),
        (dt.date(2026, m + 1, 1) if m < 12 else dt.date(2027, 1, 1)) - dt.timedelta(days=1),
    )
    for m in range(1, 13)
]


@pytest.fixture
def big() -> Organisation:
    org = Organisation.objects.create(name="Big Ltd.")
    other = Organisation.objects.create(name="Other Ltd.")
    with org_context(org):
        _fill(org, ENTRIES, _chart(org, 40))
    with org_context(other):
        _fill(other, OTHER_ENTRIES, _chart(other, 10))
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE ledger_journalentry")
        cursor.execute("ANALYZE ledger_journalline")
    return org


def test_twelve_month_aggregation_of_100k_lines_under_one_second(big: Organisation) -> None:
    with org_context(big):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM ledger_journalline WHERE organisation_id = %s"
                " AND date IS NOT NULL",
                [big.pk],
            )
            assert cursor.fetchone() == (ENTRIES * LINES_PER_ENTRY,)
        started = time.perf_counter()
        with snapshot():
            moves = period_movements(MONTHS)
            closing = balances_at([dt.date(2026, 12, 31)])
        elapsed = time.perf_counter() - started
        print(f"12-month aggregation of {ENTRIES * LINES_PER_ENTRY:,} lines: {elapsed:.3f} s")
        assert elapsed < BUDGET_SECONDS, f"took {elapsed:.3f} s"
        assert 0 < len(moves) <= 40 and all(len(v) == 12 for v in moves.values())
        # Every entry balances in the accounting book: the months and the year net to zero.
        for month in range(12):
            assert sum((v[month] for v in moves.values()), Decimal("0")) == 0
        assert sum((v[0] for v in closing.values()), Decimal("0")) == 0
