"""CSRF token for the web app (S-03-T01).

The CSRF cookie is HttpOnly, so browser JavaScript cannot read it. The web app asks for the
token here once per session and sends it back in the ``X-CSRFToken`` header on unsafe requests;
Django checks it against the cookie (double submit) and the Origin/Referer against
``CSRF_TRUSTED_ORIGINS``.
"""

from __future__ import annotations

from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.rbac.drf import PUBLIC, RequiresPermission


@method_decorator([ensure_csrf_cookie, never_cache], name="dispatch")
class CsrfTokenView(APIView):
    # AllowAny adds nothing to RequiresPermission (both must pass); it marks the OpenAPI
    # operation as open to signed-out callers.
    permission_classes = [RequiresPermission, AllowAny]
    required_permission = PUBLIC  # the web app needs the token before signing in
    authentication_classes: list[type] = []

    @extend_schema(
        responses=inline_serializer("CsrfToken", {"csrfToken": serializers.CharField()}),
        summary="CSRF token for unsafe requests (send as X-CSRFToken)",
    )
    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request)})
