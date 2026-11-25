"""D-04-T04 — proration of a first / last partial period: days covered / days in the period ×
the line amount, rounded per line (fixture 15 of 31 days → 15/31; Hypothesis)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from numo9.documents.calculator import cents
from numo9.sales.proration import Proration, for_template, proration

D = dt.date


def test_fixture_15_of_31_days() -> None:
    p = proration(D(2026, 10, 1), D(2026, 10, 31), service_start=D(2026, 10, 17))
    assert (p.covered, p.days, p.full) == (15, 31, False)
    assert p.amount(Decimal("1"), Decimal("310.00")) == Decimal("150.00")
    assert (
        p.amount(Decimal("1"), Decimal("1000.00"))
        == cents(Decimal("1000") * 15 / 31)
        == Decimal("483.87")
    )
    assert p.line(Decimal("1"), Decimal("1000.00")) == (Decimal("1"), Decimal("483.8700"))


def test_last_period_full_and_none() -> None:
    last = proration(D(2026, 2, 1), D(2026, 2, 28), service_end=D(2026, 2, 14))
    assert (last.covered, last.days) == (14, 28) and last.amount(
        Decimal("2"), Decimal("50")
    ) == Decimal("50.00")
    assert proration(D(2026, 2, 1), D(2026, 2, 28)).full
    assert proration(D(2026, 2, 1), D(2026, 2, 28), service_start=D(2026, 3, 5)).covered == 0
    with pytest.raises(ValueError):
        proration(D(2026, 2, 2), D(2026, 2, 1))


def test_template_flag() -> None:
    template = SimpleNamespace(prorate=False, service_start=D(2026, 10, 17), service_end=None)
    assert for_template(template, D(2026, 10, 1), D(2026, 10, 31)).full
    template.prorate = True
    assert for_template(template, D(2026, 10, 1), D(2026, 10, 31)) == Proration(15, 31)


@given(
    start=st.dates(min_value=D(2020, 1, 1), max_value=D(2030, 12, 31)),
    length=st.integers(min_value=0, max_value=365),
    offset=st.integers(min_value=0, max_value=400),
    quantity=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal("10000"), places=4),
    price=st.decimals(min_value=Decimal("0"), max_value=Decimal("100000"), places=4),
)
def test_property_prorated_line_matches_fraction(
    start: dt.date, length: int, offset: int, quantity: Decimal, price: Decimal
) -> None:
    end = start + dt.timedelta(days=length)
    p = proration(start, end, service_start=start + dt.timedelta(days=offset))
    assert 0 <= p.covered <= p.days == length + 1
    net = p.amount(quantity, price)
    assert net == cents(quantity * price * p.covered / p.days)
    assert Decimal("0") <= net <= cents(quantity * price)
    q, unit = p.line(quantity, price)
    assert cents(q * unit) == net
    assert unit == unit.quantize(Decimal("0.0001"))
