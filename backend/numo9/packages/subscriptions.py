"""Subscriptions as packages see them (U-02-T05, T10) — the interface U-03/U-04 implement.

Packages need three answers about subscriptions, which arrive with the ``Subscription`` model
(U-03-T02) and its billing fields (U-04):

- ``count(package)`` — subscriptions on the package that haven't ended (any status but
  cancelled): a package with subscribers is never deleted, only retired;
- ``affected_by_price(package, interval, effective_from)`` — subscriptions on that package and
  interval that will renew at a price starting on ``effective_from`` (every one that is not
  grandfathered: each renews on or after that date sooner or later). The console's price dialog
  shows it before a price change is scheduled (U-02-T10);
- ``package_of(organisation)`` — the code of the organisation's package, or None.

Until U-03 the source is ``NoSubscriptions``: nobody subscribes yet. U-03 sets
``NUMO9_SUBSCRIPTION_SOURCE`` (or changes the default here); packages need no change.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from numo9.tenancy.models import Organisation

    from .models import Package

DEFAULT_SOURCE = "numo9.packages.subscriptions.NoSubscriptions"


class SubscriptionSource(Protocol):
    def count(self, package: Package) -> int: ...

    def affected_by_price(self, package: Package, interval: str, effective_from: date) -> int: ...

    def package_of(self, organisation: Organisation) -> str | None: ...


class NoSubscriptions:
    """Interface stub until U-03: no organisation subscribes yet."""

    def count(self, package: Package) -> int:
        return 0

    def affected_by_price(self, package: Package, interval: str, effective_from: date) -> int:
        return 0

    def package_of(self, organisation: Organisation) -> str | None:
        return None


def get_source() -> SubscriptionSource:
    path = getattr(settings, "NUMO9_SUBSCRIPTION_SOURCE", DEFAULT_SOURCE) or DEFAULT_SOURCE
    source: SubscriptionSource = import_string(path)()
    return source
