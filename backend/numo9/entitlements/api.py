"""Entitlements API (U-03-T09), under ``/api/v1/``.

- ``o/<org>/entitlements`` — GET what the organisation may use now, for the web app's bootstrap
  (the entitlement store, U-03-T10): mode, reason, since, package, products, read-only products,
  feature keys, product names and the packages that include each product. Everyone who can open
  the organisation — members and assigned practice staff, whatever their role: the app can't
  render without it — checked with ``can_access`` (404 otherwise, A-01-T06) rather than through a
  role's permission set, so a cached call skips the permission resolution; never gated (``CORE``)
  and readable while the organisation is read-only (a GET). Cached (``cache.py``): < 20 ms p95.
  ``viewer.can_change_package`` — the signed-in person is the organisation's owner (the locked
  panel's buttons: "See packages" for owners, "Ask the owner" for everyone else).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.tenancy.access import can_access
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole

from .presenter import entitlements_data
from .serializers import EntitlementsSerializer


class EntitlementsView(APIView):
    required_feature = CORE  # the answer itself is never gated

    @requires_permission(AUTHENTICATED)  # + can_access below: anyone who can open the org
    @extend_schema(
        operation_id="organisation_entitlements",
        summary="What the organisation may use now (web app bootstrap)",
        responses=EntitlementsSerializer,
    )
    def get(self, request: Request, org: object) -> Response:
        organisation = current_org()
        if organisation is None or not can_access(request.user, organisation):
            raise NotFound  # the same answer as an unknown organisation
        body = entitlements_data(organisation)
        body["time_zone"] = organisation.time_zone  # dates in the read-only banner
        body["viewer"] = {"can_change_package": can_change_package(request.user, organisation)}
        return Response(body)


def can_change_package(user: Any, organisation: Organisation) -> bool:
    """Only the organisation's owner buys or changes the package; accountants never do (their
    locked panel says "Ask the owner")."""
    return OrganisationMember.objects.filter(
        organisation=organisation, user=user, role=OrganisationRole.OWNER
    ).exists()
