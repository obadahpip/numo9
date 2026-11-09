"""Test-only DRF endpoints guarded by IsOrgMemberOrAssigned (A-01-T06)."""

from __future__ import annotations

from typing import Any

from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation
from numo9.tenancy.permissions import IsOrgMemberOrAssigned

from .models import Widget


class WidgetSerializer(serializers.ModelSerializer[Widget]):
    class Meta:
        model = Widget
        fields = ("public_id", "label")


class WidgetList(generics.ListAPIView[Widget]):
    permission_classes = (IsAuthenticated, IsOrgMemberOrAssigned)
    serializer_class = WidgetSerializer

    def get_queryset(self) -> Any:
        return Widget.objects.order_by("label")


class WidgetDetail(generics.RetrieveAPIView[Widget]):
    permission_classes = (IsAuthenticated, IsOrgMemberOrAssigned)
    serializer_class = WidgetSerializer
    lookup_field = "public_id"

    def get_queryset(self) -> Any:
        return Widget.objects.all()


class UnscopedWidgetDetail(WidgetDetail):
    """Deliberately loads across organisations: only the object-level check protects it."""

    def get_queryset(self) -> Any:
        return Widget.objects.unscoped(reason="test: object-level permission check")


class OrganisationDetail(APIView):
    permission_classes = (IsAuthenticated, IsOrgMemberOrAssigned)

    def get(self, request: Request, org_id: str) -> Response:
        organisation = Organisation.objects.get(public_id=org_id)
        self.check_object_permissions(request, organisation)
        active = current_org()
        return Response({"name": organisation.name, "active": active.name if active else None})
