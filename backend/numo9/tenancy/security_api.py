"""Practice security policy (A-02-T06): ``/api/v1/practice/security?practice=<id>``.

- GET — ``{"require_2fa_for_admins": bool}`` for any member of the practice;
- PATCH ``{"require_2fa_for_admins": true}`` — practice permission ``practice.settings.manage``
  (practice admins), else 403; audited (``tenancy.practice.security_changed``). Turning it on
  applies at the next request of each practice admin without two-factor authentication.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.audit.service import record
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.rbac.resolver import has_practice_perm
from numo9.workspace.api import resolve_practice

SETTINGS_MANAGE = "practice.settings.manage"


class PracticeSecuritySerializer(serializers.Serializer[Any]):
    require_2fa_for_admins = serializers.BooleanField()


class PracticeSecurityView(APIView):
    serializer_class = PracticeSecuritySerializer

    @requires_permission(AUTHENTICATED)  # a member of the practice (resolve_practice: else 404)
    @extend_schema(
        operation_id="practice_security_get",
        parameters=[OpenApiParameter("practice", OpenApiTypes.UUID)],
        responses=PracticeSecuritySerializer,
    )
    def get(self, request: Request) -> Response:
        practice = resolve_practice(request)
        return Response({"require_2fa_for_admins": practice.require_2fa_for_admins})

    @requires_permission(AUTHENTICATED)  # + practice.settings.manage, checked below
    @extend_schema(
        operation_id="practice_security_update",
        summary="Require two-factor authentication for the practice's admins",
        parameters=[OpenApiParameter("practice", OpenApiTypes.UUID)],
        request=PracticeSecuritySerializer,
        responses=PracticeSecuritySerializer,
    )
    def patch(self, request: Request) -> Response:
        practice = resolve_practice(request)
        if not has_practice_perm(request.user, practice, SETTINGS_MANAGE):
            raise api_error(
                errors.PRACTICE_PERMISSION_DENIED,
                action=_("change the practice's security settings"),
            )
        payload = PracticeSecuritySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        new = payload.validated_data["require_2fa_for_admins"]
        old = practice.require_2fa_for_admins
        if new != old:
            practice.require_2fa_for_admins = new
            practice.save(update_fields=["require_2fa_for_admins", "updated_at"])
            record(
                "tenancy.practice.security_changed",
                obj=practice,
                organisation=None,
                practice=practice,
                changes={"require_2fa_for_admins": [old, new]},
                actor=request.user,
            )
        return Response({"require_2fa_for_admins": new})
