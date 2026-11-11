"""Permission declarations for API views (A-03-T05).

Every method of every Numo9 API view says which permission it needs; ``RequiresPermission``
enforces it and the system check ``rbac.E001``–``E004`` (``checks.py``) fails start-up and CI
when a view forgets to.

Declare per method with the decorator, or on the class:

    class ContactList(APIView):
        permission_classes = [IsOrgMemberOrAssigned, RequiresPermission]

        @requires_permission("contacts.contact.view")
        def get(self, request, org): ...

    class CsrfTokenView(APIView):
        permission_classes = [RequiresPermission]
        required_permission = PUBLIC                      # every method
        # or: required_permission = {"GET": PUBLIC, "POST": AUTHENTICATED}

A declaration is a catalogue key or one of two sentinels:

- ``PUBLIC`` — anyone, signed in or not (CSRF token, invitation preview);
- ``AUTHENTICATED`` — any signed-in user; the view or its service checks the objects itself
  (the user's own memberships, creating a practice, invitation services).

Checks by the key's scope:

- **organisation** — needs the active organisation (``/o/<org>/`` routes; else 404) the user can
  access (else 404 — never reveals that it exists), then ``has_perm``; missing permission →
  ``403`` ``permission.denied`` naming what is not allowed;
- **practice** — needs the acting practice (else 404), then ``has_practice_perm``;
- **platform** — ``has_platform_perm``.

``HEAD`` follows ``GET``; ``OPTIONS`` follows ``GET`` or else needs a signed-in user.
An undeclared method is refused (``403``) — the system check makes that a start-up error.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.access import can_access
from numo9.tenancy.context import acting_practice, current_org

from .catalogue import Scope, catalogue
from .resolver import has_perm, has_platform_perm, has_practice_perm

if TYPE_CHECKING:  # rest_framework.views loads this module through DEFAULT_PERMISSION_CLASSES
    from rest_framework.views import APIView

logger = logging.getLogger("numo9.rbac")

PUBLIC = "@public"
AUTHENTICATED = "@authenticated"
SENTINELS = frozenset({PUBLIC, AUTHENTICATED})

ATTRIBUTE = "required_permission"

F = TypeVar("F", bound=Callable[..., Any])


def requires_permission(key: str) -> Callable[[F], F]:
    """Declare the permission a view method needs (validated by the system check)."""

    def decorate(handler: F) -> F:
        setattr(handler, ATTRIBUTE, key)
        return handler

    return decorate


def declared_permission(view_class: type, method: str) -> str | None:
    """The declaration for an HTTP method of a view class, or None when there is none."""
    method = method.upper()
    if method == "HEAD":
        method = "GET"
    handler = getattr(view_class, method.lower(), None)
    on_handler = getattr(handler, ATTRIBUTE, None)
    if isinstance(on_handler, str):
        return on_handler
    on_class = getattr(view_class, ATTRIBUTE, None)
    if isinstance(on_class, str):
        return on_class
    if isinstance(on_class, dict):
        value = on_class.get(method)
        return value if isinstance(value, str) else None
    return None


def _action_text(key: str) -> str:
    label = str(catalogue.get(key).label)
    return label[:1].lower() + label[1:]


class RequiresPermission(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        method = (request.method or "GET").upper()
        key = declared_permission(type(view), method)
        if key is None and method == "OPTIONS":
            key = declared_permission(type(view), "GET") or AUTHENTICATED
        if key is None:
            logger.error(
                "No required_permission for %s %s — refused.", method, type(view).__qualname__
            )
            return False
        if key == PUBLIC:
            return True
        user = request.user
        if not (user and user.is_authenticated):
            raise NotAuthenticated
        if key == AUTHENTICATED:
            return True
        scope = catalogue.get(key).scope
        if scope == Scope.ORGANISATION:
            organisation = current_org()
            if organisation is None or not can_access(user, organisation):
                raise NotFound  # same answer as an unknown organisation (A-01-T06)
            allowed = has_perm(user, organisation, key)
        elif scope == Scope.PRACTICE:
            practice = acting_practice()
            if practice is None:
                raise NotFound
            allowed = has_practice_perm(user, practice, key)
        else:
            allowed = has_platform_perm(user, key)
        if not allowed:
            raise api_error(errors.PERMISSION_DENIED, action=_action_text(key))
        return True
