"""Job progress API for the job tray (A-08-T06), mounted under ``/api/v1/``.

Organisation-scoped (``/api/v1/o/<org>/…``; the organisation must be accessible, else 404). A
person sees **the jobs they started** in the organisation — nobody else's, and never platform jobs
(those are in the platform console, A-08-T08). Everyone with access may use it
(``organisation.profile.view``, which every role has); a job someone else started answers 404.

- ``jobs`` — GET the person's recent jobs, newest first: every job still going plus the last
  ``RECENT_LIMIT`` (20) of the past 24 hours (``?active=1``: only the ones still going). Sends an
  ``ETag``; a poll with ``If-None-Match`` answers ``304`` while nothing changed — the polling
  fallback of the tray;
- ``jobs/<id>`` — GET one job;
- ``jobs/<id>/retry`` — POST start a failed job again (``retry_run``: 409 ``job.not_retryable``
  unless it failed);
- ``jobs/events`` — GET a Server-Sent Events stream of the same list: a ``jobs`` event with the
  list at once and every time it changes (checked every ``JOBS_SSE_POLL_SECONDS``, 1 s), a
  comment line every 15 s to keep proxies from closing it. It ends after
  ``JOBS_SSE_MAX_SECONDS`` (25 s) — or at once when nothing is going — with a ``retry:`` hint,
  and ``EventSource`` reconnects by itself. Each event's ``id`` is the list's ETag: a reconnect
  sending ``Last-Event-ID`` gets no repeat of a list it already has.

What a job shows: type and label, status (+ label), progress (done, total, percent, note),
result link, error (code + message in the starter's language), whether it can be retried,
attempts and times. Never its arguments or the technical error detail.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any, cast

from django.conf import settings
from django.db.models import Q, QuerySet
from django.http import HttpResponseBase, StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org, org_context
from numo9.tenancy.models import Organisation

from .models import ACTIVE, JobRun
from .retry import retry_run
from .serializers import JobSerializer, job_list_data

EVERYONE_HERE = "organisation.profile.view"  # every organisation and practice role has it
RECENT_LIMIT = 20
RECENT_WINDOW = timedelta(hours=24)
HEARTBEAT_SECONDS = 15.0


def _org() -> Organisation:
    organisation = current_org()
    assert organisation is not None  # RequiresPermission answered 404 otherwise  # noqa: S101
    return organisation


def _user(request: Request) -> User:
    return cast(User, request.user)


def my_jobs(user: User, *, active_only: bool = False) -> QuerySet[JobRun]:
    """The person's jobs in the active organisation (tray order: newest first)."""
    mine = JobRun.objects.filter(created_by=user)  # organisation-scoped manager
    if active_only:
        return mine.filter(status__in=ACTIVE).order_by("-created_at")
    since = timezone.now() - RECENT_WINDOW
    return mine.filter(Q(status__in=ACTIVE) | Q(created_at__gte=since)).order_by("-created_at")


def tray_list(user: User, *, active_only: bool = False) -> list[JobRun]:
    runs = list(my_jobs(user, active_only=active_only).select_related("organisation")[:100])
    going = [r for r in runs if r.status in ACTIVE]
    done = [r for r in runs if r.status not in ACTIVE][:RECENT_LIMIT]
    return sorted([*going, *done], key=lambda r: r.created_at, reverse=True)


def etag_of(body: Any) -> str:
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    return f'"{digest[:32]}"'


def _my_job(request: Request, public_id: Any) -> JobRun:
    run = my_jobs(_user(request)).filter(public_id=public_id).first()
    if run is None:
        # Created long ago, by someone else, in another organisation or nonexistent: all 404.
        run = JobRun.objects.filter(created_by=_user(request), public_id=public_id).first()
    if run is None:
        raise NotFound
    return run


