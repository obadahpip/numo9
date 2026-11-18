"""Bulk actions API (V-03-T07), under ``/api/v1/practice/bulk``.

- ``POST bulk`` ``{practice?, action, params, selection}`` — create the job and its **preview**
  (nothing is changed): ``201 {job, preview: {total, counts, lines (first 50)}}``;
- ``GET bulk/<id>`` — status and live counters (the progress drawer polls it; there is no
  server-sent stream: polling every second or two is enough for a job of a few hundred rows);
- ``POST bulk/<id>/confirm`` — apply: one row per organisation, one background job (``202``);
- ``POST bulk/<id>/cancel`` — stop before the next organisation;
- ``GET bulk/<id>/rows?outcome=…&page=…`` — the results, 100 a page, filterable by outcome;
- ``GET bulk/<id>/results.csv`` — every organisation with its outcome and reason;
- ``GET bulk/<id>/export`` — the export action's CSV/XLSX (once the job has run).

Who: a member of the practice with ``practice.directory.view`` reads the practice's jobs;
creating and confirming also need the action's practice permission (``practice.groups.manage``
for group and tags, ``practice.clients.assign`` for staff); only the person who started a job may
confirm or cancel it. Another practice's job → 404. Not organisation-scoped (tenant-sweep exempt
``^api/v1/practice/``).
"""

from __future__ import annotations

import math
import uuid
from typing import Any

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import AUTHENTICATED, checks_practice_permission, requires_permission
from numo9.rbac.resolver import has_practice_perm
from numo9.workspace.api import resolve_practice
from numo9.workspace.permissions import DIRECTORY_VIEW

from . import service
from .exports import export_file, results_csv
from .models import BulkAction, BulkJob, BulkStatus, RowOutcome

ROWS_PAGE = 100


def _denied() -> Exception:
    return api_error(errors.PERMISSION_DENIED, action=str(_view_action()))


def _view_action() -> str:
    from django.utils.translation import gettext

    return gettext("see the practice's bulk actions")


def _job(request: Request, job_id: Any) -> BulkJob:
    job = BulkJob.objects.select_related("practice", "created_by").filter(public_id=job_id).first()
    if job is None or not job.practice.members.filter(user_id=request.user.pk or 0).exists():
        raise NotFound
    if not has_practice_perm(request.user, job.practice, DIRECTORY_VIEW.key):
        raise _denied()
    return job


def _own(request: Request, job: BulkJob) -> None:
    if job.created_by_id != request.user.pk:
        raise _denied()


def job_data(job: BulkJob) -> dict[str, Any]:
    counts = job.counts()
    done = job.total - counts["pending"] if job.status != BulkStatus.PREVIEW else 0
    return {
        "id": job.public_id,
        "action": job.action,
        "action_label": BulkAction(job.action).label,
        "params": job.params,
        "status": job.status,
        "total": job.total,
        "done": done,
        "percent": math.floor(done * 100 / job.total) if job.total else 0,
        "counts": counts,
        "created_by": {"id": job.created_by.public_id, "name": job.created_by.name},
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "cancel_requested": job.cancel_requested_at is not None,
        "export_ready": job.action == BulkAction.EXPORT and job.status == BulkStatus.COMPLETED,
    }


# ---- serializers (schema) ----------------------------------------------------------------------


class BulkCountsSerializer(serializers.Serializer[Any]):
    pending = serializers.IntegerField()
    succeeded = serializers.IntegerField()
    skipped = serializers.IntegerField()
    failed = serializers.IntegerField()
    cancelled = serializers.IntegerField()


class BulkPersonSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class BulkJobSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=BulkAction.choices)
    action_label = serializers.CharField()
    params = serializers.DictField(child=serializers.JSONField())
    status = serializers.ChoiceField(choices=BulkStatus.choices)
    total = serializers.IntegerField()
    done = serializers.IntegerField()
    percent = serializers.IntegerField()
    counts = BulkCountsSerializer()
    created_by = BulkPersonSerializer()
    created_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)
    cancel_requested = serializers.BooleanField()
    export_ready = serializers.BooleanField()


class BulkOrgSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class BulkPreviewLineSerializer(serializers.Serializer[Any]):
    organisation = BulkOrgSerializer()
    status = serializers.ChoiceField(
        choices=[("change", "change"), ("no_change", "no_change"), ("skipped", "skipped")]
    )
    reason = serializers.CharField()
    message = serializers.CharField()
    before = serializers.DictField(child=serializers.JSONField())
    after = serializers.DictField(child=serializers.JSONField())


class BulkPreviewCountsSerializer(serializers.Serializer[Any]):
    change = serializers.IntegerField()
    no_change = serializers.IntegerField()
    skipped = serializers.IntegerField()


class BulkPreviewSerializer(serializers.Serializer[Any]):
    total = serializers.IntegerField()
    counts = BulkPreviewCountsSerializer()
    lines = BulkPreviewLineSerializer(many=True)


class BulkCreatedSerializer(serializers.Serializer[Any]):
    job = BulkJobSerializer()
    preview = BulkPreviewSerializer()


