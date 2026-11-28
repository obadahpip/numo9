"""Statement import API (F-02-T11), under ``/api/v1/o/<org>/bank-accounts/<id>/``.

The wizard's steps — Upload → Map → Preview → Confirm — and the history:

- ``GET imports`` — the account's imports, newest first: file, format, status, counts, who and
  when, ``can_undo`` (committed, and none of its lines coded or matched), ``in_use`` (how many
  are);
- ``POST imports`` (multipart ``file``) — upload: the file is checked like every document (A-06:
  type, 25 MB, content = extension) and read as a statement. 201 with the import, what was
  detected (``format``, ``encoding``, ``delimiter``, ``warnings``), and for CSV / XLSX the first
  rows of the file (``sample``), the chosen mapping and its layout, every mapping with its score,
  and the date formats the dates fit (``date_ambiguous`` when more than one);
- ``GET imports/<id>`` — the same, for a pending import (the wizard after a reload);
- ``POST imports/<id>/preview`` ``{mapping, layout, status, offset, limit}`` — dry run with the
  saved mapping ``mapping`` or the edited ``layout`` (default: the detected one): counts
  (total / new / duplicate / error), the statement's balances and the lines of ``status`` (all
  by default), each with its reasons (row + fix). Writes nothing;
- ``POST imports/<id>/commit`` ``{mapping, layout, skip_errors}`` — 200 with the committed import;
  202 with the job (``job``: id) for files of more than 2,000 lines (the job tray shows the
  progress); 400 ``banking.import.has_errors`` with the error count unless ``skip_errors``; 409
  ``banking.import.not_pending``;
- ``POST imports/<id>/undo`` — 200 with the undone import, or 409 ``banking.import.in_use`` with
  ``lines`` (the coded or matched lines: id, date, amount, description, status).

Statement lines (F-02-T13): ``GET statement-lines`` with status / import / date / text filters
and the count of lines per status (the account page's "Uncoded" badge).

Errors: ``{code, detail}`` (``detail`` names the row or file and the fix); layout problems 400
``banking.statement.layout.*``; a file that isn't a statement 400/415 ``banking.statement.file.*``;
file checks as A-06 (``files.*``).

Permissions: ``accounting.banking.view`` to look, ``accounting.banking.import`` to upload, preview,
commit and undo; features ``accounting.banking.read`` / ``.write`` (every package, gap-27).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.jobs.models import JobRun
from numo9.orgsettings.locks import acting_user
from numo9.rbac.drf import requires_permission

from .api import READ, WRITE, _bank, _money
from .models import (
    BankAccount,
    StatementImport,
    StatementImportStatus,
    StatementLine,
    StatementLineStatus,
    StatementMapping,
)
from .permissions import BANKING_IMPORT, BANKING_VIEW
from .statements.errors import StatementError
from .statements.layout import DATE_FORMATS, Layout, Role, Sign
from .statements.mappings import Detection, detect_mapping, display_name, ensure_builtin_mappings
from .statements.service import (
    IN_USE,
    ImportInUse,
    LineStatus,
    Preview,
    PreviewLine,
    Upload,
    build_preview,
    create_import,
    layout_of,
    source_for,
    start_commit,
    undo_import,
)

SAMPLE_ROWS = 12  # raw rows sent for the mapping grid (title rows + header + 5 data rows, …)
PAGE = 200
MAX_PAGE = 1000


def _refused(error: StatementError) -> Response:
    body: dict[str, Any] = {"code": error.code, "detail": error.text}
    if isinstance(error, ImportInUse):
        body["lines"] = [
            {
                "id": str(line.public_id),
                "date": line.date,
                "amount": _money(line.amount),
                "description": line.description,
                "status": line.status,
            }
            for line in error.lines
        ]
    body.update({k: v for k, v in error.error_params.items() if k == "count"})
    return Response(body, status=error.status_code)


def import_row(batch: StatementImport, in_use: int | None = None) -> dict[str, Any]:
    person = batch.created_by
    row: dict[str, Any] = {
        "id": str(batch.public_id),
        "bank_account": str(batch.bank_account.public_id),
        "file_name": batch.file_name,
        "file_format": batch.file_format,
        "source": batch.source_name,
        "status": batch.status,
        "status_label": str(StatementImportStatus(batch.status).label),
        "mapping": (
            {
                "id": str(batch.statement_mapping.public_id),
                "name": display_name(batch.statement_mapping),
            }
            if batch.statement_mapping_id and batch.statement_mapping is not None
            else None
        ),
        "counts": {
            "total": batch.lines_total,
            "new": batch.lines_new,
            "duplicate": batch.lines_duplicate,
            "error": batch.lines_error,
        },
        "created_at": batch.created_at,
        "created_by": {"name": person.name or person.email} if person is not None else None,
        "committed_at": batch.committed_at,
        "undone_at": batch.undone_at,
    }
    if in_use is not None:
        row["in_use"] = in_use
        row["can_undo"] = batch.status == StatementImportStatus.COMMITTED and in_use == 0
    return row


def _import(account_public_id: Any, public_id: Any) -> StatementImport:
    bank = _bank(account_public_id)
    found: StatementImport | None = (
        StatementImport.objects.select_related(
            "bank_account", "file", "statement_mapping", "created_by"
        )
        .filter(public_id=public_id, bank_account=bank)
        .first()
    )
    if found is None:
        raise NotFound(_("That statement import doesn't exist."))
    return found


def _mapping_row(mapping: StatementMapping, score: float | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(mapping.public_id),
        "name": display_name(mapping),
        "institution": mapping.institution,
        "builtin": mapping.is_builtin,
        "layout": mapping.layout().as_dict(),
    }
    if score is not None:
        row["score"] = score
    return row


def _choices() -> dict[str, Any]:
    return {
        "roles": [str(r) for r in Role],
        "signs": [str(s) for s in Sign],
        "date_formats": list(DATE_FORMATS),
    }


def upload_body(upload: Upload) -> dict[str, Any]:
    parsed = upload.source.parsed
    body: dict[str, Any] = {
        "import": import_row(upload.statement_import),
        "format": parsed.format,
        "encoding": parsed.encoding,
        "delimiter": parsed.delimiter,
        "warnings": list(parsed.warnings),
        "tabular": parsed.table is not None,
        "lines": upload.statement_import.lines_total,
    }
    if parsed.table is not None:
        detection: Detection | None = upload.detection
        body["sample"] = {
            "rows": [
                {"row": r.number, "cells": list(r.cells)} for r in parsed.table.rows[:SAMPLE_ROWS]
            ],
            "width": parsed.table.width,
        }
        body["layout"] = upload.source.layout.as_dict() if upload.source.layout else None
        body["mapping"] = (
            _mapping_row(detection.mapping, detection.score)
            if detection is not None and detection.mapping is not None
            else None
        )
        scores = {c.mapping.pk: c.score for c in detection.candidates} if detection else {}
        body["mappings"] = [_mapping_row(m, scores.get(m.pk)) for m in upload.mappings]
        body["date_formats"] = list(detection.date_formats) if detection else []
        body["date_ambiguous"] = bool(detection and detection.date_ambiguous)
        body["choices"] = _choices()
    return body


def _resolve_layout(
    batch: StatementImport, data: dict[str, Any]
) -> tuple[Layout | None, StatementMapping | None]:
    """The layout of the request: ``layout`` edited in the wizard, else the saved ``mapping``,
    else the import's detected one. ``(None, None)`` for OFX files."""
    mapping: StatementMapping | None = None
    if data.get("mapping"):
        mapping = StatementMapping.objects.filter(
            public_id=data["mapping"], deleted_at__isnull=True
        ).first()
        if mapping is None:
            raise serializers.ValidationError({"mapping": [_("That mapping doesn't exist.")]})
    elif batch.statement_mapping_id:
        mapping = batch.statement_mapping
    if data.get("layout"):
        return Layout.from_dict(data["layout"]), mapping
    if mapping is not None and data.get("mapping"):
        return mapping.layout(), mapping
    return layout_of(batch), mapping


