"""Read-only organisations in the API (U-03-T08; ADR-0004).

``ReadOnlyGuard`` (``DEFAULT_PERMISSION_CLASSES``, after ``RequiresPermission`` and before
``RequiresFeature``): when the active organisation's entitlements are in ``read_only`` mode — the
grace period after a failed payment ended, a trial ended unpaid, the subscription was cancelled —
every unsafe method (POST, PUT, PATCH, DELETE) answers **402**
``entitlement.organisation_read_only`` with ``reason`` and ``since``:

    {"code": "entitlement.organisation_read_only", "detail": "…", "reason": "payment_failed",
     "since": "2026-11-20T05:00:00+00:00"}

Reading stays open (every ``GET``), and so do the methods marked ``allowed_when_read_only`` —
billing (paying makes the organisation writable again, U-04) and exports (a cancelled organisation
takes its data with it):

    class ExportView(APIView):
        @allowed_when_read_only
        def post(self, request, org): ...

    class BillingView(APIView):
        allowed_when_read_only = True        # every method

The guard answers only to people who can open the organisation (an outsider gets the 404 of the
other checks, never the organisation's billing state).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.access import can_access
from numo9.tenancy.context import current_org

from .cache import entitlements_for

if TYPE_CHECKING:
    from rest_framework.views import APIView

ATTRIBUTE = "allowed_when_read_only"


def allowed_when_read_only[F: Callable[..., Any]](handler: F) -> F:
    """Mark a view method usable while the organisation is read-only (billing, exports)."""
    setattr(handler, ATTRIBUTE, True)
    return handler


def is_allowed_when_read_only(view_class: type, method: str) -> bool:
    handler = getattr(view_class, method.lower(), None)
    if getattr(handler, ATTRIBUTE, False) is True:
        return True
    return getattr(view_class, ATTRIBUTE, False) is True


class ReadOnlyGuard(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        method = (request.method or "GET").upper()
        if method in SAFE_METHODS or method not in view.allowed_methods:
            return True
        organisation = current_org()
        if organisation is None:
            return True
        if is_allowed_when_read_only(type(view), method):
            return True
        user = request.user
        if not (user and user.is_authenticated and can_access(user, organisation)):
            return True  # the other checks answer (404/401); never reveal the billing state
        answer = entitlements_for(organisation)
        if not answer.is_read_only:
            return True
        error = api_error(errors.ORGANISATION_READ_ONLY)
        error.extra = {
            "reason": answer.reason,
            "since": answer.since.isoformat() if answer.since else None,
        }
        raise error
