"""Entitlement resolution interface (U-01-T05) — the stub the U-03 engine replaces.

``RequiresFeature`` asks the resolver named by ``settings.NUMO9_ENTITLEMENT_RESOLVER`` whether
the active organisation's package includes a feature key. Until U-03 ships its engine
(organisation → subscription → package → products → features, cached, read-retention rule) the
default resolver allows every key, so declaring keys never blocks Phase 0 screens.

    class EntitlementResolver(Protocol):
        def allows(self, organisation, key) -> bool: ...

U-03 sets ``NUMO9_ENTITLEMENT_RESOLVER = "numo9.<app>.entitlements.Engine"`` (or changes the
default here) — no view or decorator changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from numo9.tenancy.models import Organisation

DEFAULT_RESOLVER = "numo9.catalogue.entitlements.AllowAllResolver"


class EntitlementResolver(Protocol):
    def allows(self, organisation: Organisation | None, key: str) -> bool:
        """Whether ``organisation`` (None outside an organisation) may use feature ``key``."""
        ...


class AllowAllResolver:
    """Interface stub until U-03: every feature key is allowed."""

    def allows(self, organisation: Organisation | None, key: str) -> bool:
        return True


def get_resolver() -> EntitlementResolver:
    path = getattr(settings, "NUMO9_ENTITLEMENT_RESOLVER", DEFAULT_RESOLVER) or DEFAULT_RESOLVER
    resolver: EntitlementResolver = import_string(path)()
    return resolver
