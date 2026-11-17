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
from numo9.rbac.permissions import CONSOLE_VIEW, IMPERSONATE
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


class PlatformOrganisationDetailView(APIView):
    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_organisations_detail",
        summary="One organisation: subscription timeline, users, practices, recent audit events",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request, org_id: Any) -> Response:
        from numo9.tenancy.models import Organisation

        from .directory import organisation_detail

        organisation = Organisation.objects.filter(public_id=org_id).first()
        if organisation is None:
            raise NotFound
        return Response(organisation_detail(organisation))


# ---- metrics (U-06-T06) ------------------------------------------------------------------------


class PlatformMetricsCurrentSerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    mrr_cents = serializers.IntegerField()
    active = serializers.IntegerField()
    trials = serializers.IntegerField()
    conversion_rate = serializers.DecimalField(max_digits=6, decimal_places=4, allow_null=True)
    churn_rate = serializers.DecimalField(max_digits=6, decimal_places=4, allow_null=True)
    converted = serializers.IntegerField()
    trials_ended = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    active_at_start = serializers.IntegerField()


class PlatformMetricPointSerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    mrr_cents = serializers.IntegerField()
    active = serializers.IntegerField()
    trials = serializers.IntegerField()
    conversion_rate = serializers.DecimalField(max_digits=6, decimal_places=4, allow_null=True)
    churn_rate = serializers.DecimalField(max_digits=6, decimal_places=4, allow_null=True)


class PlatformMetricsSerializer(serializers.Serializer[Any]):
    current = PlatformMetricsCurrentSerializer()
    history = PlatformMetricPointSerializer(many=True)


class PlatformMetricsView(APIView):
    """Today's figures (computed live) and the daily snapshots of the last ``days`` days."""

    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_metrics",
        summary="KPI figures (live) and their daily history; demo organisations excluded",
        parameters=[OpenApiParameter("days", OpenApiTypes.INT, description="7–366, default 90")],
        responses=PlatformMetricsSerializer,
    )
    def get(self, request: Request) -> Response:
        from .metrics import compute, history

        raw = request.query_params.get("days", "90")
        if not raw.isdigit() or not 7 <= int(raw) <= 366:
            error = api_error(errors.PLATFORM_BAD_FILTER, name="days", value=raw[:100])
            error.extra = {"field": "days"}
            raise error
        current = compute()
        data = {"current": current.as_dict(), "history": history(current, int(raw))}
        return Response(PlatformMetricsSerializer(data).data)


class PlatformMetricDrillDownView(APIView):
    """The organisations a tile counts (``active``, ``mrr``, ``trials``): the tile's number is
    always this list's ``count``."""

    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_metric_drill_down",
        summary="The organisations counted by one KPI tile",
        parameters=_PAGING[3:],
        responses=PlatformOrganisationPageSerializer,
    )
    def get(self, request: Request, metric: str) -> Response:
        from .directory import page_of_organisations
        from .metrics import drill_down

        try:
            rows = drill_down(metric)
        except KeyError:
            raise NotFound from None
        return _listing(request, lambda params: page_of_organisations(rows, params))


# ---- impersonation (U-06-T09) ------------------------------------------------------------------

_REFUSALS = {
    "reason_required": errors.IMPERSONATION_REASON_REQUIRED,
    "reason_too_long": errors.IMPERSONATION_REASON_TOO_LONG,
    "bad_duration": errors.IMPERSONATION_BAD_DURATION,
    "not_self": errors.IMPERSONATION_NOT_SELF,
    "not_a_member": errors.IMPERSONATION_NOT_A_MEMBER,
    "platform_user": errors.IMPERSONATION_PLATFORM_USER,
    "already_open": errors.IMPERSONATION_ALREADY_OPEN,
}


class ImpersonationStartSerializer(serializers.Serializer[Any]):
    organisation = serializers.UUIDField()
    user = serializers.UUIDField()
    reason = serializers.CharField(allow_blank=True, trim_whitespace=False)
    minutes = serializers.IntegerField(required=False, default=30)


class ImpersonationPersonSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.CharField()


class ImpersonationOrganisationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class ImpersonationSessionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    actor = ImpersonationPersonSerializer()
    user = ImpersonationPersonSerializer()
    organisation = ImpersonationOrganisationSerializer()
    reason = serializers.CharField()
    started_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    end_reason = serializers.CharField()


class ImpersonationCurrentSerializer(serializers.Serializer[Any]):
    session = ImpersonationSessionSerializer(allow_null=True)
    ended = ImpersonationSessionSerializer(
        allow_null=True, help_text="A session that just reached its time limit."
    )


def session_data(session: Any) -> dict[str, Any]:
    def person(user: Any) -> dict[str, Any]:
        return {"id": user.public_id, "name": user.name, "email": user.email}

    return {
        "id": session.public_id,
        "actor": person(session.actor),
        "user": person(session.target_user),
        "organisation": {"id": session.organisation.public_id, "name": session.organisation.name},
        "reason": session.reason,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "ended_at": session.ended_at,
        "end_reason": session.end_reason,
    }


class ImpersonationStartView(APIView):
    """Start signing in as a user of one organisation (``platform.impersonate``): a reason and a
    duration (default 30 minutes, at most 2 hours). From the next request on, the browser acts as
    that user inside that organisation, until the session ends or expires."""

    required_feature = CORE

    @requires_permission(IMPERSONATE.key)
    @extend_schema(
        operation_id="platform_impersonation_start",
        summary="Start a time-boxed, audited session as a user of one organisation",
        request=ImpersonationStartSerializer,
        responses={201: ImpersonationSessionSerializer},
    )
    def post(self, request: Request) -> Response:
        from numo9.accounts.models import User
        from numo9.tenancy.models import Organisation

        from . import impersonation
        from .middleware import SESSION_KEY

        actor, _permissions = platform_user(request)
        body = ImpersonationStartSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        organisation = Organisation.objects.filter(public_id=body.validated_data["organisation"])
        target = User.objects.filter(public_id=body.validated_data["user"]).first()
        if not organisation.exists() or target is None:
            raise NotFound
        try:
            session = impersonation.start(
                actor,
                target,
                organisation.get(),
                body.validated_data["reason"],
                body.validated_data["minutes"],
            )
        except impersonation.ImpersonationRefused as refused:
            raise api_error(_REFUSALS[refused.code], **refused.params) from None
        request.session[SESSION_KEY] = str(session.public_id)
        return Response(session_data(session), status=201)


class ImpersonationCurrentView(APIView):
    """The session the browser is in (``session``), or the one that just expired (``ended``)."""

    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # the browser's own session; nothing else is shown
    @extend_schema(
        operation_id="platform_impersonation_current",
        summary="The impersonation session this browser is in, if any",
        responses=ImpersonationCurrentSerializer,
    )
    def get(self, request: Request) -> Response:
        session = getattr(request._request, "impersonation", None)
        ended = getattr(request._request, "impersonation_ended", None)
        return Response(
            {
                "session": session_data(session) if session else None,
                "ended": session_data(ended) if ended else None,
            }
        )


class ImpersonationEndView(APIView):
    """End the browser's session: the next request is the staff member again."""

    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # only the browser's own session can be ended
    @extend_schema(
        operation_id="platform_impersonation_end",
        summary="End the impersonation session this browser is in",
        request=None,
        responses=ImpersonationCurrentSerializer,
    )
    def post(self, request: Request) -> Response:
        from .middleware import SESSION_KEY
        from .models import ImpersonationEndReason

        session = getattr(request._request, "impersonation", None)
        ended = getattr(request._request, "impersonation_ended", None)
        if session is not None:
            session.end(ImpersonationEndReason.ENDED)
            ended = session
        request.session.pop(SESSION_KEY, None)
        return Response({"session": None, "ended": session_data(ended) if ended else None})
