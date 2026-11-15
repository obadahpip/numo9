"""Subscriptions as packages see them (U-02 interface ``packages.subscriptions``; U-03).

``settings.NUMO9_SUBSCRIPTION_SOURCE`` points here:

- ``count(package)`` — subscriptions on the package that haven't ended (not cancelled): a package
  with subscribers is never deleted, only retired;
- ``affected_by_price(package, interval, effective_from)`` — subscriptions on the package that will
  renew at a price starting that day. The billing interval and the grandfathered flag arrive with
  the Stripe fields (U-04-T02); until then every subscription on the package that hasn't ended is
  counted, whatever the interval;
- ``package_of(organisation)`` — the package code of the organisation's current subscription.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from .models import Subscription, SubscriptionStatus, current_subscription

if TYPE_CHECKING:
    from numo9.packages.models import Package
    from numo9.tenancy.models import Organisation


def _live_on(package: Package) -> int:
    return (
        Subscription._base_manager.filter(package_id=package.pk, deleted_at__isnull=True)
        .exclude(status=SubscriptionStatus.CANCELLED)
        .count()
    )


class Subscriptions:
    def count(self, package: Package) -> int:
        return _live_on(package)

    def affected_by_price(self, package: Package, interval: str, effective_from: date) -> int:
        return _live_on(package)

    def package_of(self, organisation: Organisation) -> str | None:
        subscription = current_subscription(organisation)
        if subscription is None or subscription.package_id is None:
            return None
        return subscription.package.code if subscription.package else None
