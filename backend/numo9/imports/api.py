"""Imports API (B-03-T11), under ``/api/v1/o/<org>/``: the wizard's four steps.

1. ``POST imports`` (multipart ``file``, ``entity``) — upload: the file is read once (CSV with
   its encoding detected, or XLSX values), its headers, three sample values per column, the
   suggested mapping (a saved mapping for the same headers first) and the fields to map to;
2. ``POST imports/<id>/dry-run`` ``{columns, options: {match_bn}, save_mapping_as}`` — check
   every row without writing anything: totals and the rows (``GET imports/<id>/rows?action=``);
3. ``POST imports/<id>/apply`` — import in the background (job tray), only after a dry run;
4. ``GET imports/<id>`` — status and totals; ``GET imports/<id>/errors.csv`` — every refused row
   with its column and reason, for a spreadsheet.

Also ``GET imports/template?entity=`` (an empty file with the headers, B-03-T13) and
``GET contacts/export?entity=&file_type=csv|xlsx`` (B-03-T10; not ``format``, which is DRF's
renderer switch). Contacts and people imports need
``contacts.contacts.manage`` and ``accounting.contacts.write``.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.contacts.permissions import CONTACTS_MANAGE, CONTACTS_VIEW
from numo9.files.models import MAX_FILE_SIZE
from numo9.jobs.runtime import start_job
from numo9.rbac.drf import requires_permission

from .fields import get_entity
from .mapping import as_columns, resolve, save_mapping
from .models import ImportRun, ImportRunRow, ImportRunStatus
from .parser import ImportFileError
from .runs import create_run, dry_run, sheet_of

WRITE = "accounting.contacts.write"
READ = "accounting.contacts.read"
ENTITIES = ("contacts.contact", "contacts.person")
ROWS_PAGE = 200


def _run(public_id: Any) -> ImportRun:
    found: ImportRun | None = ImportRun.objects.filter(public_id=public_id).first()
    if found is None:
        raise NotFound
    return found


def _fields(entity: str) -> list[dict[str, Any]]:
    return [
        {"key": f.key, "label": str(f.label), "required": f.required, "match_key": f.match_key}
        for f in get_entity(entity).fields
    ]


def _summary(run: ImportRun) -> dict[str, Any]:
    return {
        "id": str(run.public_id),
        "entity": run.entity,
        "filename": run.filename,
        "status": run.status,
        "rows": len(run.cells),
        "headers": run.headers,
        "columns": run.columns,
        "options": run.options,
        "counts": run.counts,
        "job": str(run.job_id) if run.job_id else None,
        "applied_at": run.applied_at,
    }


def _row(row: ImportRunRow) -> dict[str, Any]:
    return {
        "row": row.row,
        "key": row.key,
        "label": row.label,
        "action": row.action,
        "changes": row.changes,
        "errors": row.errors,
    }


class UploadSerializer(serializers.Serializer[Any]):
    entity = serializers.ChoiceField(choices=[(e, e) for e in ENTITIES])
    file = serializers.FileField()


class ImportUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    queryset = ImportRun._base_manager.none()  # tenant sweep: rows of ImportRun

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="imports_upload",
        summary="Upload a CSV or XLSX file: headers, samples and the suggested mapping",
        request={"multipart/form-data": UploadSerializer},
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = UploadSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        upload = incoming.validated_data["file"]
        if upload.size > MAX_FILE_SIZE:
            raise ValidationError(
                {
                    "file": [
                        _("'%(name)s' is %(size)s MB. The limit is 25 MB per file.")
                        % {"name": upload.name, "size": upload.size // (1024 * 1024)}
                    ]
                }
            )
        entity = incoming.validated_data["entity"]
        try:
            run = create_run(entity, upload.read(), upload.name, actor=request.user)
        except (ImportFileError, DjangoValidationError) as error:
            raise ValidationError({"file": [str(m) for m in error.messages]}) from None
        suggestions = resolve(entity, run.headers)
        sheet = sheet_of(run)
        body = _summary(run)
        body["columns"] = as_columns(suggestions)
        body["suggestions"] = [
            {"header": s.header, "field": s.field, "confidence": str(s.confidence)}
            for s in suggestions
        ]
        body["samples"] = {h: sheet.samples(h) for h in run.headers}
        body["fields"] = _fields(entity)
        return Response(body, status=status.HTTP_201_CREATED)


class ImportDetailView(APIView):
    queryset = ImportRun._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="imports_get", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        run = _run(public_id)
        body = _summary(run)
        body["fields"] = _fields(run.entity)
        return Response(body)


class DryRunSerializer(serializers.Serializer[Any]):
    columns = serializers.DictField(child=serializers.CharField(allow_blank=True))
    options = serializers.DictField(required=False)
    save_mapping_as = serializers.CharField(required=False, allow_blank=True, max_length=100)


class ImportDryRunView(APIView):
    parser_classes = (JSONParser,)
    queryset = ImportRun._base_manager.none()

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="imports_dry_run",
        summary="Check every row with this mapping; nothing is written",
        request=DryRunSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        run = _run(public_id)
        incoming = DryRunSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        if run.status in (ImportRunStatus.APPLYING, ImportRunStatus.APPLIED):
            raise ValidationError({"non_field_errors": [_("This file was already imported.")]})
        options = {"match_bn": bool((incoming.validated_data.get("options") or {}).get("match_bn"))}
        if run.entity != "contacts.contact":
            options = {}
        try:
            report = dry_run(run, incoming.validated_data["columns"], options)
        except DjangoValidationError as error:
            raise ValidationError({"columns": [str(m) for m in error.messages]}) from None
        name = (incoming.validated_data.get("save_mapping_as") or "").strip()
        if name:
            try:
                save_mapping(run.entity, name, run.columns, user=request.user)
            except DjangoValidationError as error:
                raise ValidationError(
                    {"save_mapping_as": [str(m) for m in error.messages]}
                ) from None
        rows = ImportRunRow.objects.filter(run=run)[:ROWS_PAGE]
        return Response(
            {**_summary(run), "counts": report.counts, "results": [_row(r) for r in rows]}
        )


class ImportRowsView(APIView):
    queryset = ImportRun._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="imports_rows",
        parameters=[
            OpenApiParameter("action", str, enum=["create", "update", "unchanged", "error"]),
            OpenApiParameter("offset", int),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        run = _run(public_id)
        rows = ImportRunRow.objects.filter(run=run)
        if request.query_params.get("action"):
            rows = rows.filter(action=request.query_params["action"])
        try:
            offset = max(0, int(request.query_params.get("offset") or 0))
        except ValueError:
            offset = 0
        count = rows.count()
        page = rows[offset : offset + ROWS_PAGE]
        return Response(
            {
                "results": [_row(r) for r in page],
                "count": count,
                "next_offset": offset + ROWS_PAGE if offset + ROWS_PAGE < count else None,
            }
        )


class ImportApplyView(APIView):
    queryset = ImportRun._base_manager.none()

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="imports_apply",
        summary="Import the checked file in the background (job tray)",
        request=None,
        responses={202: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .tasks import apply_import

        run = _run(public_id)
        if run.status != ImportRunStatus.REVIEWED:
            raise ValidationError(
                {"non_field_errors": [_("Check the file first (dry run), then import it.")]}
            )
        ImportRun.objects.filter(pk=run.pk).update(status=ImportRunStatus.APPLYING)
        job = start_job(
            apply_import,
            organisation=run.organisation,
            key=f"import:{run.public_id}",
            created_by=request.user,
            run_id=str(run.public_id),
            user_id=request.user.pk,
        )
        ImportRun.objects.filter(pk=run.pk).update(job_id=job.public_id)
        run.refresh_from_db()
        return Response(_summary(run), status=status.HTTP_202_ACCEPTED)


class ImportErrorsView(APIView):
    queryset = ImportRun._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="imports_errors_csv", responses={200: OpenApiTypes.BINARY})
    def get(self, request: Request, org: Any, public_id: Any) -> HttpResponse:
        from .report import Action, ImportReport, RowError, RowResult

        run = _run(public_id)
        report = ImportReport(run.entity, applied=run.status == ImportRunStatus.APPLIED)
        for row in ImportRunRow.objects.filter(run=run, action=Action.ERROR):
            result = RowResult(row.row, row.key, Action.ERROR)
            result.errors = [RowError(e["field"], e["code"], e["message"]) for e in row.errors]
            report.rows.append(result)
        labels = {f["key"]: f["label"] for f in _fields(run.entity)}
        response = HttpResponse(report.errors_csv(labels), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="import-errors.csv"'
        return response


class ImportTemplateView(APIView):
    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="imports_template",
        parameters=[OpenApiParameter("entity", str, enum=list(ENTITIES))],
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request: Request, org: Any) -> HttpResponse:
        from numo9.contacts.export import template_csv

        entity = request.query_params.get("entity", "contacts.contact")
        if entity not in ENTITIES:
            raise ValidationError({"entity": [_("Unknown record type.")]})
        response = HttpResponse(template_csv(entity), content_type="text/csv; charset=utf-8")
        name = "people-template.csv" if entity == "contacts.person" else "contacts-template.csv"
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response


class ContactExportView(APIView):
    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_export",
        parameters=[
            OpenApiParameter("entity", str, enum=list(ENTITIES)),
            OpenApiParameter("file_type", str, enum=["csv", "xlsx"]),
        ],
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request: Request, org: Any) -> HttpResponse:
        from numo9.contacts.export import export_csv, export_xlsx

        entity = request.query_params.get("entity", "contacts.contact")
        kind = request.query_params.get("file_type", "csv")
        if entity not in ENTITIES or kind not in ("csv", "xlsx"):
            raise ValidationError({"file_type": [_("Choose CSV or XLSX.")]})
        stem = "people" if entity == "contacts.person" else "contacts"
        if kind == "xlsx":
            response = HttpResponse(
                export_xlsx(entity),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            response = HttpResponse(export_csv(entity), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{stem}.{kind}"'
        return response
