"""Test-only views for feature-key declarations (U-01-T07)."""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import RequiresPermission, requires_permission
from numo9.tenancy.permissions import IsOrgMemberOrAssigned


class CanaryUndeclared(APIView):
    """A business endpoint (organisation route) that forgot its feature key."""

    @requires_permission("organisation.profile.view")
    def get(self, request: Request, org: str) -> Response:
        return Response({"ok": True})


class CanaryUnknownKey(APIView):
    """A key that is not in the catalogue (typo / missing data migration)."""

    @requires_permission("organisation.profile.view")
    @requires_feature("accounting.sales_invoicez.read")
    def get(self, request: Request, org: str) -> Response:
        return Response({"ok": True})


class CanaryNotEnforced(APIView):
    """Declares a key but sets permission_classes without RequiresFeature."""

    permission_classes = [IsOrgMemberOrAssigned, RequiresPermission]

    @requires_permission("organisation.profile.view")
    @requires_feature("accounting.sales_invoices.read")
    def get(self, request: Request, org: str) -> Response:
        return Response({"ok": True})


class DeclaredOutsideBusiness(APIView):
    """Not a business route: no key needed, but a declared key must still exist."""

    @requires_permission("organisation.profile.view")
    @requires_feature("tax.nothing_here.read")
    def get(self, request: Request) -> Response:
        return Response({"ok": True})
