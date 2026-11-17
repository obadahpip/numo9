"""Platform console API (U-06), under ``/api/v1/platform/``.

``GET /api/v1/platform/me`` (U-06-T02) — the console's route guard: who the signed-in user is in
the console and which platform permissions they hold. Anyone without a platform role gets
**404** — the console doesn't exist for them (no leak); a platform user without two-factor
authentication gets ``403 auth.two_factor_required`` (the console needs 2FA, whatever the role).
"""

from __future__ import annotations

from typing import Any, cast

from drf_spectacular.utils import extend_schema
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
from numo9.rbac.resolver import platform_permissions


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
