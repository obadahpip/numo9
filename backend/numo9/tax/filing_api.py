"""Filing cycles API (G-03a-T16), under ``/api/v1/o/<org>/tax/registrations/<id>/``.

- ``GET cycles`` — the registration's filing frequencies in date order, each with who recorded
  it and the approval reference (the change history); ``POST cycles`` ``{frequency,
  effective_from, approval_ref, approval_date, note}`` — set or switch the frequency: 201 with
  the diff (``removed`` / ``added`` / ``changed``), every period and the warnings.
- ``GET periods`` ``?from=&to=`` — the filing periods in date order with their due dates,
  status, what needs attention (``due_soon`` / ``overdue``), whether the return due date was
  moved to the next business day (``due_rolled``), and the instalment dates of annual periods.
- ``POST custom-periods`` ``{start, end, note}`` — add an out-of-cycle period;
  ``DELETE custom-periods/<period>`` — remove an unfiled one.
- ``POST preview`` ``{action: switch | custom | delete_custom, …}`` — the diff the change would
  make, writing nothing (G-03a-T15); ``{action: stop, date, reason_code, reason_text}`` and
  ``{action: restart, date, frequency, reason_text}`` the impact of a stop or restart (G-03b-T08):
  the diff, the documents dated while not registered with the registration's tax codes, and
  whether new sales default to out of scope.
- ``POST stop`` ``{date, reason_code, reason_text, confirm_number}`` — stop filing after
  ``date`` (the last day registered); ``confirm_number`` must be the registration number
  (``tax.filing.confirm_number``). ``POST restart`` ``{date, frequency, reason_text}`` — file
  again from ``date``. Both 201 with the preview's fields and the history below (G-03b-T09).
- ``GET events`` — the stop/restart history (each with its person), the not-registered gaps,
  ``stopped``, ``stop_date``, ``last_filed_end`` and the post-stop documents.

A change the rules refuse is a **422** with its ``code`` (``tax.filing.approval_required``,
``tax.filing.inside_filed``, ``tax.filing.custom_overlaps_filed``…). Reading needs
``tax.codes.view``, changing ``tax.manage``; every change is in the audit log on the registration
(the tax history). Only GST/HST (RT) and QST registrations file returns: another type is a 404.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE, requires_feature
from numo9.orgsettings.locks import local_date
from numo9.orgsettings.models import TaxRegistration
from numo9.orgsettings.service import get_settings
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from . import filing_service, stop_restart
from .filing import MONTHS, Period, instalments
from .holidays import jurisdictions_for
from .models import FilingCycle, FilingPeriod, StopReason, TaxError
from .permissions import TAX_MANAGE, TAX_VIEW
from .post_stop import post_stop_documents


def _today() -> dt.date:
    organisation = current_org()
    if organisation is None:
        return timezone.localdate()
    return local_date(organisation, timezone.now())


def _registration(public_id: Any) -> TaxRegistration:
    row: TaxRegistration | None = TaxRegistration.objects.filter(
        public_id=public_id, deleted_at__isnull=True
    ).first()
    if row is None or not row.files_returns:
        raise NotFound
    return row


def _refused(error: TaxError) -> Response:
    return Response(
        {
            "code": getattr(error, "code", None) or "invalid",
            "detail": " ".join(str(m) for m in error.messages),
        },
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def cycle_row(cycle: FilingCycle) -> dict[str, Any]:
    author = cycle.created_by
    return {
        "id": str(cycle.public_id),
        "frequency": cycle.frequency,
        "effective_from": cycle.effective_from.isoformat(),
        "approval_ref": cycle.approval_ref,
        "approval_date": cycle.approval_date.isoformat() if cycle.approval_date else None,
        "note": cycle.note,
        "created_by": getattr(author, "name", "") if author is not None else "",
        "created_at": cycle.created_at.isoformat(),
    }


def _cycles(registration: TaxRegistration) -> list[dict[str, Any]]:
    cycles = FilingCycle.objects.filter(registration=registration).select_related("created_by")
    return [cycle_row(c) for c in cycles.order_by("effective_from")]


class SwitchSerializer(serializers.Serializer[Any]):
    frequency = serializers.ChoiceField(choices=sorted(MONTHS))
    effective_from = serializers.DateField()
    approval_ref = serializers.CharField(max_length=100, required=False, allow_blank=True)
    approval_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)


class CustomPeriodSerializer(serializers.Serializer[Any]):
    start = serializers.DateField()
    end = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True)


class PreviewSerializer(serializers.Serializer[Any]):
    action = serializers.ChoiceField(
        choices=["switch", "custom", "delete_custom", "stop", "restart"]
    )
    frequency = serializers.ChoiceField(choices=sorted(MONTHS), required=False)
    effective_from = serializers.DateField(required=False)
    approval_ref = serializers.CharField(max_length=100, required=False, allow_blank=True)
    approval_date = serializers.DateField(required=False, allow_null=True)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    period = serializers.UUIDField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)
    # stop / restart (G-03b-T08)
    date = serializers.DateField(required=False)
    reason_code = serializers.CharField(max_length=16, required=False, allow_blank=True)
    reason_text = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        needs = {
            "switch": ("frequency", "effective_from"),
            "custom": ("start", "end"),
            "delete_custom": ("period",),
            "stop": ("date", "reason_code"),
            "restart": ("date", "frequency"),
        }[attrs["action"]]
        missing = {name: [self.error_messages["required"]] for name in needs if name not in attrs}
        if missing:
            raise serializers.ValidationError(missing)
        return attrs


class FilingView(APIView):
    queryset = TaxRegistration._base_manager.none()


class FilingCycleListView(FilingView):
    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_filing_cycles", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response({"results": _cycles(_registration(public_id))})

    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_filing_switch", request=SwitchSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        registration = _registration(public_id)
        payload = SwitchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        change = {"action": "switch", **payload.validated_data}
        try:
            result = filing_service.apply_change(
                registration, change, user=request.user, today=_today()
            )
        except TaxError as error:
            return _refused(error)
        return Response({**result, "cycles": _cycles(registration)}, status=status.HTTP_201_CREATED)


class FilingPeriodListView(FilingView):
    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_filing_periods", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        registration = _registration(public_id)
        periods = FilingPeriod.objects.filter(registration=registration).order_by("start")
        try:
            if request.query_params.get("from"):
                periods = periods.filter(
                    end__gte=dt.date.fromisoformat(request.query_params["from"])
                )
            if request.query_params.get("to"):
                periods = periods.filter(
                    start__lte=dt.date.fromisoformat(request.query_params["to"])
                )
        except ValueError:
            raise serializers.ValidationError({"from": ["Use YYYY-MM-DD dates."]}) from None
        today = _today()
        places = jurisdictions_for(registration.type)
        settings = get_settings(registration.organisation)
        rows = []
        for period in periods:
            row = filing_service.period_row(period)
            row["attention"] = filing_service.attention(period, today)
            row["due_rolled"] = filing_service.is_rolled(registration, period, settings)
            row["instalments"] = [
                {
                    "quarter_start": i.quarter_start.isoformat(),
                    "quarter_end": i.quarter_end.isoformat(),
                    "due_date": i.due_date.isoformat(),
                    "amount": i.amount,
                }
                for i in instalments(
                    Period(period.start, period.end, period.kind, period.frequency), places
                )
                if period.kind == "regular"
            ]
            rows.append(row)
        return Response(
            {
                "registration": {
                    "id": str(registration.public_id),
                    "type": registration.type,
                    "number": registration.display_number,
                    "start_date": _iso(registration.start_date),
                    "stop_date": _iso(registration.stop_date),
                },
                "today": today.isoformat(),
                "results": rows,
            }
        )


def _iso(value: dt.date | None) -> str | None:
    return value.isoformat() if value else None


class FilingCustomPeriodListView(FilingView):
    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_filing_custom_add", request=CustomPeriodSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        registration = _registration(public_id)
        payload = CustomPeriodSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        change = {"action": "custom", **payload.validated_data}
        try:
            result = filing_service.apply_change(
                registration, change, user=request.user, today=_today()
            )
        except TaxError as error:
            return _refused(error)
        return Response(result, status=status.HTTP_201_CREATED)


class FilingCustomPeriodDetailView(FilingView):
    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_filing_custom_remove", responses={200: dict})
    def delete(self, request: Request, org: Any, public_id: Any, period_id: Any) -> Response:
        registration = _registration(public_id)
        if not FilingPeriod.objects.filter(registration=registration, public_id=period_id).exists():
            raise NotFound
        change = {"action": "delete_custom", "period": period_id}
        try:
            result = filing_service.apply_change(
                registration, change, user=request.user, today=_today()
            )
        except TaxError as error:
            return _refused(error)
        return Response(result)


class FilingPreviewView(FilingView):
    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_filing_preview", request=PreviewSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        registration = _registration(public_id)
        payload = PreviewSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        change = dict(payload.validated_data)
        try:
            if change["action"] in ("stop", "restart"):  # G-03b-T08
                return Response(
                    stop_restart.preview(registration, change, user=request.user, today=_today())
                )
            return Response(filing_service.preview(registration, change, today=_today()))
        except TaxError as error:
            return _refused(error)


# ---- stop & restart (G-03b-T09) ----------------------------------------------------------------


class StopSerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    reason_code = serializers.ChoiceField(choices=StopReason.choices)
    reason_text = serializers.CharField(required=False, allow_blank=True, default="")
    #: The registration number typed to confirm (the danger zone's check, G-03b-T10).
    confirm_number = serializers.CharField()


class RestartSerializer(serializers.Serializer[Any]):
    date = serializers.DateField()
    frequency = serializers.ChoiceField(choices=sorted(MONTHS))
    reason_text = serializers.CharField(required=False, allow_blank=True, default="")


def _same_number(registration: TaxRegistration, typed: str) -> bool:
    def bare(value: str) -> str:
        return "".join(ch for ch in value.upper() if ch.isalnum())

    return bare(typed) == bare(registration.number)


class FilingStopView(FilingView):
    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_filing_stop", request=StopSerializer, responses={201: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        registration = _registration(public_id)
        payload = StopSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        if not _same_number(registration, data.pop("confirm_number")):
            return _refused(
                TaxError(
                    _("Type the registration number exactly to confirm."),
                    code="tax.filing.confirm_number",
                )
            )
        try:
            result = stop_restart.apply(
                registration, {"action": "stop", **data}, user=request.user, today=_today()
            )
        except TaxError as error:
            return _refused(error)
        return Response(
            {**result, **stop_restart.status_of(registration)}, status=status.HTTP_201_CREATED
        )


class FilingRestartView(FilingView):
    @requires_permission(TAX_MANAGE.key)
    @requires_feature(CORE)
    @extend_schema(
        operation_id="tax_filing_restart", request=RestartSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        registration = _registration(public_id)
        payload = RestartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = stop_restart.apply(
                registration,
                {"action": "restart", **payload.validated_data},
                user=request.user,
                today=_today(),
            )
        except TaxError as error:
            return _refused(error)
        return Response(
            {**result, **stop_restart.status_of(registration), "cycles": _cycles(registration)},
            status=status.HTTP_201_CREATED,
        )


class FilingEventListView(FilingView):
    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_filing_events", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        registration = _registration(public_id)
        return Response(
            {
                **stop_restart.status_of(registration),
                "documents": post_stop_documents(registration),
            }
        )
