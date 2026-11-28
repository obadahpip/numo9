"""F-04-T06 — allocation calculator: fixed lines first, the remainder by percentage, rounding to
the last line, tax split per line.

Acceptance: 100.00 split 33.33 % × 3 → 33.33 / 33.33 / 33.34; property: the amounts always add up
to the line's amount; fixed over the amount or fixed-only not equal to it is refused; each line is
taxed on its own amount (113.00 HST split 50/50 → 50.00 + 6.50 HST twice).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from hypothesis import given, settings
from hypothesis import strategies as st

from numo9.banking.rules.allocation import Share, allocate, money_spec
from numo9.banking.services import create_bank_account
from numo9.ledger.models import SystemRole
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

D = Decimal
THIRD = D("33.33")


def amounts(total: str, shares: list[Share]) -> list[Decimal]:
    return [a.amount for a in allocate(D(total), shares)]


def test_three_thirds() -> None:
    shares = [Share(percent=THIRD), Share(percent=THIRD), Share(percent=D("33.34"))]
    assert amounts("100.00", shares) == [D("33.33"), D("33.33"), D("33.34")]
    # Negative statement amounts are split without their sign.
    assert amounts("-100.00", shares) == [D("33.33"), D("33.33"), D("33.34")]


def test_fixed_first_then_percent_remainder_to_last() -> None:
    shares = [Share(percent=D("50")), Share(fixed_amount=D("10.00")), Share(percent=D("50"))]
    assert amounts("100.01", shares) == [D("45.01"), D("10.00"), D("45.00")]


def test_tiny_amount_never_goes_negative() -> None:
    shares = [Share(percent=D("25"))] * 4
    assert amounts("0.02", shares) == [D("0.02")]


@pytest.mark.parametrize(
    ("total", "shares", "code"),
    [
        (
            "5.00",
            [Share(fixed_amount=D("10.00")), Share(percent=D("100"))],
            "banking.rule.fixed_exceeds",
        ),
        ("25.00", [Share(fixed_amount=D("20.00"))], "banking.rule.allocation_mismatch"),
    ],
)
def test_refused(total: str, shares: list[Share], code: str) -> None:
    with pytest.raises(ValidationError) as caught:
        allocate(D(total), shares)
    assert caught.value.code == code


@st.composite
def splits(draw: st.DrawFn) -> tuple[Decimal, list[Share]]:
    cents = draw(st.integers(min_value=1, max_value=10_000_000))
    fixed = draw(st.lists(st.integers(min_value=1, max_value=cents), max_size=3))
    if sum(fixed) > cents:
        fixed = []
    count = draw(st.integers(min_value=1, max_value=7))
    weights = draw(
        st.lists(st.integers(min_value=1, max_value=10_000), min_size=count, max_size=count)
    )
    total_weight = sum(weights)
    percents = [(D(w) * 100 / total_weight).quantize(D("0.0001")) for w in weights]
    percents[-1] = D(100) - sum(percents[:-1])
    if percents[-1] <= 0:
        percents = [D(100)]
    shares = [Share(fixed_amount=D(f) / 100) for f in fixed] + [Share(percent=p) for p in percents]
    order = draw(st.permutations(shares))
    return D(cents) / 100, list(order)


@settings(max_examples=300, deadline=None)
@given(splits())
def test_property_sum_equals_amount(split: tuple[Decimal, list[Share]]) -> None:
    total, shares = split
    result = allocate(total, shares)
    assert sum(a.amount for a in result) == total
    assert all(a.amount > 0 and a.amount == a.amount.quantize(D("0.01")) for a in result)


@pytest.mark.django_db
def test_tax_split_per_line() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
    with org_context(org):
        office, supplies = account(org, "5901", "Office"), account(org, "5902", "Supplies")
        shares = [
            Share(percent=D("50"), account=office, tax_code="purchase.ON.standard"),
            Share(percent=D("50"), account=supplies, tax_code="purchase.ON.standard"),
        ]
        spec = money_spec("spend", bank, dt.date(2026, 6, 15), allocate(D("-113.00"), shares))
    assert [line.amount for line in spec.lines] == [D("56.50"), D("56.50")]
    for line in spec.lines:
        assert [(p.role, p.amount) for p in line.taxes] == [(SystemRole.ITC_RECEIVABLE, D("6.50"))]
        assert line.tax_code == "purchase.ON.standard"
