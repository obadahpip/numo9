"""Feature-key declarations for API views (U-01-T05).

Every gated API method says which feature key it needs; ``RequiresFeature`` asks the entitlement
resolver (``entitlements.py`` — U-03 engine, a stub that allows everything until then) and
answers **402** ``entitlement.feature_not_in_package`` naming the product when the
organisation's package doesn't include it. ``manage.py check_feature_keys`` (U-01-T07) fails
CI when a business endpoint declares nothing or a key that is not in the catalogue.

    class InvoiceList(APIView):
        @requires_permission("sales.invoice.view")
        @requires_feature("accounting.sales_invoices.read")
        def get(self, request, org): ...

    class RoleList(APIView):
        required_feature = CORE                 # every method: part of every organisation
        # or: required_feature = {"GET": "...read", "POST": "...write"}

A declaration is a catalogue key (``<product>.<area>.<action>``) or ``CORE`` — sign-in,
tenancy, users and roles, approval limits, audit, jobs and settings belong to every organisation
and are never gated (U-03 rule; docs/dev/feature-keys.md).

``RequiresFeature`` is in ``DEFAULT_PERMISSION_CLASSES`` after ``RequiresPermission``: a foreign
organisation answers 404 and a missing permission 403 before any 402. ``HEAD`` and ``OPTIONS``
follow ``GET``. An undeclared method is not refused at runtime — the CI check refuses it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.context import current_org

from .entitlements import get_resolver
from .models import split_key
from .texts import product_name

if TYPE_CHECKING:
    from rest_framework.views import APIView

#: Not a feature: part of every organisation, never gated.
CORE = "@core"
ATTRIBUTE = "required_feature"

F = TypeVar("F", bound=Callable[..., Any])


def requires_feature(key: str) -> Callable[[F], F]:
    """Declare the feature key a view method needs (checked by ``check_feature_keys``)."""

    def decorate(handler: F) -> F:
        setattr(handler, ATTRIBUTE, key)
        return handler

    return decorate


def declared_feature(view_class: type, method: str) -> str | None:
    """The feature declaration for an HTTP method (or ViewSet action), or None."""
    method = method.upper()
    if method in ("HEAD", "OPTIONS"):
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


def product_of(key: str) -> str:
    try:
        return split_key(key)[0]
    except ValueError:
        return key.split(".", 1)[0]


class RequiresFeature(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        method = (request.method or "GET").upper()
        if method not in view.allowed_methods:
            return True  # DRF answers 405
        key = declared_feature(type(view), method)
        if key is None or key == CORE:
            return True
        if get_resolver().allows(current_org(), key):
            return True
        product = product_of(key)
        error = api_error(errors.FEATURE_NOT_IN_PACKAGE, product=product_name(product))
        # U-03-T07 adds the packages that include the product.
        error.extra = {"feature": key, "product": product}
        raise error
