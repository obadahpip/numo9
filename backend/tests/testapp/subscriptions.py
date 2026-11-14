"""Subscription source over the SubscriptionStandIn model (U-02-T05, T10 tests)."""

from __future__ import annotations

from datetime import date

from django.db.models import QuerySet

from numo9.packages.models import Package
from numo9.tenancy.models import Organisation

from .models import SubscriptionStandIn

ENDED = ("cancelled",)


def _rows() -> QuerySet[SubscriptionStandIn]:
    return SubscriptionStandIn.objects.unscoped(reason="test subscription source").exclude(
        status__in=ENDED
    )


class StandInSubscriptions:
    def count(self, package: Package) -> int:
        return int(_rows().filter(package=package).count())

    def affected_by_price(self, package: Package, interval: str, effective_from: date) -> int:
        return int(_rows().filter(package=package, interval=interval, grandfathered=False).count())

    def package_of(self, organisation: Organisation) -> str | None:
        row = _rows().filter(organisation=organisation).select_related("package").first()
        return row.package.code if row is not None else None
