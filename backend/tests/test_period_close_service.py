"""C-06-T02, T04, T05 — close, year-end roll, reopen.

- T02: closing the GL for June sets its lock to 30 Jun (everyone and advisers only); a posting
  into it is refused naming the lock; month ends only; periods close in order.
- T04: fixture net income 25,000 → a closing journal per book to retained earnings dated the
  fiscal year end; revenue and expense accounts are zero after it; the tax book closes its own
  net income; no double closing journal; a December close is folded in.
- T05: reopen by an adviser with a reason only, the latest first (unless forced); the lock goes
  back; a year-end's closing journals are reversed (retained earnings restored); audited.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalLine
from numo9.ledger.period_close import (
    CloseRefused,
    close,
    close_year,
    lock_dates,
    net_income,
    pl_balances,
    reopen,
)
from numo9.orgsettings.locks import LockedPeriod
from numo9.tenancy.context import org_context
from tests.period_close_helpers import close_books, post

pytestmark = pytest.mark.django_db
day = dt.date
YEAR = (day(2026, 1, 1), day(2026, 12, 31))


@pytest.fixture
def books() -> dict[str, Any]:
    books = close_books()
    post(books, day(2026, 3, 10), "bank", "revenue", "40000")
    post(books, day(2026, 5, 20), "expense", "bank", "15000")
    post(books, day(2026, 6, 30), "expense", "bank", "1000", book="tax")  # tax-only difference
    return books


def re_balance(books: dict[str, Any], book: str) -> Decimal:
    with org_context(books["org"]):
        lines = JournalLine.objects.filter(account=books["re"], book__in=["both", book])
        return sum((line.credit - line.debit for line in lines), Decimal("0"))


def test_close_june_sets_the_lock(books: dict[str, Any]) -> None:
    row = close(books["org"], "gl", day(2026, 6, 30), books["owner"])
    with org_context(books["org"]):
        assert lock_dates(books["org"], "gl") == {
            "advisers_only": "2026-06-30",
            "everyone": "2026-06-30",
        }
        assert row.previous_lock == {"advisers_only": None, "everyone": None}
        assert AuditEvent.objects.filter(action="ledger.period.closed").count() == 1
    with pytest.raises(LockedPeriod) as err:
        post(books, day(2026, 6, 15), "expense", "bank", "10")
    assert "2026-06-30" in str(err.value.detail)
    post(books, day(2026, 7, 1), "expense", "bank", "10")
    for date, code in (
        (day(2026, 7, 15), "ledger.close.not_month_end"),
        (day(2026, 5, 31), "ledger.close.out_of_order"),
    ):
        with pytest.raises(CloseRefused) as refused:
            close(books["org"], "gl", date, books["owner"])
        assert refused.value.code == code
    close(books["org"], "ap", day(2026, 5, 31), books["owner"])  # another module, its own order


def test_year_end_roll_in_both_books(books: dict[str, Any]) -> None:
    org = books["org"]
    with org_context(org):
        assert net_income(org, "accounting", *YEAR) == Decimal("25000.00")
        assert net_income(org, "tax", *YEAR) == Decimal("24000.00")
    close(org, "gl", day(2026, 12, 31), books["owner"])  # December closed first: folded in
    row = close_year(org, day(2026, 12, 31), books["owner"])
    assert row.kind == "year_end" and row.accounting_entry and row.tax_entry
    assert row.previous_lock == {"advisers_only": None, "everyone": None}
    assert re_balance(books, "accounting") == Decimal("25000.00")
    assert re_balance(books, "tax") == Decimal("24000.00")
    with org_context(org):
        assert pl_balances(org, "accounting", *YEAR) == {}
        assert pl_balances(org, "tax", *YEAR) == {}
        assert row.accounting_entry.journal_type == "closing"
        assert row.accounting_entry.date == day(2026, 12, 31)
    with pytest.raises(CloseRefused) as err:
        close_year(org, day(2026, 12, 31), books["owner"])
    assert err.value.code == "ledger.close.year_closed"
    with pytest.raises(CloseRefused) as err:
        close_year(org, day(2026, 6, 30), books["owner"])
    assert err.value.code == "ledger.close.not_year_end"


def test_reopen_rules_and_year_end_reversal(books: dict[str, Any]) -> None:
    org = books["org"]
    june = close(org, "gl", day(2026, 6, 30), books["owner"])
    with pytest.raises(CloseRefused) as err:
        reopen(june, books["owner"], "Late bill")
    assert err.value.code == "ledger.close.adviser_only"
    with pytest.raises(CloseRefused) as err:
        reopen(june, books["adviser"], " ")
    assert err.value.code == "ledger.close.reason_required"
    year = close_year(org, day(2026, 12, 31), books["owner"])
    with pytest.raises(CloseRefused) as err:
        reopen(june, books["adviser"], "Late bill")
    assert err.value.code == "ledger.close.not_latest"
    reopen(year, books["adviser"], "Audit adjustment")
    assert re_balance(books, "accounting") == Decimal("0")
    assert re_balance(books, "tax") == Decimal("0")
    with org_context(org):
        assert lock_dates(org, "gl")["everyone"] == "2026-06-30"  # back to June's close
        event = AuditEvent.objects.get(action="ledger.period.reopened")
        assert event.meta["reason"] == "Audit adjustment" and len(event.meta["reversals"]) == 2
    reopen(june, books["adviser"], "Late bill")
    with org_context(org):
        assert lock_dates(org, "gl") == {"advisers_only": None, "everyone": None}
    post(books, day(2026, 6, 15), "expense", "bank", "10")


def test_forced_reopen_and_closed_year_check(books: dict[str, Any]) -> None:
    org = books["org"]
    june = close(org, "gl", day(2026, 6, 30), books["owner"])
    close(org, "gl", day(2026, 9, 30), books["owner"])
    reopen(june, books["adviser"], "Correct June", force=True)
    with org_context(org):
        assert lock_dates(org, "gl")["everyone"] == "2026-09-30"  # September stays closed
    year = close_year(org, day(2026, 12, 31), books["owner"])
    from numo9.ledger.period_close import year_end_check

    assert year_end_check(org, day(2026, 4, 1)) is not None
    assert year_end_check(org, day(2027, 1, 1)) is None
    reopen(year, books["adviser"], "x")
    assert year_end_check(org, day(2026, 4, 1)) is None
