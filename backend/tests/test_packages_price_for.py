"""price_for(package, interval, on_date) (U-02-T04). Acceptance: returns the version effective on
the date; raises if none — unit tests plus a property test over random windows (Hypothesis)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.db import transaction
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.packages.models import BillingInterval, Package, PackagePrice
from numo9.packages.prices import PriceNotFound, current_prices, next_price, price_for

pytestmark = pytest.mark.django_db

MONTH = BillingInterval.MONTH
YEAR = BillingInterval.YEAR
D0 = date(2026, 1, 1)


@pytest.fixture
def package() -> Package:
    return Package.objects.create(code="growth", name_i18n={"en-CA": "Growth"})


def version(
    package: Package, start: date, end: date | None, cents: int, interval: str = MONTH
) -> PackagePrice:
    return PackagePrice.objects.create(
        package=package,
        interval=interval,
        amount_cents=cents,
        effective_from=start,
        effective_to=end,
    )


def test_returns_the_version_effective_on_the_date(package: Package) -> None:
    old = version(package, D0, date(2026, 11, 1), 3900)
    new = version(package, date(2026, 11, 1), None, 4900)
    assert price_for(package, MONTH, D0) == old
    assert price_for(package, MONTH, date(2026, 10, 31)) == old
    assert price_for(package, MONTH, date(2026, 11, 1)) == new  # start day is the new price
    assert price_for(package, MONTH, date(2040, 1, 1)) == new  # open window


def test_raises_when_there_is_none(package: Package) -> None:
    version(package, D0, date(2026, 3, 1), 3900)
    version(package, date(2026, 4, 1), None, 4900)
    for day in (date(2025, 12, 31), date(2026, 3, 1), date(2026, 3, 31)):  # before and in a gap
        with pytest.raises(PriceNotFound) as missing:
            price_for(package, MONTH, day)
        assert missing.value.on_date == day
    with pytest.raises(PriceNotFound):
        price_for(package, YEAR, date(2026, 5, 1))  # not sold yearly
    assert isinstance(missing.value, LookupError)


def test_intervals_and_packages_are_separate(package: Package) -> None:
    monthly = version(package, D0, None, 4900)
    yearly = version(package, D0, None, 49000, YEAR)
    other = Package.objects.create(code="complete", name_i18n={"en-CA": "Complete"})
    version(other, D0, None, 9900)
    assert price_for(package, MONTH, D0) == monthly
    assert price_for(package, YEAR, D0) == yearly
    assert current_prices(package, D0) == {MONTH: monthly, YEAR: yearly}


def test_next_price_is_the_scheduled_change(package: Package) -> None:
    version(package, D0, date(2026, 11, 1), 3900)
    scheduled = version(package, date(2026, 11, 1), None, 4900)
    assert next_price(package, MONTH, date(2026, 6, 1)) == scheduled
    assert next_price(package, MONTH, date(2026, 11, 1)) is None


# ---- property: random non-overlapping windows ---------------------------------------------------


@st.composite
def windows(draw: st.DrawFn) -> list[tuple[int, int | None, int]]:
    """Sorted, non-overlapping windows as day offsets from D0: (start, end or None, cents)."""
    cuts = sorted(draw(st.sets(st.integers(0, 400), min_size=1, max_size=8)))
    result: list[tuple[int, int | None, int]] = []
    for i, start in enumerate(cuts):
        following = cuts[i + 1] if i + 1 < len(cuts) else None
        if following is None:
            end = draw(st.one_of(st.none(), st.integers(start + 1, start + 60)))
        else:
            # end exactly at the next start (adjacent) or earlier (a gap)
            end = draw(st.integers(start + 1, following))
        result.append((start, end, draw(st.integers(0, 100_000))))
    return result


def reference(rows: list[tuple[int, int | None, int]], day: int) -> int | None:
    hits = [cents for start, end, cents in rows if start <= day and (end is None or day < end)]
    assert len(hits) <= 1
    return hits[0] if hits else None


class _Rollback(Exception):
    pass


@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(rows=windows(), days=st.lists(st.integers(-10, 480), min_size=1, max_size=12))
def test_matches_a_reference_on_random_windows(
    package: Package, rows: list[tuple[int, int | None, int]], days: list[int]
) -> None:
    try:
        with transaction.atomic():
            for start, end, cents in rows:
                version(
                    package,
                    D0 + timedelta(start),
                    D0 + timedelta(end) if end is not None else None,
                    cents,
                )
            for day in days:
                expected = reference(rows, day)
                if expected is None:
                    with pytest.raises(PriceNotFound):
                        price_for(package, MONTH, D0 + timedelta(day))
                else:
                    found = price_for(package, MONTH, D0 + timedelta(day))
                    assert found.amount_cents == expected
                    assert found.covers(D0 + timedelta(day))
            raise _Rollback
    except _Rollback:
        pass
