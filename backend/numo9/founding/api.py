"""Founding offer in the platform console (U-08-T11), under ``/api/v1/platform/founding``.

- ``GET  platform/founding`` — the counter (cap, allocated, remaining), the churn rules and every
  slot (organisation, number, first payment, allocated / cancelled / released, reason);
  ``platform.console.view``.
- ``GET  platform/founding/export`` — the slots as CSV (one row per number handed out: the row
  count equals ``allocated``); ``platform.console.view``.
- ``POST platform/founding/slots/<slot_no>/release`` — release a slot with a reason (5–500
  characters, kept in the audit entry); ``platform.catalogue.manage``. A released number is
  never handed out again.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.rbac.drf import requires_permission
from numo9.rbac.permissions import CATALOGUE_MANAGE, CONSOLE_VIEW

from .models import FoundingCounter, FoundingSlot
from .services import ReleaseReason, release_slot


class FoundingSlotRowSerializer(serializers.Serializer[Any]):
    slot_no = serializers.IntegerField()
    organisation_id = serializers.UUIDField(source="organisation.public_id")
    organisation_name = serializers.CharField(source="organisation.name")
    allocated_at = serializers.DateTimeField()
    payment_ref = serializers.CharField()
    lapsed_at = serializers.DateTimeField(allow_null=True, help_text="Cancelled; may return")
    released_at = serializers.DateTimeField(allow_null=True)
    release_reason = serializers.CharField()
    state = serializers.SerializerMethodField()

    def get_state(self, slot: FoundingSlot) -> str:
        if slot.released_at is not None:
            return "released"
        return "cancelled" if slot.lapsed_at is not None else "active"


class FoundingOverviewSerializer(serializers.Serializer[Any]):
    cap = serializers.IntegerField()
    allocated = serializers.IntegerField()
    remaining = serializers.IntegerField()
    active = serializers.IntegerField(help_text="Slots not released")
    churn_rule = serializers.CharField()
    return_window_days = serializers.IntegerField()
    refund_release_hours = serializers.IntegerField()
    slots = FoundingSlotRowSerializer(many=True)


class ReleaseSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(min_length=5, max_length=500, trim_whitespace=True)


def _slots() -> Any:
    return FoundingSlot.objects.select_related("organisation").order_by("slot_no")


def overview() -> dict[str, Any]:
    counter = FoundingCounter.current()
    slots = list(_slots())
    return {
        "cap": counter.cap,
        "allocated": counter.allocated,
        "remaining": counter.remaining,
        "active": sum(1 for s in slots if s.released_at is None),
        "churn_rule": counter.churn_rule,
        "return_window_days": counter.return_window_days,
        "refund_release_hours": counter.refund_release_hours,
        "slots": slots,
    }


class FoundingOverviewView(APIView):
    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_founding_overview",
        summary="Founding offer: counter, churn rules and every slot",
        responses=FoundingOverviewSerializer,
    )
    def get(self, request: Request) -> Response:
        return Response(FoundingOverviewSerializer(overview()).data)


EXPORT_COLUMNS = (
    "slot_no",
    "organisation_id",
    "organisation_name",
    "allocated_at",
    "payment_ref",
    "state",
    "cancelled_at",
    "released_at",
    "release_reason",
)


def export_csv() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for slot in _slots():
        state = FoundingSlotRowSerializer().get_state(slot)
        writer.writerow(
            [
                slot.slot_no,
                slot.organisation.public_id,
                slot.organisation.name,
                slot.allocated_at.isoformat(),
                slot.payment_ref,
                state,
                slot.lapsed_at.isoformat() if slot.lapsed_at else "",
                slot.released_at.isoformat() if slot.released_at else "",
                slot.release_reason,
            ]
        )
    return buffer.getvalue()


class FoundingExportView(APIView):
    required_feature = CORE

    @requires_permission(CONSOLE_VIEW.key)
    @extend_schema(
        operation_id="platform_founding_export",
        summary="Founding slots as CSV (one row per number handed out)",
        responses={(200, "text/csv"): OpenApiTypes.STR},
    )
    def get(self, request: Request) -> HttpResponse:
        response = HttpResponse(export_csv(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="numo9-founding-slots.csv"'
        return response


class FoundingReleaseView(APIView):
    required_feature = CORE

    @requires_permission(CATALOGUE_MANAGE.key)
    @extend_schema(
        operation_id="platform_founding_release",
        summary="Release a founding slot with a reason (audited; the number is not reused)",
        request=ReleaseSerializer,
        responses=FoundingSlotRowSerializer,
    )
    def post(self, request: Request, slot_no: int) -> Response:
        payload = ReleaseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        slot = _slots().filter(slot_no=slot_no).first()
        if slot is None:
            raise NotFound(_("No founding slot with this number."))
        if slot.released_at is not None:
            raise serializers.ValidationError({"reason": [_("This slot is already released.")]})
        release_slot(
            slot, ReleaseReason.ADMIN, actor=request.user, note=payload.validated_data["reason"]
        )
        return Response(FoundingSlotRowSerializer(slot).data)
