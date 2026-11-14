"""PackagePrice model (U-02-T03): versions per package and interval, whole cents in CAD,
``effective_from``/``effective_to``. Acceptance: an overlapping row is rejected by the database
(btree_gist exclusion constraint)."""

from __future__ import annotations

from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction

from numo9.packages.models import (
    BillingInterval,
    Package,
    PackageError,
    PackagePrice,
    TaxBehaviour,
)

pytestmark = pytest.mark.django_db

postgres_only = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="the exclusion constraint is PostgreSQL-only"
)

MONTH = BillingInterval.MONTH
YEAR = BillingInterval.YEAR


@pytest.fixture
def package() -> Package:
    return Package.objects.create(code="growth", name_i18n={"en-CA": "Growth"})


def price(
    package: Package,
    start: date,
    end: date | None = None,
    *,
    interval: str = MONTH,
    cents: int = 4900,
) -> PackagePrice:
    return PackagePrice.objects.create(
        package=package,
        interval=interval,
        amount_cents=cents,
        effective_from=start,
        effective_to=end,
    )


def raw_insert(package: Package, start: date, end: date | None, interval: str = MONTH) -> None:
    """Straight to the database: no model validation, only the database's own rules."""
    PackagePrice.objects.bulk_create(
        [
            PackagePrice(
                package=package,
                interval=interval,
                amount_cents=100,
                effective_from=start,
                effective_to=end,
            )
        ]
    )


# ---- acceptance -------------------------------------------------------------------------------


@postgres_only
@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 6, 1), None),  # open window inside the open one
        (date(2026, 6, 1), date(2026, 7, 1)),  # inside
        (date(2025, 12, 1), date(2026, 1, 2)),  # overlaps the first day
        (date(2026, 1, 1), date(2026, 2, 1)),  # same start
    ],
)
def test_overlapping_row_is_rejected_by_the_database(
    package: Package, start: date, end: date | None
) -> None:
    raw_insert(package, date(2026, 1, 1), None)
    with pytest.raises(IntegrityError) as refused, transaction.atomic():
        raw_insert(package, start, end)
    assert "packages_price_no_overlap" in str(refused.value)
    assert PackagePrice.objects.count() == 1


@postgres_only
def test_adjacent_windows_and_other_intervals_or_packages_are_fine(package: Package) -> None:
    raw_insert(package, date(2026, 1, 1), date(2026, 11, 1))
    raw_insert(package, date(2026, 11, 1), None)  # [from, to): the end day belongs to the next
    raw_insert(package, date(2026, 1, 1), None, interval=YEAR)
    other = Package.objects.create(code="complete", name_i18n={"en-CA": "Complete"})
    raw_insert(other, date(2026, 1, 1), None)
    assert PackagePrice.objects.count() == 4


@postgres_only
def test_overlap_with_a_closed_window(package: Package) -> None:
    raw_insert(package, date(2026, 1, 1), date(2026, 3, 1))
    with pytest.raises(IntegrityError), transaction.atomic():
        raw_insert(package, date(2026, 2, 28), date(2026, 4, 1))
    raw_insert(package, date(2026, 3, 1), date(2026, 4, 1))


# ---- fields and rules -------------------------------------------------------------------------


def test_defaults_cad_and_before_tax(package: Package) -> None:
    row = price(package, date(2026, 1, 1))
    assert row.currency == "CAD"
    assert row.tax_behaviour == TaxBehaviour.EXCLUSIVE
    assert row.effective_to is None
    assert str(row) == "growth month 49.00 CAD [2026-01-01, …)"


def test_other_currencies_are_rejected(package: Package) -> None:
    row = PackagePrice(
        package=package,
        interval=MONTH,
        amount_cents=4900,
        currency="USD",
        effective_from=date(2026, 1, 1),
    )
    with pytest.raises(PackageError) as refused:
        row.save()
    assert refused.value.error_dict["currency"][0].code == "packages.currency_cad"
    with pytest.raises(IntegrityError), transaction.atomic():
        PackagePrice.objects.bulk_create([row])  # the database refuses it too


def test_end_must_be_after_start(package: Package) -> None:
    with pytest.raises(PackageError):
        price(package, date(2026, 1, 1), date(2026, 1, 1))
    with pytest.raises(IntegrityError), transaction.atomic():
        raw_insert(package, date(2026, 1, 2), date(2026, 1, 1))


def test_database_refuses_unknown_interval_and_negative_amounts(package: Package) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        raw_insert(package, date(2026, 1, 1), None, interval="week")
    row = price(package, date(2026, 1, 1))
    with pytest.raises(IntegrityError), transaction.atomic():
        PackagePrice.objects.filter(pk=row.pk).update(amount_cents=-1)


def test_a_version_never_changes_except_its_end(package: Package) -> None:
    row = price(package, date(2026, 1, 1))
    row.effective_to = date(2026, 11, 1)
    row.save()  # closing the window is allowed
    for field, value in (
        ("amount_cents", 5900),
        ("interval", YEAR),
        ("effective_from", date(2026, 2, 1)),
    ):
        stored = PackagePrice.objects.get(pk=row.pk)
        setattr(stored, field, value)
        with pytest.raises(PackageError) as refused:
            stored.save()
        assert refused.value.code == "packages.price_immutable"


def test_free_price_is_allowed(package: Package) -> None:
    assert price(package, date(2026, 1, 1), cents=0).amount_cents == 0


def test_covers(package: Package) -> None:
    row = price(package, date(2026, 1, 1), date(2026, 2, 1))
    assert not row.covers(date(2025, 12, 31))
    assert row.covers(date(2026, 1, 1)) and row.covers(date(2026, 1, 31))
    assert not row.covers(date(2026, 2, 1))


def test_deleting_a_draft_package_removes_its_prices(package: Package) -> None:
    price(package, date(2026, 1, 1))
    package.delete()
    assert not PackagePrice.objects.exists()