class BulkCreateSerializer(serializers.Serializer[Any]):
    practice = serializers.UUIDField(required=False)
    action = serializers.ChoiceField(choices=BulkAction.choices)
    params = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
    selection = serializers.DictField(
        child=serializers.JSONField(),
        help_text='{"ids": [organisation ids]} or {"query": {directory search and filters}}',
    )


class BulkRowSerializer(serializers.Serializer[Any]):
    organisation = BulkOrgSerializer()
    outcome = serializers.ChoiceField(choices=RowOutcome.choices)
    reason = serializers.CharField()
    message = serializers.CharField()
    before = serializers.DictField(child=serializers.JSONField())
    after = serializers.DictField(child=serializers.JSONField())
    processed_at = serializers.DateTimeField(allow_null=True)


class BulkRowPageSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    pages = serializers.IntegerField()
    results = BulkRowSerializer(many=True)


# ---- views -------------------------------------------------------------------------------------


class BulkJobCreateView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view + the action's (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_bulk_create",
        summary="Preview a bulk action over organisations (nothing is changed yet)",
        request=BulkCreateSerializer,
        responses={201: BulkCreatedSerializer},
    )
    def post(self, request: Request) -> Response:
        body = BulkCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        given = body.validated_data.get("practice")
        practice = resolve_practice(request, str(given) if given else None)
        if not has_practice_perm(request.user, practice, DIRECTORY_VIEW.key):
            raise _denied()
        job, result = service.create_job(
            request.user,
            practice,
            body.validated_data["action"],
            body.validated_data.get("params") or {},
            body.validated_data["selection"],
        )
        return Response({"job": job_data(job), "preview": result}, status=status.HTTP_201_CREATED)


class BulkJobDetailView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_bulk_detail",
        summary="A bulk action's status and live counters",
        responses=BulkJobSerializer,
    )
    def get(self, request: Request, job_id: uuid.UUID) -> Response:
        return Response(job_data(_job(request, job_id)))


class BulkJobConfirmView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # the starter, with the action's permission (here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_bulk_confirm",
        summary="Apply a previewed bulk action (one background job)",
        request=None,
        responses={202: BulkJobSerializer},
    )
    def post(self, request: Request, job_id: uuid.UUID) -> Response:
        job = _job(request, job_id)
        _own(request, job)
        job = service.confirm(job, request.user)
        return Response(job_data(job), status=status.HTTP_202_ACCEPTED)


class BulkJobCancelView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # the starter (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_bulk_cancel",
        summary="Stop a bulk action before the next organisation",
        request=None,
        responses=BulkJobSerializer,
    )
    def post(self, request: Request, job_id: uuid.UUID) -> Response:
        job = _job(request, job_id)
        _own(request, job)
        return Response(job_data(service.cancel(job)))


class BulkJobRowsView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_bulk_rows",
        summary="A bulk action's results, one line per organisation",
        parameters=[
            OpenApiParameter("outcome", OpenApiTypes.STR, enum=RowOutcome.values),
            OpenApiParameter("page", OpenApiTypes.INT),
        ],
        responses=BulkRowPageSerializer,
    )
    def get(self, request: Request, job_id: uuid.UUID) -> Response:
        job = _job(request, job_id)
        rows = job.rows.select_related("organisation").order_by("position")
        outcome = request.query_params.get("outcome", "")
        if outcome:
            if outcome not in RowOutcome.values:
                error = api_error(errors.WORKSPACE_BAD_FILTER, name="outcome", value=outcome[:100])
                error.extra = {"field": "outcome"}
                raise error
            rows = rows.filter(outcome=outcome)
        raw = request.query_params.get("page", "1")
        page = int(raw) if raw.isdigit() and int(raw) > 0 else 1
        count = rows.count()
        start = (page - 1) * ROWS_PAGE
        return Response(
            {
                "count": count,
                "page": page,
                "pages": max(1, math.ceil(count / ROWS_PAGE)),
                "results": [
                    {
                        "organisation": {
                            "id": r.organisation.public_id,
                            "name": r.organisation.name,
                        },
                        "outcome": r.outcome,
                        "reason": r.reason,
                        "message": r.message,
                        "before": r.before,
                        "after": r.after,
                        "processed_at": r.processed_at,
                    }
                    for r in rows[start : start + ROWS_PAGE]
                ],
            }
        )


class BulkJobResultsCsvView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_bulk_results_csv",
        summary="Every organisation of a bulk action with its outcome (CSV)",
        responses={(200, "text/csv"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, job_id: uuid.UUID) -> HttpResponse:
        job = _job(request, job_id)
        response = HttpResponse(results_csv(job), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="bulk-{job.public_id}.csv"'
        return response


class BulkJobExportView(APIView):
    required_feature = CORE

    @requires_permission(AUTHENTICATED)  # practice.directory.view (checked here)
    @checks_practice_permission(DIRECTORY_VIEW.key)
    @extend_schema(
        operation_id="practice_bulk_export",
        summary="The export action's file (CSV or XLSX)",
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, job_id: uuid.UUID) -> HttpResponse:
        job = _job(request, job_id)
        if job.action != BulkAction.EXPORT or job.status != BulkStatus.COMPLETED:
            raise NotFound
        content, kind, name = export_file(job)
        response = HttpResponse(content, content_type=kind)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response
