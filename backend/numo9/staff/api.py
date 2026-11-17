"""Practice staff API (V-05), under ``/api/v1/practice/staff``.

``GET staff?practice=…`` (V-05-T02) — the practice's members and pending invitations with role,
organisations they can open, last sign-in and status (``active``, ``dormant``, ``suspended``,
``pending``). Practice-scoped: members of the practice with ``practice.directory.view`` (any
practice role); not a member → 404. Tenant-sweep exempt (``^api/v1/practice/``).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import AUTHENTICATED, checks_practice_permission, requires_permission
from numo9.rbac.resolver import has_practice_perm
from numo9.tenancy.models import Practice
from numo9.workspace.api import resolve_practice
from numo9.workspace.permissions import DIRECTORY_VIEW

PRACTICE_PARAM = OpenApiParameter("practice", OpenApiTypes.UUID)
STATUSES = [(s, s) for s in ("active", "dormant", "suspended", "pending")]


def practice_for(request: Request, permission: Any) -> Practice:
    given = request.data.get("practice") if isinstance(request.data, dict) else None
    practice = resolve_practice(request, str(given) if given else None)
    if not has_practice_perm(request.user, practice, permission.key):
        label = str(permission.label)
        raise api_error(errors.PERMISSION_DENIED, action=label[:1].lower() + label[1:])
    return practice


class StaffLineSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(help_text="The user's id; an invitation's id when pending")
    name = serializers.CharField()
    email = serializers.CharField()
    role = serializers.CharField()
    role_label = serializers.CharField()
    status = serializers.ChoiceField(choices=STATUSES)
    organisation_count = serializers.IntegerField()
    last_login = serializers.DateTimeField(allow_null=True)
    joined_at = serializers.DateTimeField(allow_null=True)
    suspended_at = serializers.DateTimeField(allow_null=True)
    dormant = serializers.BooleanField()
    invitation_expires_at = serializers.DateTimeField(allow_null=True)


class StaffListSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField()
    dormant_days = serializers.IntegerField()
    staff = StaffLineSerializer(many=True)


class StaffListView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_staff_list",
        summary="The practice's staff: role, organisations, last sign-in, status",
        parameters=[PRACTICE_PARAM],
        responses=StaffListSerializer,
    )
    def get(self, request: Request) -> Response:
        from .directory import staff_lines

        practice = practice_for(request, DIRECTORY_VIEW)
        return Response(
            {
                "practice": practice.public_id,
                "dormant_days": practice.dormant_days,
                "staff": staff_lines(practice),
            }
        )
