"""Internal job dashboard of the platform console — API (A-08-T08), mounted under ``/api/v1/``.

Platform routes (no organisation; ``platform.jobs.view`` to look, ``platform.jobs.manage`` to
act — the platform owner has both, platform support may look):

- ``platform/jobs/overview`` — GET queues (messages waiting in the broker, jobs running, jobs
  waiting for a retry) and job counts by status: everything still going, failures and successes
  of the last 24 hours, every dead letter;
- ``platform/jobs`` — GET job runs of every organisation and the platform, newest first, with
  ``status``, ``queue``, ``type``, ``organisation`` (public id) and ``q`` (job id, task, error
  code or organisation name) filters, ``limit`` (≤ 100) / ``offset``; ``count`` is the total;
- ``platform/jobs/<id>`` — GET one run with its technical detail (arguments scrubbed, worker,
  Celery task id, idempotency key, error detail);
- ``platform/jobs/<id>/retry`` — POST send a failed or dead run again (``retry_run``);
- ``platform/jobs/purge`` — POST delete failed or dead runs (the dead-letter queue):
  ``{"ids": [...]}`` for chosen runs, or ``{"status": "dead"|"failed", "older_than_days": n}``;
  never a run that succeeded or is still going. Broker queues are never purged from here: their
  messages belong to queued runs, which would never run.

Every retry and purge is logged (``numo9.jobs``: who, what, how many) until the audit log (A-04)
records platform actions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any, cast

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.i18n import errors
from numo9.i18n.errors import api_error, error_detail
from numo9.rbac.drf import requires_permission
from numo9.rbac.permissions import JOBS_MANAGE, JOBS_VIEW
from numo9.security.scrubbing import scrub

from .models import ACTIVE, RETRYABLE, JobRun, JobStatus
from .queues import QUEUE_NAMES
from .retry import retry_run
from .serializers import JobSerializer

logger = logging.getLogger("numo9.jobs")

WINDOW = timedelta(hours=24)
MAX_LIMIT = 100


def queue_depths() -> dict[str, int | None]:
    """Messages waiting in the broker per queue (None when the broker cannot be reached)."""
    from numo9.celery import app

    depths: dict[str, int | None] = dict.fromkeys(QUEUE_NAMES)
    try:
        with app.connection_for_read(connect_timeout=2) as connection:
            channel = connection.default_channel
            for name in QUEUE_NAMES:
                try:
                    depths[name] = int(channel.queue_declare(name, passive=True).message_count)
                except Exception:  # a queue no worker has declared yet holds nothing
                    depths[name] = 0
                    channel = connection.channel()  # a refused declare may close the channel
    except Exception as exc:  # broker down: the dashboard still shows the database side
        logger.warning("jobs.console broker unreachable: %s", type(exc).__name__)
        return dict.fromkeys(QUEUE_NAMES)
    return depths


def overview() -> dict[str, Any]:
    runs = JobRun.platform_runs
    since = timezone.now() - WINDOW
    by_queue: dict[str, dict[str, Any]] = {
        row["queue"]: dict(row)
        for row in runs.filter(status__in=ACTIVE)
        .values("queue")
        .annotate(
            running=Count("pk", filter=Q(status=JobStatus.RUNNING)),
            retrying=Count("pk", filter=Q(status=JobStatus.RETRYING)),
            queued=Count("pk", filter=Q(status=JobStatus.QUEUED)),
        )
        .order_by()
    }
    empty: dict[str, Any] = {}
    depths = queue_depths()
    queues = [
        {
            "name": name,
            "waiting_messages": depths[name],
            "queued": by_queue.get(name, empty).get("queued", 0),
            "running": by_queue.get(name, empty).get("running", 0),
            "retrying": by_queue.get(name, empty).get("retrying", 0),
        }
        for name in QUEUE_NAMES
    ]
    active = dict(
        runs.filter(status__in=ACTIVE).values_list("status").annotate(n=Count("pk")).order_by()
    )
    recent = dict(
        runs.filter(finished_at__gte=since, status__in=[JobStatus.SUCCEEDED, JobStatus.FAILED])
        .values_list("status")
        .annotate(n=Count("pk"))
        .order_by()
    )
    return {
        "queues": queues,
        "counts": {
            "queued": active.get(JobStatus.QUEUED, 0),
            "running": active.get(JobStatus.RUNNING, 0),
            "retrying": active.get(JobStatus.RETRYING, 0),
            "succeeded_24h": recent.get(JobStatus.SUCCEEDED, 0),
            "failed_24h": recent.get(JobStatus.FAILED, 0),
            "dead": runs.filter(status=JobStatus.DEAD).count(),
        },
    }


# ---- serializers -------------------------------------------------------------------------------


class QueueSerializer(serializers.Serializer[Any]):
    name = serializers.CharField()
    waiting_messages = serializers.IntegerField(allow_null=True)
    queued = serializers.IntegerField()
    running = serializers.IntegerField()
    retrying = serializers.IntegerField()


class CountsSerializer(serializers.Serializer[Any]):
    queued = serializers.IntegerField()
    running = serializers.IntegerField()
    retrying = serializers.IntegerField()
    succeeded_24h = serializers.IntegerField()
    failed_24h = serializers.IntegerField()
    dead = serializers.IntegerField()


class OverviewSerializer(serializers.Serializer[Any]):
    queues = QueueSerializer(many=True)
    counts = CountsSerializer()


class JobOrganisationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    name = serializers.CharField()


class JobStarterSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    name = serializers.CharField()
    email = serializers.EmailField()


class ConsoleJobSerializer(JobSerializer):
    organisation = JobOrganisationSerializer(allow_null=True, read_only=True)
    created_by = JobStarterSerializer(allow_null=True, read_only=True)
    payload = serializers.SerializerMethodField()
    error_detail = serializers.CharField(read_only=True)

    class Meta(JobSerializer.Meta):
        fields = [
            *JobSerializer.Meta.fields,
            "organisation",
            "created_by",
            "queue",
            "payload",
            "error_detail",
            "worker",
            "celery_task_id",
            "idempotency_key",
            "max_retries",
        ]
        read_only_fields = fields

    def get_payload(self, run: JobRun) -> dict[str, Any]:
        cleaned: dict[str, Any] = scrub(run.payload)  # SIN, card, bank numbers, secrets
        return cleaned


class ConsoleJobPageSerializer(serializers.Serializer[Any]):
    count = serializers.IntegerField()
    results = ConsoleJobSerializer(many=True)


class PurgeSerializer(serializers.Serializer[Any]):
    ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=500)
    status = serializers.ChoiceField(
        choices=[JobStatus.DEAD, JobStatus.FAILED], required=False, allow_null=True
    )
    older_than_days = serializers.IntegerField(required=False, min_value=0, max_value=3650)


class PurgeResultSerializer(serializers.Serializer[Any]):
    deleted = serializers.IntegerField()


# ---- views -------------------------------------------------------------------------------------


def _user(request: Request) -> User:
    return cast(User, request.user)


def _run(public_id: Any) -> JobRun:
    run = (
        JobRun.platform_runs.select_related("organisation", "created_by")
        .filter(public_id=public_id)
        .first()
    )
    if run is None:
        raise NotFound
    return run


class ConsoleOverviewView(APIView):
    @requires_permission(JOBS_VIEW.key)
    @extend_schema(
        operation_id="console_jobs_overview",
        summary="Queues and job counts (platform console)",
        responses=OverviewSerializer,
    )
    def get(self, request: Request) -> Response:
        return Response(OverviewSerializer(overview()).data)


class ConsoleJobListView(APIView):
    @requires_permission(JOBS_VIEW.key)
    @extend_schema(
        operation_id="console_jobs_list",
        summary="Job runs of every organisation and the platform (platform console)",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, enum=JobStatus.values),
            OpenApiParameter("queue", OpenApiTypes.STR, enum=list(QUEUE_NAMES)),
            OpenApiParameter("type", OpenApiTypes.STR, description="Task name"),
            OpenApiParameter("organisation", OpenApiTypes.UUID),
            OpenApiParameter("q", OpenApiTypes.STR, description="Search"),
            OpenApiParameter("limit", OpenApiTypes.INT),
            OpenApiParameter("offset", OpenApiTypes.INT),
        ],
        responses=ConsoleJobPageSerializer,
    )
    def get(self, request: Request) -> Response:
        params = request.query_params
        runs = JobRun.platform_runs.select_related("organisation", "created_by")
        if params.get("status") in JobStatus.values:
            runs = runs.filter(status=params["status"])
        if params.get("queue"):
            runs = runs.filter(queue=params["queue"])
        if params.get("type"):
            runs = runs.filter(task_name=params["type"])
        if params.get("organisation"):
            try:
                organisation = uuid.UUID(params["organisation"])
            except ValueError as exc:
                detail = error_detail(errors.JOB_CONSOLE_ORGANISATION)
                raise serializers.ValidationError({"organisation": [detail]}) from exc
            runs = runs.filter(organisation__public_id=organisation)
        if search := params.get("q", "").strip():
            text = (
                Q(task_name__icontains=search)
                | Q(error_code__icontains=search)
                | Q(organisation__name__icontains=search)
            )
            if len(search) >= 8 and all(c in "0123456789abcdef-" for c in search.lower()):
                text |= Q(public_id__startswith=search.lower())  # reference from the tray
            runs = runs.filter(text)
        limit = min(MAX_LIMIT, max(1, _int(params.get("limit"), 50)))
        offset = max(0, _int(params.get("offset"), 0))
        runs = runs.order_by("-created_at", "-pk")
        page = {"count": runs.count(), "results": list(runs[offset : offset + limit])}
        return Response(ConsoleJobPageSerializer(page).data)


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


class ConsoleJobDetailView(APIView):
    @requires_permission(JOBS_VIEW.key)
    @extend_schema(
        operation_id="console_jobs_get",
        summary="One job run with its technical detail (platform console)",
        responses=ConsoleJobSerializer,
    )
    def get(self, request: Request, public_id: Any) -> Response:
        return Response(ConsoleJobSerializer(_run(public_id)).data)


class ConsoleJobRetryView(APIView):
    @requires_permission(JOBS_MANAGE.key)
    @extend_schema(
        operation_id="console_jobs_retry",
        summary="Send a failed or dead job run again (platform console)",
        request=None,
        responses={202: ConsoleJobSerializer},
    )
    def post(self, request: Request, public_id: Any) -> Response:
        run = retry_run(_run(public_id), by=_user(request))
        return Response(ConsoleJobSerializer(_run(run.public_id)).data, status=202)


class ConsolePurgeView(APIView):
    @requires_permission(JOBS_MANAGE.key)
    @extend_schema(
        operation_id="console_jobs_purge",
        summary="Delete failed or dead job runs — the dead-letter queue (platform console)",
        request=PurgeSerializer,
        responses=PurgeResultSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = PurgeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        if not data.get("ids") and not data.get("status"):
            raise api_error(errors.JOB_PURGE_FILTER)  # never "everything" by accident
        runs = JobRun.platform_runs.filter(status__in=RETRYABLE)  # never succeeded or going
        if data.get("ids"):
            runs = runs.filter(public_id__in=data["ids"])
        if data.get("status"):
            runs = runs.filter(status=data["status"])
        if data.get("older_than_days") is not None:
            cutoff = timezone.now() - timedelta(days=data["older_than_days"])
            runs = runs.filter(finished_at__lt=cutoff)
        deleted = runs.delete()[0]
        logger.info(
            "jobs.purged %s",
            deleted,
            extra={
                "job": {
                    "purged": deleted,
                    "by": str(_user(request).public_id),
                    "filter": {k: str(v) for k, v in data.items() if k != "ids"},
                    "ids": len(data.get("ids") or []),
                }
            },
        )
        return Response(PurgeResultSerializer({"deleted": deleted}).data)
