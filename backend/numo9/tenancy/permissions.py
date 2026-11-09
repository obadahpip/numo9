"""DRF permission for organisation-scoped endpoints (A-01-T06).

``IsOrgMemberOrAssigned`` lets a request through only when

- the user is authenticated (otherwise DRF's usual 401/403 — the same for every organisation id),
- the request has an active organisation (``TenantContextMiddleware``, A-01-T03), and
- the access resolver allows the user in that organisation (``can_access``, A-01-T05).

Every refusal about *which* organisation or object is a ``404 Not Found``, never ``403``: an
organisation the user may not see, an unknown organisation (middleware) and an object of another
organisation all answer the same, so responses never reveal that something exists.

The object-level check is defence in depth: ``OrgScopedManager`` already limits querysets to the
active organisation, and this check also catches objects loaded any other way.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .access import can_access
from .context import current_org
from .models import Organisation


class IsOrgMemberOrAssigned(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        organisation = current_org()
        if organisation is None or not can_access(request.user, organisation):
            raise NotFound
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        organisation = current_org()
        if isinstance(obj, Organisation):
            owner_id = obj.pk
        elif hasattr(obj, "organisation_id"):
            owner_id = obj.organisation_id
        else:
            raise ImproperlyConfigured(
                f"IsOrgMemberOrAssigned used on {type(obj).__name__}, which has no organisation."
            )
        if organisation is None or owner_id != organisation.pk:
            raise NotFound
        return True