class JobListView(APIView):
    required_feature = CORE  # part of every organisation, never gated (U-01)
    serializer_class = JobSerializer  # tenant sweep: rows of JobRun

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="jobs_list",
        summary="My background jobs in the organisation (job tray)",
        parameters=[
            OpenApiParameter("active", OpenApiTypes.BOOL, description="Only jobs still going"),
        ],
        responses={200: JobSerializer(many=True), 304: OpenApiResponse(description="Unchanged")},
    )
    def get(self, request: Request, org: Any) -> Response:
        active_only = request.query_params.get("active") in {"1", "true"}
        body = job_list_data(tray_list(_user(request), active_only=active_only))
        tag = etag_of(body)
        if request.headers.get("If-None-Match") == tag:
            return Response(status=304, headers={"ETag": tag})
        return Response(body, headers={"ETag": tag, "Cache-Control": "no-cache"})


class JobDetailView(APIView):
    required_feature = CORE  # part of every organisation, never gated (U-01)
    serializer_class = JobSerializer

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="jobs_get",
        summary="One of my background jobs: status, progress, result or error",
        responses=JobSerializer,
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(JobSerializer(_my_job(request, public_id)).data)


class JobRetryView(APIView):
    required_feature = CORE  # part of every organisation, never gated (U-01)
    serializer_class = JobSerializer

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="jobs_retry",
        summary="Start one of my failed jobs again",
        request=None,
        responses={202: JobSerializer},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        run = retry_run(_my_job(request, public_id), by=_user(request))
        return Response(JobSerializer(run).data, status=202)


class EventStreamRenderer(BaseRenderer):
    """``text/event-stream`` for ``EventSource`` clients; errors are rendered as JSON text."""

    media_type = "text/event-stream"
    format = "sse"
    charset = "utf-8"

    def render(
        self, data: Any, accepted_media_type: str | None = None, renderer_context: Any = None
    ) -> bytes:
        return json.dumps(data).encode() if data is not None else b""


def sse(event: str | None = None, data: Any = None, *, event_id: str | None = None) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    if event:
        lines.append(f"event: {event}")
    if data is not None:
        lines.append(f"data: {json.dumps(data, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def job_events(organisation: Organisation, user: User, last_event_id: str | None) -> Iterator[str]:
    """The SSE body: the list now and on every change, until nothing is going or time is up."""
    poll = float(getattr(settings, "JOBS_SSE_POLL_SECONDS", 1.0))
    limit = float(getattr(settings, "JOBS_SSE_MAX_SECONDS", 25.0))
    started = last_beat = time.monotonic()
    sent_tag = last_event_id
    yield f"retry: {int(getattr(settings, 'JOBS_SSE_RETRY_MS', 2000))}\n\n"
    while True:
        with org_context(organisation):  # the request's context ended when the view returned
            runs = tray_list(user)
        body = job_list_data(runs)
        tag = etag_of(body)
        if tag != sent_tag:
            yield sse("jobs", body, event_id=tag)
            sent_tag = tag
        now = time.monotonic()
        if not any(r.status in ACTIVE for r in runs):
            yield sse("idle", {"active": 0})
            return
        if now - started >= limit:
            return
        if now - last_beat >= HEARTBEAT_SECONDS:
            yield ": keep-alive\n\n"
            last_beat = now
        time.sleep(poll)


class JobEventsView(APIView):
    required_feature = CORE  # part of every organisation, never gated (U-01)
    renderer_classes = [EventStreamRenderer, JSONRenderer]

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="jobs_events",
        summary="My jobs as a Server-Sent Events stream (job tray progress)",
        responses={(200, "text/event-stream"): OpenApiTypes.STR},
    )
    def get(self, request: Request, org: Any) -> HttpResponseBase:
        stream = job_events(_org(), _user(request), request.headers.get("Last-Event-ID"))
        response = StreamingHttpResponse(stream, content_type="text/event-stream; charset=utf-8")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # proxies must pass events through at once
        return response