def line_row(item: PreviewLine) -> dict[str, Any]:
    line = item.line
    return {
        "row": line.row,
        "date": line.date,
        "amount": _money(line.amount),
        "description": line.description,
        "payee": line.payee,
        "reference": line.reference,
        "fitid": line.fitid,
        "status": item.status.value,
        "reasons": [{"code": r.code, "message": r.message()} for r in item.reasons],
    }


def balances_row(preview: Preview) -> dict[str, Any]:
    def one(balance: Any) -> dict[str, Any] | None:
        return {"amount": _money(balance.amount), "date": balance.date} if balance else None

    return {"opening": one(preview.balances.opening), "closing": one(preview.balances.closing)}


class LayoutSerializer(serializers.Serializer[Any]):
    mapping = serializers.UUIDField(required=False, allow_null=True)
    layout = serializers.DictField(required=False, allow_null=True)


class PreviewSerializer(LayoutSerializer):
    status = serializers.ChoiceField(
        choices=[s.value for s in LineStatus], required=False, allow_null=True
    )
    offset = serializers.IntegerField(required=False, min_value=0, default=0)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=MAX_PAGE, default=PAGE)


class CommitSerializer(LayoutSerializer):
    skip_errors = serializers.BooleanField(required=False, default=False)


class UploadSerializer(serializers.Serializer[Any]):
    file = serializers.FileField()


