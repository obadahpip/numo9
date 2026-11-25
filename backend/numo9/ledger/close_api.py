"""Period close API (C-06-T07), under ``/api/v1/o/<org>/period-close/``. Feature keys
``accounting.period_close.read`` / ``.write``; permissions ``accounting.period_close.view`` /
``.manage`` (a reopen is refused for anyone but an adviser, by the service).

- ``GET period-close/?year=2026`` — the timeline: for each module (general ledger, sales,
  purchases, bank, payroll, sales tax) and each month of the fiscal year containing 1 Jan of
  ``year`` (default: the current fiscal year), its status — ``closed`` (an open close covers it;
  ``close`` names it), ``locked`` (a lock date covers it without a close), ``open`` — and the
  year-end close of the year, if any;
- ``GET period-close/checklist?period_end=2026-06-30`` — what is still open in that month
  (``period_close.checklist``);
- ``POST period-close/close`` ``{module, period_end}`` — close a month (201);
- ``POST period-close/<id>/reopen`` ``{reason, force}`` — reopen it (advisers);
- ``POST period-close/year-end`` ``{fiscal_year_end}`` — the year-end roll and close (201).

A refusal is a 400 with its ``code`` (``ledger.close.out_of_order``, ``ledger.close.
adviser_only``…).
"""

from __future__ import annotations

import calendar
import datetime as dt
from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.orgsettings.locks import is_adviser, local_date
from numo9.orgsettings.models import LockModule
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from . import period_close as service
from .models import CloseKind, PeriodClose
from .permissions import PERIOD_CLOSE_MANAGE, PERIOD_CLOSE_VIEW

READ = "accounting.period_close.read"
WRITE = "accounting.period_close.write"
MODULES = [m.value for m in LockModule]


def close_row(row: PeriodClose) -> dict[str, Any]:
    def person(user: Any) -> dict[str, str] | None:
        return {"id": str(user.public_id), "name": user.name or user.email} if user else None

    return {
        "id": str(row.public_id),
        "module": row.module,
        "period_end": row.period_end.isoformat(),
        "kind": row.kind,
        "closed_by": person(row.closed_by),
        "closed_at": row.closed_at.isoformat(),
        "reopened_by": person(row.reopened_by),
        "reopened_at": row.reopened_at.isoformat() if row.reopened_at else None,
        "reason": row.reason,
        "entries": [
            {"book": book, "id": str(entry.public_id), "number": entry.number}
            for book, entry in (("accounting", row.accounting_entry), ("tax", row.tax_entry))
            if entry is not None
        ],
    }


def _months(start: dt.date) -> list[tuple[dt.date, dt.date]]:
    out = []
    year, month = start.year, start.month
    for _ in range(12):
        last = calendar.monthrange(year, month)[1]
        out.append((dt.date(year, month, 1), dt.date(year, month, last)))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def timeline(organisation: Any, year: int | None, user: Any) -> dict[str, Any]:
    today = local_date(organisation, timezone.now())
    anchor = dt.date(year, 1, 1) if year else today
    start, end = service.fiscal_year_of(organisation, anchor)
    closes = list(
        PeriodClose.objects.filter(organisation=organisation, reopened_at__isnull=True)
        .select_related("closed_by", "reopened_by", "accounting_entry", "tax_entry")
        .order_by("period_end")
    )
    rows = []
    for module in MODULES:
        locked = service.lock_dates(organisation, module).get("everyone")
        locked_to = dt.date.fromisoformat(locked) if locked else None
        own = [c for c in closes if c.module == module]
        months = []
        for first, last in _months(start):
            covering = next((c for c in own if c.period_end >= last), None)
            state = (
                "closed"
                if covering is not None
                else ("locked" if locked_to is not None and locked_to >= last else "open")
            )
            months.append(
                {
                    "start": first.isoformat(),
                    "end": last.isoformat(),
                    "status": state,
                    "close": str(covering.public_id) if covering is not None else None,
                    "past": last < today,
                }
            )
        rows.append({"module": module, "label": str(LockModule(module).label), "months": months})
    year_end = next(
        (c for c in closes if c.kind == CloseKind.YEAR_END and c.period_end == end), None
    )
    return {
        "fiscal_year": {"start": start.isoformat(), "end": end.isoformat()},
        "today": today.isoformat(),
        "modules": rows,
        "closes": [close_row(c) for c in closes if start <= c.period_end <= end],
        "year_end": close_row(year_end) if year_end else None,
        "is_adviser": is_adviser(user, organisation),
    }


def _refused(error: Any) -> Response:
    messages = getattr(error, "messages", None) or [str(error)]
    return Response(
        {"code": getattr(error, "code", "invalid"), "detail": " ".join(str(m) for m in messages)},
        status=status.HTTP_400_BAD_REQUEST,
    )


class PeriodCloseTimelineView(APIView):
    @requires_permission(PERIOD_CLOSE_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="period_close_timeline", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        raw = request.query_params.get("year")
        try:
            year = int(raw) if raw else None
        except ValueError:
            raise serializers.ValidationError({"year": ["Use a year like 2026."]}) from None
        return Response(timeline(current_org(), year, request.user))


class PeriodCloseChecklistView(APIView):
    @requires_permission(PERIOD_CLOSE_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="period_close_checklist", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        try:
            end = dt.date.fromisoformat(request.query_params.get("period_end", ""))
        except ValueError:
            raise serializers.ValidationError({"period_end": ["Use YYYY-MM-DD."]}) from None
        organisation = current_org()
        return Response(
            {"period_end": end.isoformat(), "items": service.checklist(organisation, end)}
        )


class CloseSerializer(serializers.Serializer[Any]):
    module = serializers.ChoiceField(choices=MODULES)
    period_end = serializers.DateField()


class ReopenSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(allow_blank=True)
    force = serializers.BooleanField(required=False, default=False)


class YearEndSerializer(serializers.Serializer[Any]):
    fiscal_year_end = serializers.DateField()


class PeriodCloseView(APIView):
    @requires_permission(PERIOD_CLOSE_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="period_close_close", request=CloseSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = CloseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            row = service.close(
                current_org(),
                payload.validated_data["module"],
                payload.validated_data["period_end"],
                request.user,
            )
        except service.CloseRefused as error:
            return _refused(error)
        return Response(close_row(row), status=status.HTTP_201_CREATED)


class PeriodYearEndView(APIView):
    @requires_permission(PERIOD_CLOSE_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="period_close_year_end", request=YearEndSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = YearEndSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            row = service.close_year(
                current_org(), payload.validated_data["fiscal_year_end"], request.user
            )
        except service.CloseRefused as error:
            return _refused(error)
        return Response(close_row(row), status=status.HTTP_201_CREATED)


class PeriodReopenView(APIView):
    @requires_permission(PERIOD_CLOSE_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="period_close_reopen", request=ReopenSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        row = PeriodClose.objects.filter(public_id=public_id).first()
        if row is None:
            raise NotFound
        payload = ReopenSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            done = service.reopen(
                row,
                request.user,
                payload.validated_data["reason"],
                force=payload.validated_data["force"],
            )
        except service.CloseRefused as error:
            return _refused(error)
        return Response(close_row(done))
