"""Organisation settings API (A-05), under ``/api/v1/o/<org>/settings/``.

- ``settings/lock-dates/impact?module=gl&date=2026-03-31`` — GET what a lock at that date would
  leave not posted (A-05-T07): ``{"module", "date", "items": [{"module", "kind", "label",
  "count"}], "total"}``; permission ``organisation.settings.manage`` (it is asked before changing a
  lock).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .impact import impact
from .models import LockModule

VIEW = "organisation.profile.view"
MANAGE = "organisation.settings.manage"


class ImpactItemSerializer(serializers.Serializer[Any]):
    module = serializers.CharField()
    kind = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]  # the field, not Field.label
    count = serializers.IntegerField()


class ImpactSerializer(serializers.Serializer[Any]):
    module = serializers.ChoiceField(choices=LockModule.choices)
    date = serializers.DateField()
    items = ImpactItemSerializer(many=True, read_only=True)
    total = serializers.IntegerField(read_only=True)


class ImpactQuerySerializer(serializers.Serializer[Any]):
    module = serializers.ChoiceField(choices=LockModule.choices)
    date = serializers.DateField()


class LockImpactView(APIView):
    required_feature = CORE
    serializer_class = ImpactSerializer

    @requires_permission(MANAGE)
    @extend_schema(
        operation_id="settings_lock_impact",
        summary="Records not posted that a lock at this date would leave behind",
        parameters=[
            OpenApiParameter("module", OpenApiTypes.STR, enum=LockModule.values),
            OpenApiParameter("date", OpenApiTypes.DATE),
        ],
        responses=ImpactSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        query = ImpactQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        module: str = query.validated_data["module"]
        date: dt.date = query.validated_data["date"]
        organisation = current_org()
        assert organisation is not None  # noqa: S101 — set by the tenant middleware for /o/<org>/
        items = impact(organisation, module, date)
        return Response(
            {
                "module": module,
                "date": date.isoformat(),
                "items": [item.__dict__ for item in items],
                "total": sum(item.count for item in items),
            }
        )
