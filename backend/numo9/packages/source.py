"""Packages for the catalogue's feature matrix (U-01-T09 interface, implemented by U-02).

``settings.NUMO9_PACKAGE_SOURCE`` points here: the feature matrix, its exports and the in-app
"Package and features" page list the packages **offered** (active) with their products — the
products chosen for the package plus the free sets (Practice, Client portal), which are part of
every package. Names are the client's, in the request's language. The organisation's current
package comes from the subscription source (None until U-03/U-04).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import translation

from numo9.catalogue.models import Product, ProductKind
from numo9.catalogue.packages import PackageRef

from .models import Package
from .subscriptions import get_source

if TYPE_CHECKING:
    from numo9.tenancy.models import Organisation


def free_sets() -> frozenset[str]:
    return frozenset(
        Product.objects.filter(kind=ProductKind.FREE_SET).values_list("code", flat=True)
    )


class OfferedPackages:
    def packages(self) -> list[PackageRef]:
        locale = translation.get_language() or "en-CA"
        free = free_sets()
        offered = Package.objects.offered().prefetch_related("products").order_by("sort", "code")
        return [
            PackageRef(
                package.code,
                package.name(locale),
                frozenset(p.code for p in package.products.all()) | free,
            )
            for package in offered
        ]

    def current_package(self, organisation: Organisation) -> str | None:
        return get_source().package_of(organisation)
