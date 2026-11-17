"""Platform console API (U-06), under ``/api/v1/platform/``.

``GET /api/v1/platform/me`` (U-06-T02) — the console's route guard: who the signed-in user is in
the console and which platform permissions they hold. Anyone without a platform role gets
**404** — the console doesn't exist for them (no leak); a platform user without two-factor
authentication gets ``403 auth.two_factor_required`` (the console needs 2FA, whatever the role).
"""

from __future__ import annotations

from typing import Any, cast

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.accounts.twofactor_policy import has_two_factor
from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.rbac.permissions import CONSOLE_VIEW
from numo9.rbac.resolver import platform_permissions
from numo9.tenancy.models import OrganisationStatus


def platform_user(request: Request) -> tuple[User, frozenset[str]]:
    """The signed-in platform user and their permissions; 404 for anyone else, 403 without 2FA."""
    user = cast(User, request.user)
    permissions = platform_permissions(user)
    if not permissions:
        raise NotFound
    if not has_two_factor(user):
        raise api_error(errors.AUTH_TWO_FACTOR_REQUIRED)
    return user, permissions


class PlatformMeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())


class PlatformMeView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # any platform permission (checked here; else 404)
    @extend_schema(
        operation_id="platform_me",
        summary="The console's route guard: the signed-in user's platform permissions",
        responses=PlatformMeSerializer,
    )
    def get(self, request: Request) -> Response:
        user, permissions = platform_user(request)
        return Response(
            {
                "id": user.public_id,
                "name": user.name,
                "email": user.email,
                "permissions": sorted(permissions),
            }
        )


# ---- practices and organisations (U-06-T03) ----------------------------------------------------


def _listing(request: Request, build: Any) -> Response:
    from .directory import BadFilter

    try:
        return Response(build(request.query_params))
    except BadFilter as bad:
        error = api_error(errors.PLATFORM_BAD_FILTER, name=bad.name, value=bad.value[:100])
        error.extra = {"field": bad.name}
        raise error from None


class PlatformOrganisationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=OrganisationStatus.choices)
    is_demo = serializers.BooleanField(help_text="Demo organisations are left out of metrics.")
    package = serializers.CharField(help_text="Current package code; empty when none.")
    subscription_status = serializers.CharField()
    province = serializers.CharField()
    created_at = serializers.DateTimeField()


class PlatformOrganisationPageSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    pages = serializers.IntegerField()
    results = PlatformOrganisationSerializer(many=True)


class PlatformPracticeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    staff_count = serializers.IntegerField()
    client_count = serializers.IntegerField(help_text="Organisations it actively serves.")
    created_at = serializers.DateTimeField()


class PlatformPracticePageSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    pages = serializers.IntegerField()
    results = PlatformPracticeSerializer(many=True)


_PAGING = [
    OpenApiParameter("q", OpenApiTypes.STR, description="Name contains"),
    OpenApiParameter("created_from", OpenApiTypes.DATE),
    OpenApiParameter("created_to", OpenApiTypes.DATE),
    OpenApiParameter("page", OpenApiTypes.INT),
    OpenApiParameter("page_size", OpenApiTypes.INT, description="1–200"),
]


class PlatformOrganisationListView(APIView):
    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_organisations_list",
        summary="Every organisation, with filters (status, package, province, created)",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, many=True, enum=OrganisationStatus.values),
            OpenApiParameter("package", OpenApiTypes.STR, many=True, description="Code or none"),
            OpenApiParameter("province", OpenApiTypes.STR, many=True),
            *_PAGING,
        ],
        responses=PlatformOrganisationPageSerializer,
    )
    def get(self, request: Request) -> Response:
        from .directory import organisations

        return _listing(request, organisations)


class PlatformPracticeListView(APIView):
    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_practices_list",
        summary="Every practice, with staff and client counts",
        parameters=_PAGING,
        responses=PlatformPracticePageSerializer,
    )
    def get(self, request: Request) -> Response:
        from .directory import practices

        return _listing(request, practices)
