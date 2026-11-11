"""Test-only views for permission declarations (A-03-T05)."""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.rbac.drf import AUTHENTICATED, PUBLIC, RequiresPermission, requires_permission
from numo9.tenancy.permissions import IsOrgMemberOrAssigned


class OrgSettings(APIView):
    """Organisation-scoped: read with one permission, change with another."""

    permission_classes = [IsOrgMemberOrAssigned, RequiresPermission]

    @requires_permission("organisation.profile.view")
    def get(self, request: Request) -> Response:
        return Response({"ok": "read"})

    @requires_permission("organisation.settings.manage")
    def post(self, request: Request) -> Response:
        return Response({"ok": "changed"})


class ByClass(APIView):
    """Declarations on the class, per method."""

    required_permission = {"GET": PUBLIC, "POST": AUTHENTICATED}

    def get(self, request: Request) -> Response:
        return Response({"ok": "public"})

    def post(self, request: Request) -> Response:
        return Response({"ok": "signed in"})


class Console(APIView):
    @requires_permission("platform.console.view")
    def get(self, request: Request) -> Response:
        return Response({"ok": "console"})


class PracticeStaff(APIView):
    @requires_permission("practice.staff.view")
    def get(self, request: Request) -> Response:
        return Response({"ok": "staff"})


# ---- deliberately wrong (system check and runtime refusal) -------------------------------------


class Undeclared(APIView):
    @requires_permission("organisation.profile.view")
    def get(self, request: Request) -> Response:
        return Response({})

    def delete(self, request: Request) -> Response:  # no declaration
        return Response({"deleted": True})


class UnknownKey(APIView):
    @requires_permission("organisation.profile.veiw")
    def get(self, request: Request) -> Response:
        return Response({})


class NotEnforced(APIView):
    permission_classes = [IsAuthenticated]

    @requires_permission(AUTHENTICATED)
    def get(self, request: Request) -> Response:
        return Response({})


def view_path(cls: type[Any]) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"
