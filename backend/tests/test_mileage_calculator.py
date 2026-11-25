"""E-04-T03 — the mileage calculator: km × the CRA rate in force on the line's date, two tiers
around 5,000 business km in the calendar year counted per employee (YTD across their claims),
a line that crosses 5,000 km split between the tiers."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from numo9.purchases.mileage import mileage_amount, price_mileage, split_km, year_to_date_km
from numo9.purchases.models import ExpenseClaimStatus, MileageRate
from numo9.tenancy.context import org_context
from tests.expense_helpers import add_trip, expense_org, make_claim

KM = st.decimals(min_value=0, max_value=20000, places=1, allow_nan=False, allow_infinity=False)


@given(prior=KM, km=KM)
def test_split_adds_up_and_respects_the_threshold(prior: Decimal, km: Decimal) -> None:
    first, after = split_km(prior, km, Decimal(5000))
    assert first + after == km
    assert first >= 0 and after >= 0
    assert prior + first <= max(prior, Decimal(5000))
    if prior >= 5000:
        assert first == 0
    if prior + km <= 5000:
        assert after == 0


def _rate() -> MileageRate:
    return MileageRate(
        first_tier_rate=Decimal("0.73"), second_tier_rate=Decimal("0.67"), tier_threshold_km=5000
    )


@given(prior=KM, km=KM)
def test_amount_is_first_tier_then_second_tier(prior: Decimal, km: Decimal) -> None:
    amount, detail = mileage_amount(km, _rate(), prior)
    first = max(Decimal(0), min(km, 5000 - prior))
    expected = (first * Decimal("0.73") + (km - first) * Decimal("0.67")).quantize(Decimal("0.01"))
    assert amount == expected
    assert sum(Decimal(d["km"]) for d in detail) == km


def test_crossing_5000_km_splits_the_rate() -> None:
    amount, detail = mileage_amount(Decimal("300"), _rate(), Decimal("4900"))
    assert amount == Decimal("100") * Decimal("0.73") + Decimal("200") * Decimal("0.67")
    assert [(d["tier"], d["km"], d["rate"]) for d in detail] == [
        ("first", "100", "0.73"),
        ("after", "200", "0.67"),
    ]


def test_negative_km_rejected() -> None:
    with pytest.raises(ValueError):
        split_km(Decimal(0), Decimal(-1), Decimal(5000))


@pytest.mark.django_db
def test_claim_crossing_5000_km_with_ytd_from_earlier_claims() -> None:
    org, who = expense_org()
    owner = who["owner"]
    earlier = make_claim(
        org, owner, status=ExpenseClaimStatus.APPROVED, number="EXP-0001", submitted_at=_now()
    )
    add_trip(earlier, "4800", dt.date(2026, 3, 1))
    rejected = make_claim(
        org, owner, status=ExpenseClaimStatus.REJECTED, number="EXP-0002", submitted_at=_now()
    )
    add_trip(rejected, "1000", dt.date(2026, 3, 2))  # not counted
    last_year = make_claim(
        org, owner, status=ExpenseClaimStatus.PAID, number="EXP-0003", submitted_at=_now()
    )
    add_trip(last_year, "9000", dt.date(2025, 11, 2))  # another year
    claim = make_claim(org, owner)
    a = add_trip(claim, "150", dt.date(2026, 6, 1), position=1)
    b = add_trip(claim, "100", dt.date(2026, 6, 2), position=2)
    with org_context(org):
        assert year_to_date_km(claim, a) == Decimal("4800")
        assert year_to_date_km(claim, b) == Decimal("4950")
        total = price_mileage(claim)
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.amount == Decimal("109.50")  # 150 × 0.73
    assert b.amount == Decimal("36.50") + Decimal("33.50")  # 50 × 0.73 + 50 × 0.67
    assert [d["tier"] for d in b.rate_detail] == ["first", "after"]
    assert total == a.amount + b.amount


@pytest.mark.django_db
def test_ytd_is_per_employee_and_rate_by_line_date() -> None:
    org, who = expense_org()
    other = make_claim(
        org,
        who["adviser"],
        status=ExpenseClaimStatus.SUBMITTED,
        number="EXP-0001",
        submitted_at=_now(),
    )
    add_trip(other, "6000", dt.date(2025, 2, 1))
    claim = make_claim(org, who["owner"])
    trip = add_trip(claim, "100", dt.date(2025, 2, 10))
    with org_context(org):
        assert year_to_date_km(claim, trip) == 0
        price_mileage(claim)
    trip.refresh_from_db()
    assert trip.amount == Decimal("72.00")  # 2025 rate, first tier


def _now() -> dt.datetime:
    from django.utils import timezone

    return timezone.now()
