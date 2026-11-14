"""Packages in the catalogue's matrix (U-01-T09) — the interface U-02 implements.

The feature matrix answers key → product → packages. Packages and their products are U-02
(``Package``, ``PackageProduct``); until it ships there are no packages, so the matrix lists every
key with its product and an empty package list. U-02 sets ``NUMO9_PACKAGE_SOURCE`` (or replaces
the default here); the API, the exports and the screens need no change. The organisation's
current package (highlighted on the in-app page) comes from the same source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from numo9.tenancy.models import Organisation

DEFAULT_SOURCE = "numo9.catalogue.packages.NoPackages"


@dataclass(frozen=True)
class PackageRef:
    code: str
    name: str
    #: Product codes in the package.
    products: frozenset[str] = field(default_factory=frozenset)


class PackageSource(Protocol):
    def packages(self) -> list[PackageRef]:
        """Packages offered for sale (active), in display order."""
        ...

    def current_package(self, organisation: Organisation) -> str | None:
        """Code of the organisation's package (its subscription, U-03/U-04), or None."""
        ...


class NoPackages:
    """Interface stub until U-02: no packages yet, so no organisation has one."""

    def packages(self) -> list[PackageRef]:
        return []

    def current_package(self, organisation: Organisation) -> str | None:
        return None


def get_source() -> PackageSource:
    path = getattr(settings, "NUMO9_PACKAGE_SOURCE", DEFAULT_SOURCE) or DEFAULT_SOURCE
    source: PackageSource = import_string(path)()
    return source
