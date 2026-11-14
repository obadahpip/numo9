"""Which price applies on a day (U-02-T04).

``price_for(package, interval, on_date)`` returns the ``PackagePrice`` version in force on
``on_date`` — the one with ``effective_from <= on_date < effective_to`` (no end = open) — and
raises ``PriceNotFound`` when there is none (before the first version, in a gap, or an interval
the package isn't sold at). The database guarantees at most one version per day
(``packages_price_no_overlap``).

The renewal rule (U-04): a subscription renews at ``price_for(package, interval, renewal_date)``
unless it is grandfathered — so a price dated in the future changes nothing until a renewal on
or after its start date.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Q

from .models import Package, PackagePrice


class PriceNotFound(LookupError):
    """No price version of the package and interval is in force on the day."""

    def __init__(self, package: Package, interval: str, on_date: date) -> None:
        self.package = package
        self.interval = interval
        self.on_date = on_date
        super().__init__(
            f"No {interval} price for package {package.code} on {on_date.isoformat()}."
        )


def in_force(on_date: date) -> Q:
    return Q(effective_from__lte=on_date) & (
        Q(effective_to__isnull=True) | Q(effective_to__gt=on_date)
    )


def price_for(package: Package, interval: str, on_date: date) -> PackagePrice:
    """The price version of ``package`` for ``interval`` in force on ``on_date``."""
    found = (
        PackagePrice.objects.filter(package=package, interval=interval)
        .filter(in_force(on_date))
        .order_by("-effective_from")
        .first()
    )
    if found is None:
        raise PriceNotFound(package, interval, on_date)
    return found


def current_prices(package: Package, on_date: date) -> dict[str, PackagePrice]:
    """``{interval: version in force on on_date}`` for the intervals that have one."""
    rows = PackagePrice.objects.filter(package=package).filter(in_force(on_date))
    return {row.interval: row for row in rows}


def next_price(package: Package, interval: str, on_date: date) -> PackagePrice | None:
    """The first version that starts after ``on_date`` (a scheduled change), if any."""
    return (
        PackagePrice.objects.filter(package=package, interval=interval, effective_from__gt=on_date)
        .order_by("effective_from")
        .first()
    )