class StatementImportListView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    queryset = BankAccount._base_manager.none()  # tenant sweep: rows of BankAccount

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_account_imports_list", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        bank = _bank(public_id)
        imports: QuerySet[StatementImport] = (
            StatementImport.objects.filter(bank_account=bank)
            .select_related("bank_account", "statement_mapping", "created_by")
            .annotate(in_use=Count("lines", filter=Q(lines__status__in=IN_USE)))
            .order_by("-created_at", "-pk")
        )
        return Response(
            {"results": [import_row(b, b.in_use) for b in imports[:100]]}  # type: ignore[attr-defined]
        )

    @requires_permission(BANKING_IMPORT.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_account_imports_upload",
        summary="Upload a statement file (CSV, XLSX, OFX, QFX, QBO): what was detected",
        request={"multipart/form-data": UploadSerializer},
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        bank = _bank(public_id)
        incoming = UploadSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        upload = incoming.validated_data["file"]
        from numo9.files.services import check_name_and_size

        check_name_and_size(upload.name, upload.size)  # before reading 25 MB+ into memory
        try:
            created = create_import(bank, upload.read(), upload.name, user=acting_user())
        except StatementError as error:
            return _refused(error)
        return Response(upload_body(created), status=status.HTTP_201_CREATED)


class StatementImportDetailView(APIView):
    queryset = StatementImport._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="bank_account_imports_read", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, account_public_id: Any, public_id: Any) -> Response:
        batch = _import(account_public_id, public_id)
        body: dict[str, Any] = {"import": import_row(batch)}
        if batch.status == StatementImportStatus.PENDING and batch.file_id:
            try:
                source = source_for(batch)
                mappings = tuple(ensure_builtin_mappings(batch.organisation))
                parsed = source.parsed
                detection = (
                    detect_mapping(parsed.table, mappings, batch.statement_mapping)
                    if parsed.table is not None
                    else None
                )
                body = upload_body(Upload(batch, source, detection, mappings))
                if parsed.table is not None and batch.mapping:
                    body["layout"] = batch.mapping
            except StatementError as error:
                body["problem"] = {"code": error.code, "detail": error.text}
        return Response(body)


class StatementImportPreviewView(APIView):
    parser_classes = (JSONParser,)
    queryset = StatementImport._base_manager.none()

    @requires_permission(BANKING_IMPORT.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_account_imports_preview",
        summary="Dry run: new, duplicate and error lines with reasons; nothing is written",
        request=PreviewSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, account_public_id: Any, public_id: Any) -> Response:
        batch = _import(account_public_id, public_id)
        incoming = PreviewSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = incoming.validated_data
        try:
            layout, mapping = _resolve_layout(batch, data)
            preview = build_preview(batch.bank_account, source_for(batch, layout))
        except StatementError as error:
            return _refused(error)
        wanted = data.get("status")
        lines = [p for p in preview.lines if not wanted or p.status == wanted]
        page = lines[data["offset"] : data["offset"] + data["limit"]]
        return Response(
            {
                "import": import_row(batch),
                "counts": preview.counts,
                "balances": balances_row(preview),
                "warnings": list(preview.warnings),
                "layout": layout.as_dict() if layout else None,
                "mapping": _mapping_row(mapping) if mapping is not None else None,
                "count": len(lines),
                "results": [line_row(p) for p in page],
            }
        )


