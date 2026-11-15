"""Test-only views gated by the entitlement engine (U-03-T07, T08, T13)."""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE, requires_feature
from numo9.entitlements.drf import allowed_when_read_only
from numo9.rbac.drf import requires_permission

VIEW = "organisation.profile.view"
MANAGE = "organisation.settings.manage"


class PayRuns(APIView):
    """A Payroll screen: read with payroll.pay_runs.read, run with .write."""

    @requires_permission(VIEW)
    @requires_feature("payroll.pay_runs.read")
    def get(self, request: Request, org: str) -> Response:
        return Response({"ok": True})

    @requires_permission(MANAGE)
    @requires_feature("payroll.pay_runs.write")
    def post(self, request: Request, org: str) -> Response:
        return Response({"ok": True}, status=201)


class Feature(APIView):
    """One feature key for every method (the leak matrix builds one per key, T13)."""

    @requires_permission(VIEW)
    def get(self, request: Request, org: str) -> Response:
        return Response({"ok": True})

    @requires_permission(MANAGE)
    def post(self, request: Request, org: str) -> Response:
        return Response({"ok": True}, status=201)

    @classmethod
    def for_key(cls, key: str) -> type[APIView]:
        """A subclass declaring ``key`` for every method."""
        return type(f"Feature_{key.replace('.', '_')}", (cls,), {"required_feature": key})


class CoreSettings(APIView):
    """Part of every organisation (CORE): never gated, but read-only refuses its writes."""

    required_feature = CORE

    @requires_permission(VIEW)
    def get(self, request: Request, org: str) -> Response:
        return Response({"ok": True})

    @requires_permission(MANAGE)
    def post(self, request: Request, org: str) -> Response:
        return Response({"ok": True}, status=201)


class Export(APIView):
    """An export started with POST: allowed while read-only."""

    required_feature = CORE

    @requires_permission(VIEW)
    @allowed_when_read_only
    def post(self, request: Request, org: str) -> Response:
        return Response({"ok": True}, status=202)


class Billing(APIView):
    """Billing (U-04): every method allowed while read-only (paying makes it writable again)."""

    required_feature = CORE
    allowed_when_read_only = True

    @requires_permission(MANAGE)
    def post(self, request: Request, org: str) -> Response:
        return Response({"ok": True}, status=201)

    @requires_permission(MANAGE)
    def delete(self, request: Request, org: str) -> Response:
        return Response(status=204)
