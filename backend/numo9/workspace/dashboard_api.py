"""``GET /api/v1/practice/dashboard?practice=…&scope=mine|all`` (V-04-T06): the practice home.

Every widget the user sees (``dashboard.answer_all``) with its own ``status``: ``ok`` with its
figures, or ``error`` when its provider failed — one failing provider never fails the response
(the card shows its error with a retry; the rest of the page loads). ``scope``: ``mine`` (the
organisations the user is assigned to) or ``all`` (every client the user may see) — ``all`` for
practice-wide roles only (the default for them); everyone else always gets ``mine``.
Members of the practice with ``practice.directory.view``; anyone else 404 / 403 as the directory.
"""

from __future__ import annotations

from typing import Any, cast

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.tenancy.access import PRACTICE_WIDE_ROLES
from numo9.tenancy.models import PracticeMember

from .api import _require_directory, bad_parameter, resolve_practice
from .dashboard import ALL, KINDS, MINE, DashboardContext, answer_all


class WidgetSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    kind = serializers.ChoiceField(choices=[(k, k) for k in KINDS])
    status = serializers.ChoiceField(choices=[("ok", "ok"), ("error", "error")])
    count = serializers.IntegerField(allow_null=True, help_text="Count widgets; 0 renders 0")
    filters = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        allow_null=True,
        help_text="Directory filter parameters listing exactly the organisations counted",
    )
    href = serializers.CharField(allow_blank=True, help_text="Another drill-down page")
    hidden = serializers.BooleanField(help_text="Hidden by the user (shown when customising)")
    items = serializers.ListField(child=serializers.DictField(), help_text="List/workload rows")


class LayoutSerializer(serializers.Serializer[Any]):
    order = serializers.ListField(
        child=serializers.CharField(max_length=64), max_length=50, help_text="Widget keys, in order"
    )
    hidden = serializers.ListField(
        child=serializers.CharField(max_length=64), max_length=50, help_text="Hidden widget keys"
    )


class DashboardSerializer(serializers.Serializer[Any]):
    practice = serializers.DictField()
    scope = serializers.ChoiceField(choices=[(MINE, MINE), (ALL, ALL)])
    scopes = serializers.ListField(child=serializers.CharField(), help_text="Scopes offered")
    layout = LayoutSerializer(help_text="The user's own order and hidden widgets (V-04-T09)")
    widgets = WidgetSerializer(
        many=True, help_text="In the user's order; hidden ones last, with hidden=true"
    )


def apply_layout(
    widgets: list[dict[str, Any]], order: list[str], hidden: list[str]
) -> list[dict[str, Any]]:
    """The widgets in the user's order (unknown keys ignored, new widgets after the ordered ones,
    in their default order), each marked ``hidden``; hidden ones are kept for the customise view."""
    rank = {key: index for index, key in enumerate(order)}
    ordered = sorted(
        enumerate(widgets), key=lambda pair: (rank.get(pair[1]["key"], len(rank)), pair[0])
    )
    return [{**widget, "hidden": widget["key"] in set(hidden)} for _i, widget in ordered]


def layout_of(ctx: DashboardContext) -> dict[str, list[str]]:
    from .models import DashboardLayout

    row = DashboardLayout.objects.filter(user=ctx.user, practice=ctx.practice).first()
    if row is None:
        return {"order": [], "hidden": []}
    return {"order": list(row.order or []), "hidden": list(row.hidden or [])}


def dashboard_context(request: Request) -> DashboardContext:
    practice = resolve_practice(request)
    _require_directory(request, practice)
    member = PracticeMember.objects.get(practice=practice, user=cast(User, request.user))
    wide = member.role in PRACTICE_WIDE_ROLES
    scope = request.query_params.get("scope") or (ALL if wide else MINE)
    if scope not in (MINE, ALL):
        raise bad_parameter(_bad_scope(), "scope", name="scope", value=scope[:100])
    if not wide:
        scope = MINE
    return DashboardContext(user=request.user, practice=practice, member=member, scope=scope)


def _bad_scope() -> Any:
    from numo9.i18n import errors

    return errors.WORKSPACE_BAD_FILTER


class PracticeDashboardView(APIView):
    required_feature = CORE  # the Practice product is free: never gated

    @requires_permission(AUTHENTICATED)  # membership and practice.directory.view checked here
    @extend_schema(
        operation_id="practice_dashboard",
        summary="Practice home: every widget with its figures, or its own error",
        parameters=[
            OpenApiParameter("practice", OpenApiTypes.UUID, description="The practice"),
            OpenApiParameter("scope", OpenApiTypes.STR, enum=[MINE, ALL]),
        ],
        responses=DashboardSerializer,
    )
    def get(self, request: Request) -> Response:
        ctx = dashboard_context(request)
        wide = ctx.practice_wide
        layout = layout_of(ctx)
        body = {
            "practice": {"id": str(ctx.practice.public_id), "name": ctx.practice.name},
            "scope": ctx.scope,
            "scopes": [MINE, ALL] if wide else [MINE],
            "layout": layout,
            "widgets": apply_layout(answer_all(ctx), layout["order"], layout["hidden"]),
        }
        return Response(DashboardSerializer(body).data)


class DashboardLayoutView(APIView):
    """``PUT practice/dashboard/layout?practice=…`` (V-04-T09): save the user's own order and
    hidden widgets for this practice (only the widgets they can see are kept)."""

    required_feature = CORE

    @requires_permission(AUTHENTICATED)
    @extend_schema(
        operation_id="practice_dashboard_layout",
        summary="Save my practice home layout: widget order and hidden widgets",
        parameters=[OpenApiParameter("practice", OpenApiTypes.UUID, description="The practice")],
        request=LayoutSerializer,
        responses=LayoutSerializer,
    )
    def put(self, request: Request) -> Response:
        from .dashboard import widgets
        from .models import DashboardLayout

        ctx = dashboard_context(request)
        payload = LayoutSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        known = [w.key for w in widgets() if w.shown_to(ctx)]
        order = list(dict.fromkeys(k for k in payload.validated_data["order"] if k in known))
        hidden = sorted({k for k in payload.validated_data["hidden"] if k in known})
        DashboardLayout.objects.update_or_create(
            user=ctx.user, practice=ctx.practice, defaults={"order": order, "hidden": hidden}
        )
        return Response(LayoutSerializer({"order": order, "hidden": hidden}).data)
