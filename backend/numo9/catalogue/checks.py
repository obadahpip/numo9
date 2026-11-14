"""Feature-key declarations of the API (U-01-T07): what ``manage.py check_feature_keys`` walks.

For every Numo9 DRF view reachable from the URLconf, every method's feature declaration
(``@requires_feature`` / ``required_feature``, ``numo9.catalogue.drf``). Problems:

- ``feature.E001`` — a **business endpoint** (a route matching ``FEATURE_BUSINESS_ROUTES``,
  default the organisation and practice routes ``api/v1/o/…`` and ``api/v1/p/…``) has a method
  with no declaration: neither a key nor ``CORE``;
- ``feature.E002`` — a declaration names a key that is not in the catalogue (the
  ``catalogue_featurekey`` table: keys are data, seeded by migrations — a typo or a key whose
  data migration is missing);
- ``feature.E003`` — a business endpoint's ``permission_classes`` don't include
  ``RequiresFeature``, so its key would not be enforced.

Endpoints outside the business routes (sign-in, the user's own memberships, the platform
console, the catalogue itself) need no key; when they declare one it must still exist.

The known keys come from the database, so this is a management command, not a system check
(system checks must not query the database): CI migrates first.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from rest_framework.views import APIView

from .drf import CORE, RequiresFeature, declared_feature

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
DEFAULT_BUSINESS_ROUTES: tuple[str, ...] = (r"^api/v1/o/", r"^api/v1/p/")


def business_routes() -> list[re.Pattern[str]]:
    patterns = getattr(settings, "FEATURE_BUSINESS_ROUTES", DEFAULT_BUSINESS_ROUTES)
    return [re.compile(p) for p in patterns]


@dataclass(frozen=True)
class FeatureDeclaration:
    route: str
    method: str
    view: str
    feature: str | None  # key, CORE or None (undeclared)
    business: bool
    enforced: bool  # RequiresFeature in permission_classes


@dataclass(frozen=True)
class Problem:
    id: str
    msg: str
    hint: str


def _views(urlconf: str | None) -> Iterator[tuple[str, type[APIView], dict[str, str]]]:
    from numo9.tenancy.sweep import iter_endpoints

    seen: set[tuple[type, str]] = set()
    for endpoint in iter_endpoints(urlconf):
        view_class = endpoint.view_class
        if not (isinstance(view_class, type) and issubclass(view_class, APIView)):
            continue
        if (view_class, endpoint.route) in seen:
            continue
        seen.add((view_class, endpoint.route))
        actions: dict[str, str] = getattr(endpoint.callback, "actions", None) or {
            m: m for m in HTTP_METHODS if hasattr(view_class, m)
        }
        yield endpoint.display or endpoint.route, view_class, actions


def declarations(urlconf: str | None = None) -> list[FeatureDeclaration]:
    own = tuple(getattr(settings, "RBAC_VIEW_MODULE_PREFIXES", ("numo9.",)))
    routes = business_routes()
    rows: list[FeatureDeclaration] = []
    for route, view_class, actions in _views(urlconf):
        if not view_class.__module__.startswith(own):
            continue  # third-party views: rbac.E004 already requires an exemption
        business = any(p.match(route) for p in routes)
        enforced = any(
            isinstance(cls, type) and issubclass(cls, RequiresFeature)
            for cls in view_class.permission_classes
        )
        for method, handler in sorted(actions.items()):
            feature = declared_feature(view_class, handler) or declared_feature(view_class, method)
            rows.append(
                FeatureDeclaration(
                    route,
                    method.upper(),
                    f"{view_class.__module__}.{view_class.__qualname__}",
                    feature,
                    business,
                    enforced,
                )
            )
    return rows


def problems(rows: Iterable[FeatureDeclaration], known: set[str]) -> list[Problem]:
    found: list[Problem] = []
    unenforced: set[tuple[str, str]] = set()
    for row in rows:
        where = f"/{row.route}: {row.method} on {row.view}"
        if row.feature is None:
            if row.business:
                found.append(
                    Problem(
                        "feature.E001",
                        f"{where} declares no feature key.",
                        "Decorate the method with @requires_feature('<product>.<area>.<action>'), "
                        "or set required_feature = CORE when it is part of every organisation.",
                    )
                )
        elif row.feature != CORE and row.feature not in known:
            found.append(
                Problem(
                    "feature.E002",
                    f"{where} requires unknown feature key {row.feature!r}.",
                    "Add the key to the catalogue with a data migration (numo9/catalogue/"
                    "migrations) and a description in numo9/catalogue/texts.py, or fix the typo.",
                )
            )
        if row.business and not row.enforced and (row.route, row.view) not in unenforced:
            unenforced.add((row.route, row.view))
            found.append(
                Problem(
                    "feature.E003",
                    f"/{row.route}: {row.view} does not use RequiresFeature.",
                    "Add numo9.catalogue.drf.RequiresFeature to permission_classes (it is a "
                    "default; a view that sets permission_classes must list it).",
                )
            )
    return found


def known_keys() -> set[str]:
    from .models import FeatureKey

    return set(FeatureKey.objects.values_list("key", flat=True))


def check(
    urlconf: str | None = None, **kwargs: Any
) -> tuple[list[FeatureDeclaration], list[Problem]]:
    rows = declarations(urlconf)
    return rows, problems(rows, known_keys())
