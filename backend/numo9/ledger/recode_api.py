"""Find & recode API (C-07-T09), under ``/api/v1/o/<org>/recode/``. Feature key
``accounting.recode.write``; permission ``accounting.recode`` (owners, admins and the advisers'
roles — accountants, accountant delegates; not sales, purchasing or employees).

- ``POST recode/search`` ``{criteria, page, page_size}`` — the lines found (C-07-T02), paged,
  with ``count``; ``excluded`` — the lines the exclusion engine leaves out, each with its
  ``reason`` (C-07-T03); ``keys`` — every included line's ``{entry, line_no, fingerprint}``, so a
  grid can **select all across pages** without loading them;
- ``POST recode/preview`` ``{criteria, changes, selection?, page, page_size}`` — before / after
  per line (paged), the summary (``lines · accounts · totals unchanged · excluded``), totals per
  book, account movements and the tax impact (C-07-T04);
- ``POST recode/execute`` ``{criteria, changes, selection?, name?, confirm_tax?}`` — creates the
  batch and runs it: ``201`` with the batch when it ran at once, ``202`` with the running batch
  (and its job) for more than 200 lines (C-07-T05);
- ``GET recode/batches`` — the history, newest first; ``GET recode/batches/<id>`` — one batch
  with its problems and ``undo`` (``{"allowed": bool, "blocked": [...]}``, C-07-T07);
- ``POST recode/batches/<id>/undo`` ``{reason}`` — undo it;
- ``GET recode/batches/<id>/report?export=csv|xlsx|pdf`` — the audit report (C-07-T08).

A refusal is a ``400`` ``{"code", "detail"}`` (``ledger.recode.condition_invalid``,
``ledger.recode.changes_invalid``, ``ledger.recode.confirm_tax``, ``ledger.recode.undo_refused``
with ``blocked``…).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
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

from . import recode_execute, recode_report, recode_undo
from .models import RecodeBatch
from .permissions import RECODE
from .recode_exclusions import split
from .recode_preview import fingerprint, preview
from .recode_query import find_lines
from .sequence import format_journal_number

FEATURE = "accounting.recode.write"
PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


def _refused(error: ValidationError, **extra: Any) -> Response:
    code = getattr(error, "code", None)
    field = None
    if hasattr(error, "error_dict"):
        field, errors = next(iter(error.error_dict.items()))
        code = code or (errors[0].code if errors else None)
        detail = " ".join(str(m) for e in errors for m in e.messages)
    else:
        code = code or next((e.code for e in error.error_list if e.code), None)
        detail = " ".join(str(m) for m in error.messages)
    body: dict[str, Any] = {"code": code or "invalid", "detail": detail, **extra}
    if field:
        body["field"] = field
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def _person(user: Any) -> dict[str, str] | None:
    return {"id": str(user.public_id), "name": user.name or user.email} if user else None


def line_row(line: Any) -> dict[str, Any]:
    entry = line.entry
    return {
        "entry": str(entry.public_id),
        "number": format_journal_number(entry.organisation, entry.number),
        "date": entry.date.isoformat(),
        "type": entry.type,
        "narration": entry.narration,
        "line_no": line.line_no,
        "book": line.book,
        "account": {"id": str(line.account.public_id), "label": str(line.account)},
        "debit": f"{line.debit:.2f}",
        "credit": f"{line.credit:.2f}",
        "tax_code": line.tax_code or "",
        "contact": (
            {"id": str(line.contact.public_id), "label": line.contact.display_name}
            if line.contact_id
            else None
        ),
        "tracking": dict(line.tracking or {}),
        "description": line.description,
        "fingerprint": fingerprint(line),
    }


def batch_row(batch: RecodeBatch, *, detail: bool = False) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(batch.public_id),
        "name": batch.name,
        "label": str(batch),
        "status": batch.status,
        "criteria": batch.criteria,
        "changes": batch.changes,
        "line_count": batch.line_count,
        "excluded_count": batch.excluded_count,
        "progress": batch.progress,
        "problem_count": sum(len(p.get("lines", [])) for p in batch.problems or []),
        "created_at": batch.created_at.isoformat(),
        "executed_by": _person(batch.executed_by),
        "executed_at": batch.executed_at.isoformat() if batch.executed_at else None,
        "undone_by": _person(batch.undone_by),
        "undone_at": batch.undone_at.isoformat() if batch.undone_at else None,
        "undo_reason": batch.undo_reason,
        "job": str(batch.job_run.public_id) if batch.job_run_id and batch.job_run else None,
        "error": batch.error,
    }
    if detail:
        blocked = (
            recode_undo.undo_blockers(batch)
            if batch.status in recode_undo.UNDOABLE and batch.line_count
            else []
        )
        row["problems"] = batch.problems or []
        row["undo"] = {
            "allowed": batch.status in recode_undo.UNDOABLE
            and bool(batch.line_count)
            and not blocked,
            "blocked": blocked,
        }
    return row


def _page(data: dict[str, Any]) -> tuple[int, int]:
    return int(data.get("page") or 1), int(data.get("page_size") or PAGE_SIZE)


def _org() -> Any:
    organisation = current_org()
    if organisation is None:  # the URL's organisation is always set by the tenancy middleware
        raise NotFound
    return organisation


class SearchSerializer(serializers.Serializer[Any]):
    criteria = serializers.JSONField()
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=MAX_PAGE_SIZE)


class PreviewSerializer(SearchSerializer):
    changes = serializers.JSONField()
    selection = serializers.JSONField(required=False, allow_null=True)


class ExecuteSerializer(serializers.Serializer[Any]):
    criteria = serializers.JSONField()
    changes = serializers.JSONField()
    selection = serializers.JSONField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    confirm_tax = serializers.BooleanField(required=False, default=False)


class UndoSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class RecodeSearchView(APIView):
    @requires_permission(RECODE.key)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="recode_search", request=SearchSerializer, responses={200: dict})
    def post(self, request: Request, org: Any) -> Response:
        payload = SearchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        organisation = _org()
        page, size = _page(data)
        try:
            found = list(find_lines(organisation, data["criteria"]))
        except ValidationError as error:
            return _refused(error)
        included, excluded = split(organisation, found, {}, request.user)
        start = (page - 1) * size
        return Response(
            {
                "count": len(included),
                "page": page,
                "page_size": size,
                "lines": [line_row(line) for line in included[start : start + size]],
                "keys": [
                    {
                        "entry": str(line.entry.public_id),
                        "line_no": line.line_no,
                        "fingerprint": fingerprint(line),
                    }
                    for line in included
                ],
                "excluded_count": len(excluded),
                "excluded": [{**line_row(x.line), "reason": x.reason.as_dict()} for x in excluded],
            }
        )


class RecodePreviewView(APIView):
    @requires_permission(RECODE.key)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="recode_preview", request=PreviewSerializer, responses={200: dict})
    def post(self, request: Request, org: Any) -> Response:
        payload = PreviewSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        organisation = _org()
        page, size = _page(data)
        try:
            chosen = recode_execute.clean_selection(data.get("selection"))
            keys = (
                {(row["entry"], row["line_no"]) for row in chosen} if chosen is not None else None
            )
            built = preview(
                organisation,
                data["criteria"],
                data["changes"],
                request.user,
                keys=keys,
            )
        except ValidationError as error:
            return _refused(error)
        start = (page - 1) * size

        def money(totals: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
            return {b: {k: f"{v:.2f}" for k, v in t.items()} for b, t in totals.items()}

        return Response(
            {
                "summary": built.summary(),
                "count": len(built.lines),
                "page": page,
                "page_size": size,
                "lines": [
                    {
                        **row.as_dict(),
                        "number": format_journal_number(organisation, row.line.entry.number),
                    }
                    for row in built.lines[start : start + size]
                ],
                "excluded": [
                    {**line_row(x.line), "reason": x.reason.as_dict()} for x in built.excluded
                ],
                "totals_before": money(built.totals_before),
                "totals_after": money(built.totals_after),
                "accounts": money(built.accounts),
                "tax_impact": built.tax_impact,
            }
        )


class RecodeExecuteView(APIView):
    @requires_permission(RECODE.key)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="recode_execute", request=ExecuteSerializer, responses={201: dict})
    def post(self, request: Request, org: Any) -> Response:
        payload = ExecuteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        organisation = _org()
        try:
            batch = recode_execute.create_batch(
                organisation,
                data["criteria"],
                data["changes"],
                request.user,
                selection=data.get("selection"),
                name=data.get("name", ""),
                confirm_tax=data["confirm_tax"],
            )
            done = recode_execute.execute(batch, request.user)
        except ValidationError as error:
            return _refused(error)
        running = done.status == "running"
        return Response(
            batch_row(done, detail=not running),
            status=status.HTTP_202_ACCEPTED if running else status.HTTP_201_CREATED,
        )


class RecodeBatchListView(APIView):
    @requires_permission(RECODE.key)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="recode_batches", responses={200: dict})
    def get(self, request: Request, org: Any) -> Response:
        rows = RecodeBatch.objects.select_related("executed_by", "undone_by", "job_run").order_by(
            "-created_at", "-pk"
        )[:200]
        return Response({"batches": [batch_row(b) for b in rows]})


def _batch(public_id: Any) -> RecodeBatch:
    batch: RecodeBatch | None = (
        RecodeBatch.objects.select_related("executed_by", "undone_by", "job_run")
        .filter(public_id=public_id)
        .first()
    )
    if batch is None:
        raise NotFound
    return batch


class RecodeBatchDetailView(APIView):
    @requires_permission(RECODE.key)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="recode_batch", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(batch_row(_batch(public_id), detail=True))


class RecodeUndoView(APIView):
    @requires_permission(RECODE.key)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="recode_undo", request=UndoSerializer, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        batch = _batch(public_id)
        payload = UndoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            done = recode_undo.undo(
                batch, request.user, reason=payload.validated_data.get("reason", "")
            )
        except recode_undo.RecodeUndoRefused as error:
            return _refused(error, blocked=error.blocked)
        return Response(batch_row(done, detail=True))


class RecodeReportView(APIView):
    @requires_permission(RECODE.key)
    @requires_feature(FEATURE)
    @extend_schema(operation_id="recode_report", responses={200: bytes})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        batch = _batch(public_id)
        fmt = request.query_params.get("export", "csv")
        if fmt not in recode_report.FORMATS:
            raise serializers.ValidationError({"export": ["Use csv, xlsx or pdf."]})
        locale = getattr(request, "LANGUAGE_CODE", None) or "en-ca"
        body, content_type, name = recode_report.export(batch, fmt, locale.lower())
        response = HttpResponse(body, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response
