"""Demo API (U-07-T10…T12), under /api/v1/.

- ``POST o/<org>/demo/convert`` {name} — start my free trial: a new empty organisation, the demo
  deleted (owner of the demo; a real account);
- ``POST o/<org>/demo/reset`` — back to the sample data (owner);
- ``GET  o/<org>/demo/outbox`` — the emails the demo would have sent (any member);
- ``POST demo`` — open a demo (U-07-T11; signed in or anonymous).

A non-demo organisation answers 409 ``demo.not_a_demo``.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth import login
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.entitlements.trials import TrialAlreadyUsed
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import PUBLIC, requires_permission
from numo9.tenancy.api import trial_refused
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole

from .cloning import create_demo
from .convert import NotADemo, SignUpFirst, convert_to_trial
from .exclusions import is_demo
from .models import DemoOutbox
from .reset import reset_demo
from .users import make_demo_user

CLOSE = "organisation.close"
VIEW = "organisation.profile.view"


def _demo() -> Organisation:
    organisation = current_org()
    if organisation is None or not is_demo(organisation):
        raise api_error(errors.DEMO_NOT_A_DEMO)
    return organisation


class ConvertSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200)


class DemoConvertView(APIView):
    required_feature = CORE  # the demo itself, not a product feature
    queryset = DemoOutbox._base_manager.none()  # tenant sweep: organisation-scoped

    @requires_permission(CLOSE)
    @extend_schema(
        operation_id="demo_convert",
        summary="Start my free trial: a new empty organisation; the demo is deleted",
        request=ConvertSerializer,
        responses={
            201: inline_serializer(
                "DemoConverted", {"id": serializers.UUIDField(), "name": serializers.CharField()}
            )
        },
    )
    def post(self, request: Request, org: Any) -> Response:
        demo = _demo()
        incoming = ConvertSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        try:
            organisation = convert_to_trial(
                demo, request.user, name=incoming.validated_data["name"]
            )
        except NotADemo:
            raise api_error(errors.DEMO_NOT_A_DEMO) from None
        except SignUpFirst:
            raise api_error(errors.DEMO_SIGN_UP_FIRST) from None
        except TrialAlreadyUsed as refused:
            raise trial_refused(request, refused) from None
        return Response(
            {"id": str(organisation.public_id), "name": organisation.name},
            status=status.HTTP_201_CREATED,
        )


class DemoResetView(APIView):
    required_feature = CORE  # the demo itself, not a product feature
    queryset = DemoOutbox._base_manager.none()  # tenant sweep: organisation-scoped

    @requires_permission(CLOSE)
    @extend_schema(
        operation_id="demo_reset",
        summary="Reset the demo to its sample data",
        request=None,
        responses={
            200: inline_serializer("DemoReset", {"seed_version": serializers.IntegerField()})
        },
    )
    def post(self, request: Request, org: Any) -> Response:
        demo = _demo()
        reset_demo(demo)
        demo.refresh_from_db()
        return Response({"seed_version": demo.demo_seed_version})


class DemoOutboxItemSerializer(serializers.ModelSerializer[DemoOutbox]):
    id = serializers.IntegerField(source="pk")

    class Meta:
        model = DemoOutbox
        fields = ("id", "to_email", "subject", "text_body", "kind", "created_at")


class DemoOutboxView(APIView):
    required_feature = CORE  # the demo itself, not a product feature
    queryset = DemoOutbox._base_manager.none()  # tenant sweep: rows of DemoOutbox

    @requires_permission(VIEW)
    @extend_schema(
        operation_id="demo_outbox",
        summary="Emails the demo would have sent (never sent), newest first",
        responses={
            200: inline_serializer(
                "DemoOutboxPage", {"results": DemoOutboxItemSerializer(many=True)}
            )
        },
    )
    def get(self, request: Request, org: Any) -> Response:
        demo = _demo()
        rows = DemoOutbox.objects.filter(organisation=demo).order_by("-created_at", "-pk")[:100]
        return Response({"results": DemoOutboxItemSerializer(rows, many=True).data})


#: Anonymous demo sessions last a working day; the account can't sign in again (no password).
ANONYMOUS_SESSION_SECONDS = 8 * 60 * 60
#: Demos one address may open anonymously per hour (a creation spike from one client is abuse).
ANONYMOUS_PER_HOUR = int(getattr(settings, "NUMO9_DEMO_OPEN_PER_HOUR", 10))


def _client_address(request: Request) -> str:
    return str(request.META.get("REMOTE_ADDR", ""))


def _rate_limited(request: Request) -> bool:
    key = f"demo:open:{_client_address(request)}"
    added = cache.add(key, 1, 60 * 60)
    if added:
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 60 * 60)
        return False
    return count > ANONYMOUS_PER_HOUR


class DemoOpenView(APIView):
    """Open a demo (U-07-T11): from the website (anonymous) or for a signed-in accountant."""

    @requires_permission(PUBLIC)  # the website's "Try the demo": anyone, signed in or not
    @extend_schema(
        operation_id="demo_open",
        summary="Open a demo organisation (anonymous visitors get a limited demo session)",
        request=None,
        responses={
            201: inline_serializer(
                "DemoOpened",
                {
                    "organisation": serializers.UUIDField(),
                    "name": serializers.CharField(),
                    "anonymous": serializers.BooleanField(),
                },
            )
        },
    )
    def post(self, request: Request) -> Response:
        # CSRF even for anonymous callers: a cross-site form must not sign a visitor into a demo.
        SessionAuthentication().enforce_csrf(request)
        anonymous = not request.user.is_authenticated
        if anonymous and _rate_limited(request):
            raise api_error(errors.DEMO_TOO_MANY)
        demo = create_demo()
        user: User = make_demo_user() if anonymous else request.user  # type: ignore[assignment]
        OrganisationMember.objects.create(organisation=demo, user=user, role=OrganisationRole.OWNER)
        if anonymous:
            login(request._request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
            request._request.session.set_expiry(ANONYMOUS_SESSION_SECONDS)
        return Response(
            {"organisation": str(demo.public_id), "name": demo.name, "anonymous": anonymous},
            status=status.HTTP_201_CREATED,
        )
