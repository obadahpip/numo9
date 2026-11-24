"""K-01-T04 — ledger aggregation for reports: period movements and balances by account from one
grouped query on (organisation, account, date, book); posted lines only (drafts never, a
reversal nets to zero); the line carries its entry's date (filled by the database, following a
draft's date change); one repeatable-read snapshot per report run.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection

from numo9.ledger.models import JournalLine
from numo9.ledger.services import post_journal, reverse, save_draft
from numo9.reports.aggregation import balances_at, period_movements, snapshot
from numo9.reports.parameters import DateRange
from numo9.tenancy.context import org_context
from tests.journal_helpers import pay
from tests.report_helpers import report_books

D = dt.date
MAY = DateRange(D(2026, 5, 1), D(2026, 5, 31))
JUNE = DateRange(D(2026, 6, 1), D(2026, 6, 30))
JULY = DateRange(D(2026, 7, 1), D(2026, 7, 31))


@pytest.fixture
def books() -> dict[str, Any]:
    return report_books()


@pytest.mark.django_db
def test_movements_by_period(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        moves = period_movements([MAY, JUNE, JULY])
    assert moves[books["chequing"].pk] == [
        Decimal("5000.00"),
        Decimal("-2550.00"),
        Decimal("1200.00"),
    ]
    assert moves[books["sales"].pk] == [Decimal("-5000.00"), Decimal("0.00"), Decimal("-1200.00")]
    assert moves[books["rent"].pk] == [Decimal("0.00"), Decimal("2400.00"), Decimal("0.00")]
    assert sum((sum(v) for v in moves.values()), Decimal("0")) == 0


@pytest.mark.django_db
def test_balances_drafts_and_reversals(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        closing = balances_at([D(2026, 5, 31), D(2026, 6, 30)])
        assert closing[books["chequing"].pk] == [Decimal("5000.00"), Decimal("2450.00")]
        assert closing[books["rent"].pk] == [Decimal("0.00"), Decimal("2400.00")]  # no draft 999
        entry = post_journal(
            pay(books["office"], books["chequing"], "75.00", D(2026, 6, 25)), user=None
        )
        reverse(entry, date=D(2026, 6, 26), user=None)
        after = balances_at([D(2026, 6, 30)])
        assert after[books["office"].pk] == [Decimal("150.00")]  # posted and reversed: nets to 0
        only = period_movements([JUNE], accounts=[books["rent"].pk])
        assert list(only) == [books["rent"].pk]


@pytest.mark.django_db
def test_line_date_follows_its_entry(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        assert not JournalLine.objects.filter(date__isnull=True).exists()
        draft = save_draft(pay(books["rent"], books["chequing"], "10.00", D(2026, 6, 2)), user=None)
        draft.date = D(2026, 8, 1)
        draft.save()
        assert set(JournalLine.objects.filter(entry=draft).values_list("date", flat=True)) == {
            D(2026, 8, 1)
        }


@pytest.mark.django_db(transaction=True)
def test_snapshot_is_repeatable_read() -> None:
    with snapshot(), connection.cursor() as cursor:
        cursor.execute("SHOW transaction_isolation")
        assert cursor.fetchone() == ("repeatable read",)
