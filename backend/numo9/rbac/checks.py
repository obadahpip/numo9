"""System check: every API endpoint declares its permission per method (A-03-T05).

For every DRF view reachable from ``ROOT_URLCONF``:

- ``rbac.E001`` — an HTTP method handler has no declaration (``@requires_permission`` or
  ``required_permission`` on the class);
- ``rbac.E002`` — a declaration names a key that is not in the catalogue (and is not ``PUBLIC``
  or ``AUTHENTICATED``);
- ``rbac.E003`` — the view's ``permission_classes`` don't include ``RequiresPermission``, so the
  declaration would not be enforced;
- ``rbac.E004`` — a third-party DRF view (module outside ``RBAC_VIEW_MODULE_PREFIXES``, default
  ``numo9.``) that is not on ``settings.RBAC_EXEMPT_VIEWS`` (dotted path → why it is safe);
- ``rbac.E005`` — a view that is not a DRF view mounted under ``/api/`` (it would bypass
  ``RequiresPermission`` entirely), unless it is on ``settings.RBAC_EXEMPT_VIEWS`` (A-03-T06).

Non-DRF views outside ``/api/`` (django-allauth's headless authentication API, Django admin, the
health check) are outside the catalogue: authentication endpoints act only on the caller's own
account, and the admin is limited to platform staff (A-01-T15).

CI (A-03-T06): the backend job runs ``manage.py permission_check`` — the readable report of every
endpoint and method with its declaration, failing on any of these errors — and a canary that runs
it on a fixture URLconf with an undeclared view and must fail.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core import checks
from rest_framework.views import APIView

from .catalogue import catalogue
from .drf import SENTINELS, RequiresPermission, declared_permission

HTTP_METHODS = ("get", "post", "put", "patch", "delete")


#: Routes whose views must all be DRF views (so ``RequiresPermission`` applies), A-03-T06.
API_ROUTE = re.compile(r"^api/")


def _callback_path(callback: Any) -> str:
    target = getattr(callback, "view_class", None) or getattr(callback, "cls", None) or callback
    return f"{target.__module__}.{getattr(target, '__qualname__', type(target).__qualname__)}"


def _non_drf_api_views(urlconf: str | None = None) -> Iterator[tuple[str, str]]:
    """(route, dotted path) of every non-DRF view mounted under ``api/``."""
    from numo9.tenancy.sweep import iter_endpoints

    for endpoint in iter_endpoints(urlconf):
        view_class = endpoint.view_class
        if isinstance(view_class, type) and issubclass(view_class, APIView):
            continue
        if API_ROUTE.match(endpoint.route):
            yield endpoint.display or endpoint.route, _callback_path(endpoint.callback)


def _drf_views(urlconf: str | None = None) -> Iterator[tuple[str, type[APIView], dict[str, str]]]:
    from numo9.tenancy.sweep import iter_endpoints

    seen: set[tuple[type, str]] = set()
    for endpoint in iter_endpoints(urlconf):
        view_class = endpoint.view_class
        if not (isinstance(view_class, type) and issubclass(view_class, APIView)):
            continue
        # ViewSets map HTTP methods to actions (callback.actions); plain views use the methods.
        actions: dict[str, str] = getattr(endpoint.callback, "actions", None) or {
            m: m for m in HTTP_METHODS if hasattr(view_class, m)
        }
        key = (view_class, endpoint.route)
        if key in seen:
            continue
        seen.add(key)
        yield endpoint.display or endpoint.route, view_class, actions


def _path(view_class: type) -> str:
    return f"{view_class.__module__}.{view_class.__qualname__}"


def _declaration(view_class: type, method: str, handler: str) -> str | None:
    # ViewSets declare on the action (e.g. "list"); plain views on the method.
    return declared_permission(view_class, handler) or declared_permission(view_class, method)


@dataclass(frozen=True)
class Declaration:
    """One endpoint method and what it requires (``manage.py permission_check`` report)."""

    route: str
    method: str
    view: str
    permission: str | None  # catalogue key, PUBLIC / AUTHENTICATED, or None (undeclared)


def declarations(urlconf: str | None = None) -> list[Declaration]:
    """Every method of every Numo9 DRF view reachable from the URLconf, with its declaration."""
    own = tuple(getattr(settings, "RBAC_VIEW_MODULE_PREFIXES", ("numo9.",)))
    rows: list[Declaration] = []
    for route, view_class, actions in _drf_views(urlconf):
        if not view_class.__module__.startswith(own):
            continue
        for method, handler in sorted(actions.items()):
            rows.append(
                Declaration(
                    route,
                    method.upper(),
                    _path(view_class),
                    _declaration(view_class, method, handler),
                )
            )
    return rows


def check_permission_declarations(
    app_configs: Sequence[AppConfig] | None = None, urlconf: str | None = None, **kwargs: Any
) -> list[checks.CheckMessage]:
    exempt: dict[str, str] = getattr(settings, "RBAC_EXEMPT_VIEWS", {})
    own = tuple(getattr(settings, "RBAC_VIEW_MODULE_PREFIXES", ("numo9.",)))
    messages: list[checks.CheckMessage] = []
    for route, view_class, actions in _drf_views(urlconf):
        path = _path(view_class)
        if not view_class.__module__.startswith(own):
            if path not in exempt:
                messages.append(
                    checks.Error(
                        f"/{route}: third-party API view {path} has no permission declaration.",
                        hint="Wrap it in a Numo9 view with required_permission, or add it to "
                        "settings.RBAC_EXEMPT_VIEWS with the reason it is safe.",
                        obj=view_class,
                        id="rbac.E004",
                    )
                )
            continue
        if not any(
            isinstance(cls, type) and issubclass(cls, RequiresPermission)
            for cls in view_class.permission_classes
        ):
            messages.append(
                checks.Error(
                    f"/{route}: {path} does not use RequiresPermission.",
                    hint="Add numo9.rbac.drf.RequiresPermission to permission_classes (it is the "
                    "default; a view that sets permission_classes must list it).",
                    obj=view_class,
                    id="rbac.E003",
                )
            )
        for method, handler in sorted(actions.items()):
            key = _declaration(view_class, method, handler)
            if key is None:
                messages.append(
                    checks.Error(
                        f"/{route}: {method.upper()} on {path} declares no required permission.",
                        hint="Decorate the method with @requires_permission('<catalogue key>') "
                        "(or PUBLIC / AUTHENTICATED), or set required_permission on the class.",
                        obj=view_class,
                        id="rbac.E001",
                    )
                )
            elif key not in SENTINELS and key not in catalogue:
                messages.append(
                    checks.Error(
                        f"/{route}: {method.upper()} on {path} requires unknown permission "
                        f"{key!r}.",
                        hint="Declare it in the app's permissions.py (A-03-T01) or fix the key.",
                        obj=view_class,
                        id="rbac.E002",
                    )
                )
    for route, path in _non_drf_api_views(urlconf):
        if path in exempt:
            continue
        messages.append(
            checks.Error(
                f"/{route}: {path} is not a DRF view, so no permission is checked.",
                hint="Write API endpoints as DRF views with required_permission, or add the view "
                "to settings.RBAC_EXEMPT_VIEWS with the reason it is safe.",
                obj=path,
                id="rbac.E005",
            )
        )
    return messages
