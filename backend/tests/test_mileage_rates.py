"""E-04-T02 — ``MileageRate``: the CRA per-kilometre rates as effective-dated data, seeded for
2022–2026 with the 5,000 km tier threshold; the rate in force on a date is selected."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.purchases.mileage import rate_on, region_for, seed_mileage_rates
from numo9.purchases.models import MileageRate, MileageRegion

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("day", "first", "after"),
    [
        (dt.date(2024, 7, 1), "0.70", "0.64"),
        (dt.date(2025, 1, 1), "0.72", "0.66"),
        (dt.date(2025, 12, 31), "0.72", "0.66"),
        (dt.date(2026, 1, 1), "0.73", "0.67"),
        (dt.date(2030, 5, 5), "0.73", "0.67"),  # the latest year stays open
    ],
)
def test_rate_by_date_selected(day: dt.date, first: str, after: str) -> None:
    rate = rate_on(day)
    assert (rate.first_tier_rate, rate.second_tier_rate) == (Decimal(first), Decimal(after))
    assert rate.tier_threshold_km == 5000


def test_territories_are_four_cents_higher() -> None:
    for year in range(2022, 2027):
        day = dt.date(year, 6, 1)
        prov, terr = rate_on(day), rate_on(day, MileageRegion.TERRITORIES)
        assert terr.first_tier_rate - prov.first_tier_rate == Decimal("0.04")
        assert terr.second_tier_rate - prov.second_tier_rate == Decimal("0.04")


def test_region_for_province_codes() -> None:
    assert region_for("ON") == MileageRegion.PROVINCES
    assert region_for("nu") == MileageRegion.TERRITORIES
    assert region_for("YT") == MileageRegion.TERRITORIES


def test_no_rate_before_the_seeded_years() -> None:
    with pytest.raises(ValidationError) as err:
        rate_on(dt.date(2019, 3, 1))
    assert err.value.code == "mileage_rate_missing"


def test_seed_is_idempotent() -> None:
    before = MileageRate.objects.count()
    assert before == 10
    seed_mileage_rates()
    assert MileageRate.objects.count() == before


def test_next_year_seeded_as_data_closes_the_open_row() -> None:
    open_row = MileageRate.objects.get(region="provinces", effective_to__isnull=True)
    open_row.effective_to = dt.date(2026, 12, 31)
    open_row.save()
    MileageRate.objects.create(
        region="provinces",
        effective_from=dt.date(2027, 1, 1),
        first_tier_rate=Decimal("0.75"),
        second_tier_rate=Decimal("0.69"),
    )
    assert rate_on(dt.date(2026, 12, 31)).first_tier_rate == Decimal("0.73")
    assert rate_on(dt.date(2027, 1, 1)).first_tier_rate == Decimal("0.75")


def test_constraints() -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        MileageRate.objects.create(  # duplicate start for the region
            region="provinces",
            effective_from=dt.date(2026, 1, 1),
            first_tier_rate=Decimal("1"),
            second_tier_rate=Decimal("1"),
        )
    with transaction.atomic(), pytest.raises(IntegrityError):
        MileageRate.objects.create(
            region="provinces",
            effective_from=dt.date(2031, 1, 1),
            effective_to=dt.date(2030, 1, 1),
            first_tier_rate=Decimal("1"),
            second_tier_rate=Decimal("1"),
        )
    with transaction.atomic(), pytest.raises(IntegrityError):
        MileageRate.objects.create(
            region="provinces",
            effective_from=dt.date(2032, 1, 1),
            first_tier_rate=Decimal("0"),
            second_tier_rate=Decimal("1"),
        )
