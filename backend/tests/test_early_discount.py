"""E-07-T02 — early-payment discount calculator: the window (inclusive, in the organisation's time
zone — 23:59 on the last day is inside, midnight after is not), the base (total or before tax)
and partial payments pro-rata; Hypothesis: the discounts of a document never exceed the full
discount and add up to it when the document is paid inside the window."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from numo9.documents.early_discount import (
    PRE_TAX,
    TOTAL,
    EarlyDiscount,
    for_payment,
    payment_day,
    window_until,
)
from numo9.tenancy.models import Organisation

D, day = Decimal, dt.date
DOC_DATE = day(2026, 11, 1)
UNTIL = day(2026, 11, 11)


def terms(base: str = TOTAL, pct: str = "2") -> EarlyDiscount:
    return EarlyDiscount(D(pct), UNTIL, D("1130.00"), D("1000.00"), base)


def test_window() -> None:
    assert window_until(DOC_DATE, 10) == UNTIL
    assert window_until(DOC_DATE, 10, due=day(2026, 11, 5)) == day(2026, 11, 5)
    assert window_until(DOC_DATE, 0) is None
    t = terms()
    assert t.available_on(UNTIL) and not t.available_on(day(2026, 11, 12))
    assert not t.available_on(day(2026, 10, 31), DOC_DATE)
    assert (t.days_left(day(2026, 11, 9)), t.days_left(UNTIL), t.days_left(day(2026, 11, 12))) == (
        2,
        0,
        None,
    )


@pytest.mark.parametrize(
    ("base", "full", "pays"),
    [(TOTAL, "22.60", "1107.40"), (PRE_TAX, "20.00", "1110.00")],
)
def test_full_payment_in_the_window(base: str, full: str, pays: str) -> None:
    t = terms(base)
    assert t.full_discount == D(full) and t.discounted_total == D(pays)
    paid = for_payment(t, D(pays), UNTIL, open_balance=D("1130.00"))
    assert (paid.discount, paid.settles, paid.in_window) == (D(full), D("1130.00"), True)


def test_outside_the_window_no_discount() -> None:
    paid = for_payment(terms(), D("1107.40"), day(2026, 11, 12), open_balance=D("1130.00"))
    assert (paid.discount, paid.settles, paid.in_window) == (D("0.00"), D("1107.40"), False)


def test_partial_payments_pro_rata() -> None:
    t = terms()
    first = for_payment(t, D("553.70"), day(2026, 11, 5), open_balance=D("1130.00"))
    assert (first.discount, first.settles) == (D("11.30"), D("565.00"))
    second = for_payment(
        t,
        D("553.70"),
        day(2026, 11, 10),
        open_balance=D("565.00"),
        already_discounted=first.discount,
    )
    assert (second.discount, second.settles) == (D("11.30"), D("565.00"))
    # a third payment finds nothing left to discount
    third = for_payment(t, D("5.00"), UNTIL, open_balance=D("0.00"), already_discounted=D("22.60"))
    assert third.discount == D("0.00")


def test_partial_then_late() -> None:
    t = terms()
    first = for_payment(t, D("553.70"), day(2026, 11, 5), open_balance=D("1130.00"))
    late = for_payment(
        t, D("565.00"), day(2026, 11, 20), open_balance=D("565.00"), already_discounted=D("11.30")
    )
    assert first.discount == D("11.30") and late.discount == D("0.00")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("moment", "inside"),
    [
        (dt.datetime(2026, 11, 11, 23, 59, tzinfo=ZoneInfo("America/Toronto")), True),
        (dt.datetime(2026, 11, 12, 0, 0, tzinfo=ZoneInfo("America/Toronto")), False),
        # 04:30 UTC on the 12th is 23:30 on the 11th in Toronto: still inside
        (dt.datetime(2026, 11, 12, 4, 30, tzinfo=dt.UTC), True),
        (dt.datetime(2026, 11, 12, 5, 0, tzinfo=dt.UTC), False),
    ],
)
def test_2359_boundary_in_the_organisation_time_zone(moment: dt.datetime, inside: bool) -> None:
    org = Organisation.objects.create(name="Maple Bakery Inc.", time_zone="America/Toronto")
    on = payment_day(org, moment)
    paid = for_payment(terms(), D("1107.40"), on, open_balance=D("1130.00"))
    assert paid.in_window is inside
    assert paid.discount == (D("22.60") if inside else D("0.00"))


amounts = st.decimals(min_value=D("0.01"), max_value=D("99999.99"), places=2)


@settings(max_examples=300, deadline=None)
@given(
    total=amounts,
    pct=st.decimals(min_value=D("0.25"), max_value=D("10"), places=2),
    parts=st.lists(
        st.decimals(min_value=D("0.01"), max_value=D("1"), places=2), min_size=1, max_size=5
    ),
    base=st.sampled_from([TOTAL, PRE_TAX]),
)
def test_discounts_add_up_to_the_full_discount(
    total: Decimal, pct: Decimal, parts: list[Decimal], base: str
) -> None:
    t = EarlyDiscount(pct, UNTIL, total, (total / D("1.13")).quantize(D("0.01")), base)
    balance, taken = total, D("0.00")
    target = t.discounted_total
    shares = [p / sum(parts) for p in parts]
    paid_so_far = D("0.00")
    for i, share in enumerate(shares):
        amount = (
            target - paid_so_far
            if i == len(shares) - 1
            else min((target * share).quantize(D("0.01")), target - paid_so_far)
        )
        if amount <= 0:
            continue
        result = for_payment(t, amount, UNTIL, open_balance=balance, already_discounted=taken)
        assert D("0.00") <= result.discount <= t.full_discount - taken
        assert result.settles <= balance
        balance -= result.settles
        taken += result.discount
        paid_so_far += amount
    assert taken <= t.full_discount
    if paid_so_far == target:
        assert balance == D("0.00") and taken == t.full_discount
