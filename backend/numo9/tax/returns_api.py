"""GST/HST returns API (G-03-T10), under ``/api/v1/o/<org>/tax/returns``. Feature keys
``tax.returns.read`` / ``.write`` / ``.approve``; permissions ``tax.returns.view`` /
``.prepare`` / ``.file``.

- ``GET tax/returns?registration=…`` — the returns, latest first;
- ``POST tax/returns`` ``{period, method?}`` — generate the period's return (the draft in
  progress, or a new one): 201;
- ``GET tax/returns/<id>`` — the return: its lines with their CRA labels, the entries typed on
  it, its versions and — for a draft — ``changed``: the lines the books now put differently
  (the "changed since you looked" banner);
- ``POST …/recalculate`` ``{entries?}`` — recalculate a draft from the books (and the entries);
- ``POST …/review``, ``…/send-back`` ``{reason}``, ``…/file`` ``{confirmation_no, filed_on?}``,
  ``…/amend`` ``{reason}`` — the workflow (G-03-T06 – T09; the reviewer isn't the preparer);
- ``GET …/drill?line=101`` — the documents behind a line (G-03-T05);
- ``GET …/pdf`` and ``…/csv`` — the worksheet (G-03-T13).

A refusal is a ``422`` ``{"code", "detail"}``; self-review is the ``403`` of A-03-T08.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from . import return_export, returns
from .models import FilingPeriod, ReturnMethod, ReturnStatus, TaxError, TaxReturn
from .permissions import RETURNS_FILE, RETURNS_PREPARE, RETURNS_VIEW
from .return_lines import DRILL_LINES, ENTRY_LINES, LINES, drill_down, line_labels

READ = "tax.returns.read"
WRITE = "tax.returns.write"
APPROVE = "tax.returns.approve"


def _person(person: Any) -> dict[str, str] | None:
    if person is None:
        return None
    return {
        "id": str(getattr(person, "public_id", "") or ""),
        "name": getattr(person, "name", "") or "",
    }


def _refused(error: TaxError) -> Response:
    return Response(
        {
            "code": getattr(error, "code", None) or "invalid",
            "detail": " ".join(str(m) for m in error.messages),
        },
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def period_row(period: FilingPeriod) -> dict[str, Any]:
    return {
        "id": str(period.public_id),
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
        "label": str(period),
        "status": period.status,
        "due_date": period.due_date.isoformat(),
        "locked": period.status in ("filed", "paid"),
    }


def return_row(tax_return: TaxReturn, *, detail: bool = False) -> dict[str, Any]:
    values = tax_return.lines or {}
    labels = line_labels()
    row: dict[str, Any] = {
        "id": str(tax_return.public_id),
        "registration": str(tax_return.registration.public_id),
        "period": period_row(tax_return.period),
        "version": tax_return.version,
        "status": tax_return.status,
        "method": tax_return.method,
        "is_current": tax_return.is_current,
        "lines": [
            {
                "line": line,
                "label": labels[line],
                "amount": str(values.get(line, "0.00")),
                "drill": line in DRILL_LINES,
                "entry": line in ENTRY_LINES,
            }
            for line in LINES
        ],
        "entries": values.get("entries") or {},
        "prepared_by": _person(tax_return.prepared_by),
        "prepared_at": tax_return.prepared_at.isoformat() if tax_return.prepared_at else None,
        "reviewed_by": _person(tax_return.reviewed_by),
        "filed_by": _person(tax_return.filed_by),
        "filed_on": tax_return.filed_on.isoformat() if tax_return.filed_on else None,
        "confirmation_no": tax_return.confirmation_no,
        "amend_reason": tax_return.amend_reason,
    }
    if detail:
        row["versions"] = returns.versions(tax_return.period)
        row["changed"] = []
        if tax_return.status == ReturnStatus.DRAFT:
            fresh = returns.computed_lines(tax_return)
            row["changed"] = [
                {"line": line, "was": str(values.get(line, "0.00")), "now": fresh[line]}
                for line in LINES
                if str(values.get(line, "0.00")) != fresh[line]
            ]
    return row


def _return(public_id: Any) -> TaxReturn:
    found: TaxReturn | None = (
        TaxReturn.objects.select_related(
            "period", "registration", "prepared_by", "reviewed_by", "filed_by"
        )
        .filter(public_id=public_id, deleted_at__isnull=True)
        .first()
    )
    if found is None:
        raise NotFound
    return found


class GenerateSerializer(serializers.Serializer[Any]):
    period = serializers.UUIDField()
    method = serializers.ChoiceField(choices=ReturnMethod.values, required=False)


class EntriesSerializer(serializers.Serializer[Any]):
    entries = serializers.DictField(
        child=serializers.DecimalField(max_digits=18, decimal_places=2), required=False
    )

    def validate_entries(self, value: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(value) - set(ENTRY_LINES))
        if unknown:
            raise serializers.ValidationError(
                f"Only lines {', '.join(ENTRY_LINES)} are entered on the return."
            )
        return value


class ReturnReasonSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(allow_blank=True)


class ReturnFileSerializer(serializers.Serializer[Any]):
    confirmation_no = serializers.CharField(allow_blank=True)
    filed_on = serializers.DateField(required=False)


class ReturnView(APIView):
    queryset = TaxReturn._base_manager.none()


class TaxReturnListView(ReturnView):
    @requires_permission(RETURNS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="tax_returns", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        rows = TaxReturn.objects.filter(deleted_at__isnull=True).select_related(
            "period", "registration", "prepared_by", "reviewed_by", "filed_by"
        )
        registration = request.query_params.get("registration")
        if registration:
            rows = rows.filter(registration__public_id=registration)
        rows = rows.order_by("-period__start", "-version")[:200]
        return Response({"returns": [return_row(r) for r in rows]})

    @requires_permission(RETURNS_PREPARE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="tax_returns_generate", request=GenerateSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = GenerateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        period = FilingPeriod.objects.filter(public_id=payload.validated_data["period"]).first()
        if period is None or current_org() is None:
            raise NotFound
        try:
            made = returns.prepare(
                period,
                request.user,
                method=payload.validated_data.get("method") or ReturnMethod.REGULAR,
            )
        except TaxError as error:
            return _refused(error)
        return Response(return_row(made, detail=True), status=status.HTTP_201_CREATED)


class TaxReturnDetailView(ReturnView):
    @requires_permission(RETURNS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="tax_return", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(return_row(_return(public_id), detail=True))


class TaxReturnRecalculateView(ReturnView):
    @requires_permission(RETURNS_PREPARE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="tax_return_recalculate", request=EntriesSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        tax_return = _return(public_id)
        payload = EntriesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            done = returns.recalculate(
                tax_return, request.user, entries=payload.validated_data.get("entries")
            )
        except TaxError as error:
            return _refused(error)
        return Response(return_row(done, detail=True))


class TaxReturnReviewView(ReturnView):
    @requires_permission(RETURNS_FILE.key)
    @requires_feature(APPROVE)
    @extend_schema(operation_id="tax_return_review", request=None, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        try:
            done = returns.review(_return(public_id), request.user)
        except TaxError as error:
            return _refused(error)
        return Response(return_row(done, detail=True))


class TaxReturnSendBackView(ReturnView):
    @requires_permission(RETURNS_FILE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="tax_return_send_back", request=ReturnReasonSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        tax_return = _return(public_id)
        payload = ReturnReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            done = returns.send_back(tax_return, request.user, payload.validated_data["reason"])
        except TaxError as error:
            return _refused(error)
        return Response(return_row(done, detail=True))


class TaxReturnFileView(ReturnView):
    @requires_permission(RETURNS_FILE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="tax_return_file", request=ReturnFileSerializer, responses={200: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        tax_return = _return(public_id)
        payload = ReturnFileSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            done = returns.file(
                tax_return,
                request.user,
                confirmation_no=payload.validated_data["confirmation_no"],
                filed_on=payload.validated_data.get("filed_on"),
            )
        except TaxError as error:
            return _refused(error)
        return Response(return_row(done, detail=True))


class TaxReturnAmendView(ReturnView):
    @requires_permission(RETURNS_FILE.key)
    @requires_feature(APPROVE)
    @extend_schema(
        operation_id="tax_return_amend", request=ReturnReasonSerializer, responses={201: dict}
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        tax_return = _return(public_id)
        payload = ReturnReasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            made = returns.amend(tax_return, request.user, payload.validated_data["reason"])
        except TaxError as error:
            return _refused(error)
        return Response(return_row(made, detail=True), status=status.HTTP_201_CREATED)


class TaxReturnDrillView(ReturnView):
    @requires_permission(RETURNS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="tax_return_drill", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        tax_return = _return(public_id)
        line = request.query_params.get("line", "")
        if line not in LINES:
            raise serializers.ValidationError({"line": ["Choose a line of the return."]})
        documents = drill_down(tax_return.period, line)
        return Response({"line": line, "documents": documents})


class TaxReturnFileExportView(ReturnView):
    fmt = "csv"

    @requires_permission(RETURNS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="tax_return_export", responses={200: bytes})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        tax_return = _return(public_id)
        locale = (getattr(request, "LANGUAGE_CODE", None) or "en-ca").lower()
        if self.fmt == "pdf":
            body, content_type = return_export.render_pdf(tax_return, locale), "application/pdf"
        else:
            body, content_type = return_export.render_csv(tax_return, locale), "text/csv"
        response = HttpResponse(body, content_type=content_type)
        name = return_export.filename(tax_return, self.fmt)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response


class TaxReturnPdfView(TaxReturnFileExportView):
    fmt = "pdf"

    @requires_permission(RETURNS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="tax_return_pdf", responses={200: bytes})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        return super().get(request, org, public_id)


class TaxReturnCsvView(TaxReturnFileExportView):
    fmt = "csv"

    @requires_permission(RETURNS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="tax_return_csv", responses={200: bytes})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        return super().get(request, org, public_id)