class StatementImportCommitView(APIView):
    parser_classes = (JSONParser,)
    queryset = StatementImport._base_manager.none()

    @requires_permission(BANKING_IMPORT.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_account_imports_commit",
        summary="Import the new lines (in the background for files of more than 2,000 lines)",
        request=CommitSerializer,
        responses={200: OpenApiTypes.OBJECT, 202: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, account_public_id: Any, public_id: Any) -> Response:
        batch = _import(account_public_id, public_id)
        incoming = CommitSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = incoming.validated_data
        try:
            layout, mapping = _resolve_layout(batch, data)
            source = source_for(batch, layout)
            done, run = start_commit(
                batch, source, skip_errors=data["skip_errors"], mapping=mapping, user=acting_user()
            )
        except StatementError as error:
            return _refused(error)
        done = _import(account_public_id, public_id)
        body = {"import": import_row(done, 0 if run is None else None)}
        if run is not None:
            return Response({**body, "job": _job(run)}, status=status.HTTP_202_ACCEPTED)
        return Response(body)


def _job(run: JobRun) -> dict[str, Any]:
    return {"id": str(run.public_id), "status": run.status}


class StatementImportUndoView(APIView):
    queryset = StatementImport._base_manager.none()

    @requires_permission(BANKING_IMPORT.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="bank_account_imports_undo",
        summary="Undo an import: remove its lines unless some are coded or matched (409)",
        request=None,
        responses={200: OpenApiTypes.OBJECT, 409: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, account_public_id: Any, public_id: Any) -> Response:
        batch = _import(account_public_id, public_id)
        try:
            undone = undo_import(batch, user=acting_user())
        except StatementError as error:
            return _refused(error)
        return Response({"import": import_row(undone, 0)})


# ---- statement lines (F-02-T13) -----------------------------------------------------------------

LINE_STATUSES = [s.value for s in StatementLineStatus]


def statement_line_row(line: StatementLine) -> dict[str, Any]:
    batch = line.statement_import
    return {
        "id": str(line.public_id),
        "date": line.date,
        "amount": _money(line.amount),
        "description": line.description,
        "payee": line.payee,
        "reference": line.reference,
        "fitid": line.fitid,
        "status": line.status,
        "status_label": str(StatementLineStatus(line.status).label),
        "import": {"id": str(batch.public_id), "file_name": batch.file_name} if batch else None,
    }


class StatementLineListView(APIView):
    """``GET bank-accounts/<id>/statement-lines`` — the account's statement lines, newest first:
    ``?status=uncoded|coded|matched|ignored``, ``import=<id>``, ``from`` / ``to`` (dates), ``q``
    (description, payee or reference), ``limit`` (≤ 500) / ``offset``. ``counts`` — lines per
    status over the other filters (the "Uncoded" badge is ``counts.uncoded``)."""

    queryset = BankAccount._base_manager.none()

    @requires_permission(BANKING_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="bank_account_statement_lines", responses={200: OpenApiTypes.OBJECT}
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        bank = _bank(public_id)
        params = request.query_params
        lines: QuerySet[StatementLine] = StatementLine.objects.filter(bank_account=bank)
        try:
            if params.get("from"):
                lines = lines.filter(date__gte=dt.date.fromisoformat(params["from"]))
            if params.get("to"):
                lines = lines.filter(date__lte=dt.date.fromisoformat(params["to"]))
            limit = min(max(int(params.get("limit", 100)), 1), 500)
            offset = max(int(params.get("offset", 0)), 0)
        except ValueError:
            raise serializers.ValidationError(
                {"filters": [_("Check the dates (YYYY-MM-DD) and the page size.")]}
            ) from None
        if params.get("import"):
            lines = lines.filter(statement_import__public_id=params["import"])
        if params.get("q"):
            text = params["q"].strip()
            lines = lines.filter(
                Q(description__icontains=text)
                | Q(payee__icontains=text)
                | Q(reference__icontains=text)
            )
        counts = dict.fromkeys(LINE_STATUSES, 0)
        for row in lines.values("status").annotate(n=Count("pk")).order_by():
            counts[row["status"]] = row["n"]
        wanted = params.get("status")
        if wanted:
            if wanted not in LINE_STATUSES:
                raise serializers.ValidationError({"status": [_("Unknown status.")]})
            lines = lines.filter(status=wanted)
        total = lines.count()
        page = lines.select_related("statement_import").order_by("-date", "-pk")[
            offset : offset + limit
        ]
        return Response(
            {
                "counts": {"all": sum(counts.values()), **counts},
                "count": total,
                "results": [statement_line_row(line) for line in page],
            }
        )
