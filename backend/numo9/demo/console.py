"""Demo manager in the platform console (U-06-T13), under ``/api/v1/platform/demos``.

- ``GET  platform/demos`` — the demo organisations open now (not templates, not purged): name,
  seed version, created, last activity, the day the inactivity purge takes it (``IDLE_DAYS`` after
  the last activity) and its members; the counts (open, purged within 7 days) and the templates
  by seed version; ``platform.console.view``.
- ``POST platform/demos/<id>/purge`` — purge one demo now (as the inactivity job does: data
  wiped, members removed, the row kept as a cancelled demo); ``platform.catalogue.manage``.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.rbac.drf import requires_permission
from numo9.rbac.permissions import CATALOGUE_MANAGE, CONSOLE_VIEW
from numo9.tenancy.models import Organisation, OrganisationStatus

from .models import DemoTemplate
from .purge import IDLE_DAYS, purge_demo
from .seeders import SEED_VERSION

SOON_DAYS = 7


def open_demos() -> Any:
    templates = DemoTemplate.objects.values("organisation_id")
    return (
        Organisation.objects.filter(is_demo=True, status=OrganisationStatus.DEMO)
        .exclude(pk__in=templates)
        .annotate(member_count=Count("members", distinct=True))
        .order_by("-created_at")
    )


def purge_on(organisation: Organisation) -> dt.date:
    last = organisation.last_active_at or organisation.created_at
    return timezone.localdate(last + dt.timedelta(days=IDLE_DAYS + 1))


def overview(now: dt.datetime | None = None) -> dict[str, Any]:
    today = timezone.localdate(now or timezone.now())
    demos = list(open_demos())
    rows = [
        {
            "id": d.public_id,
            "name": d.name,
            "seed_version": d.demo_seed_version,
            "created_at": d.created_at,
            "last_active_at": d.last_active_at,
            "purge_on": purge_on(d),
            "members": d.member_count,
        }
        for d in demos
    ]
    return {
        "seed_version": SEED_VERSION,
        "idle_days": IDLE_DAYS,
        "open": len(rows),
        "purge_soon": sum(1 for r in rows if r["purge_on"] <= today + dt.timedelta(SOON_DAYS)),
        "templates": [
            {"seed_version": t.seed_version, "built_at": t.built_at}
            for t in DemoTemplate.objects.order_by("-seed_version")
        ],
        "demos": rows,
    }


class DemoRowSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    seed_version = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    last_active_at = serializers.DateTimeField(allow_null=True)
    purge_on = serializers.DateField(help_text="The inactivity purge takes it on this day")
    members = serializers.IntegerField()


class DemoTemplateRowSerializer(serializers.Serializer[Any]):
    seed_version = serializers.IntegerField()
    built_at = serializers.DateTimeField()


class DemoOverviewSerializer(serializers.Serializer[Any]):
    seed_version = serializers.IntegerField(help_text="The seed new demos are built from")
    idle_days = serializers.IntegerField()
    open = serializers.IntegerField()
    purge_soon = serializers.IntegerField(help_text=f"Purged within {SOON_DAYS} days")
    templates = DemoTemplateRowSerializer(many=True)
    demos = DemoRowSerializer(many=True)


class DemoOverviewView(APIView):
    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_demos_overview",
        summary="Demo organisations open now, their purge day, and the templates",
        responses=DemoOverviewSerializer,
    )
    def get(self, request: Request) -> Response:
        return Response(DemoOverviewSerializer(overview()).data)


class DemoPurgeView(APIView):
    required_feature = CORE

    @requires_permission(CATALOGUE_MANAGE.key)
    @extend_schema(
        operation_id="platform_demos_purge",
        summary="Purge one demo organisation now (data wiped, members removed)",
        request=None,
        responses={204: None},
    )
    def post(self, request: Request, demo_id: Any) -> Response:
        demo = open_demos().filter(public_id=demo_id).first()
        if demo is None:
            raise NotFound(_("No open demo organisation with this id."))
        with transaction.atomic():
            purge_demo(demo)
        return Response(status=204)
