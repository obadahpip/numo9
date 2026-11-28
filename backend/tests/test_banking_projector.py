"""F-07-T02 — minimum-running-balance projector: for an account, a date and a delta, the lowest
end-of-day balance from that date onward (windowed SQL).

Acceptance: a back-dated −100 on a day with a later trough detects the negative (the trough day
goes to −50 while the date itself and today stay positive) — unit; and for any sequence of
postings, date and delta the projector equals a day-by-day replay (Hypothesis property). Also:
future-dated entries count; draft entries and the tax book don't; a reversal nets out.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.banking.projector import minimum_running_balance
from numo9.ledger.models import Book
from numo9.ledger.services import post_journal, reverse, save_draft
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db
D = Decimal
JUNE = dt.date(2026, 6, 1)


def day(n: int) -> dt.date:
    return JUNE + dt.timedelta(days=n - 1)


def _move(accounts: dict[str, Any], amount: str, on: dt.date, book: str = Book.BOTH) -> Any:
    """Money into chequing (amount > 0) or out of it (amount < 0)."""
    value = D(amount)
    if value > 0:
        spec = pay(accounts["chequing"], accounts["sales"], str(value), on)
    else:
        spec = pay(accounts["office"], accounts["chequing"], str(-value), on)
    if book != Book.BOTH:
        spec = JournalSpec(
            date=on,
            lines=tuple(
                LineSpec(line.account, debit=line.debit, credit=line.credit, book=book)
                for line in spec.lines
            ),
        )
    return post_journal(spec, user=None)


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        _move(accounts, "500.00", day(1))
        _move(accounts, "-450.00", day(10))  # trough: 50.00
        _move(accounts, "1000.00", day(20))
    return {"org": org, "accounts": accounts}


def test_backdated_minus_100_before_a_later_trough_is_detected(books: dict[str, Any]) -> None:
    found = minimum_running_balance(
        books["accounts"]["chequing"], day(5), D("-100.00"), today=day(30)
    )
    assert found.at_date == D("400.00")
    assert (found.lowest, found.lowest_on) == (D("-50.00"), day(10))
    assert found.first_negative_on == day(10)
    assert found.at_today == D("950.00")
    assert found.goes_negative and found.shortfall == D("50.00")


def test_without_the_trough_nothing_is_negative(books: dict[str, Any]) -> None:
    found = minimum_running_balance(
        books["accounts"]["chequing"], day(12), D("-30.00"), today=day(30)
    )
    assert (found.lowest, found.lowest_on, found.first_negative_on) == (D("20.00"), day(12), None)


def test_on_the_day_and_future_dated(books: dict[str, Any]) -> None:
    chequing = books["accounts"]["chequing"]
    found = minimum_running_balance(chequing, day(1), D("-600.00"), today=day(2))
    assert (found.at_date, found.lowest, found.lowest_on) == (
        D("-100.00"),
        D("-550.00"),
        day(10),
    )
    assert found.first_negative_on == day(1)
    assert found.at_today == D("-100.00")  # today is 2 Jun: the 10 Jun spend hasn't happened
    later = minimum_running_balance(chequing, day(40), D("-10.00"), today=day(30))
    assert later.at_today == D("1050.00")  # dated after today: not in today's balance


def test_drafts_tax_book_and_reversals(books: dict[str, Any]) -> None:
    org, accounts = books["org"], books["accounts"]
    with org_context(org):
        save_draft(pay(accounts["office"], accounts["chequing"], "5000.00", day(15)))
        _move(accounts, "-5000.00", day(15), book=Book.TAX)
        reversed_out = _move(accounts, "-5000.00", day(16))
        reverse(reversed_out, user=None)
    found = minimum_running_balance(accounts["chequing"], day(11), D("0"), today=day(30))
    assert (found.lowest, found.lowest_on) == (D("50.00"), day(11))


MOVES = st.lists(
    st.tuples(
        st.integers(min_value=1, max_value=15),
        st.integers(min_value=-500, max_value=500).filter(lambda n: n != 0),
    ),
    max_size=6,
)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    moves=MOVES,
    on=st.integers(min_value=1, max_value=16),
    delta=st.integers(min_value=-800, max_value=200),
    today=st.integers(min_value=1, max_value=20),
)
def test_property_equals_a_day_by_day_replay(
    moves: list[tuple[int, int]], on: int, delta: int, today: int
) -> None:
    org = Organisation.objects.create(name="Property Co.")
    with org_context(org):
        accounts = chart(org)
        for when, amount in moves:
            _move(accounts, f"{amount}.00", day(when))
    found = minimum_running_balance(accounts["chequing"], day(on), D(delta), today=day(today))

    def balance(upto: int) -> D:
        return D(sum(a for w, a in moves if w <= upto))

    later_days = sorted({w for w, _a in moves if w > on})
    points = [(balance(on) + delta, on)] + [(balance(w) + delta, w) for w in later_days]
    lowest, lowest_on = min(points, key=lambda point: (point[0], point[1]))
    if lowest == points[0][0]:
        lowest_on = on  # the date itself wins a tie (it is the first day)
    assert (found.lowest, found.lowest_on) == (lowest, day(lowest_on))
    negative = [w for value, w in points if value < 0]
    assert found.first_negative_on == (day(min(negative)) if negative else None)
    assert found.at_today == balance(today) + (delta if today >= on else 0)
