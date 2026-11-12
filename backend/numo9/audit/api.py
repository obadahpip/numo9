"""Audit log API (A-04-T07), mounted under ``/api/v1/``.

Organisation log (``/api/v1/o/<org>/audit/…``; ``audit.log.view``):

- ``audit/events`` — GET the global viewer's list: the filters of ``query.AuditQuery`` (default
  range: the last 90 days in the organisation's time zone), newest first, cursor pages
  (``cursor``, ``limit`` ≤ 200, default 50). The answer names the range applied and the viewer's
  display preferences (language, 12/24-hour time, time zone) for the screen;
- ``audit/events/<id>`` — GET one event with its full values and hashes;
- ``audit/records/<type>/<id>`` — GET a record's whole history (every date), newest first, cursor
  pages: the record history drawer of detail pages. 404 when the record has no history here;
- ``audit/filters`` — GET the choices of the viewer's filters: the people and record types that
  appear in the log, and the actions.

Platform log (``/api/v1/platform/audit/events``; ``platform.audit.view``): every event —
sign-ins, 2FA and practice events (no organisation) and every organisation's — with the same
filters plus ``organisation`` (public id).
"""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

from .models import AuditEvent
from .permissions import AUDIT_VIEW, PLATFORM_AUDIT_VIEW
from .presenter import VERB_LABELS, event_data, type_label
from .query import AuditQuery, limit_of, loose_distinct, page, time_zone_of
from .serializers import (
    AuditEventDetailSerializer,
    AuditFiltersSerializer,
    AuditHistorySerializer,
    AuditPageSerializer,
)

SELECT = ("actor_user", "impersonator")

FILTER_PARAMETERS = [
    OpenApiParameter("from", OpenApiTypes.DATE, description="First day (default: 89 days ago)"),
    OpenApiParameter("to", OpenApiTypes.DATE, description="Last day (default: today)"),
    OpenApiParameter("user", OpenApiTypes.STR, description="User public ids, or 'system'"),
    OpenApiParameter("type", OpenApiTypes.STR, description="Record types (model labels)"),
    OpenApiParameter("action", OpenApiTypes.STR, description="Actions, or verbs (created…)"),
    OpenApiParameter("object_type", OpenApiTypes.STR, description="One record: its type"),
    OpenApiParameter("object_id", OpenApiTypes.STR, description="One record: its public id"),
    OpenApiParameter("batch", OpenApiTypes.UUID, description="One bulk operation"),
    OpenApiParameter("q", OpenApiTypes.STR, description="Text in record, person or action"),
]
PAGE_PARAMETERS = [
    OpenApiParameter("cursor", OpenApiTypes.STR, description="From the previous page's 'next'"),
    OpenApiParameter("limit", OpenApiTypes.INT, description="Events per page, 1–200 (50)"),
]


def _org() -> Organisation:
    organisation = current_org()
    assert organisation is not None  # RequiresPermission answered 404 otherwise  # noqa: S101
    return organisation


def viewer(request: Request, organisation: Organisation | None) -> dict[str, str]:
    """The viewer's display preferences: dates and times are shown their way (A-04-T12)."""
    user = cast(User, request.user)
    return {
        "locale": user.locale,
        "time_format": user.time_format,
        "time_zone": time_zone_of(organisation).key,
    }


def org_events() -> QuerySet[AuditEvent]:
    return AuditEvent.objects.select_related(*SELECT)  # organisation-scoped manager


def list_body(
    request: Request, events: QuerySet[AuditEvent], query: AuditQuery, org: Organisation | None
) -> dict[str, Any]:
    rows, cursor = page(
        query.apply(events), request.query_params.get("cursor"), limit_of(request.query_params)
    )
    described = query.describe()
    return {
        "results": [event_data(e) for e in rows],
        "next": cursor,
        "range": {k: described[k] for k in ("from", "to", "default", "time_zone")},
        "viewer": viewer(request, org),
    }


class AuditEventListView(APIView):
    queryset = AuditEvent.platform_events.none()  # tenant sweep: rows of AuditEvent

    @requires_permission(AUDIT_VIEW.key)
    @extend_schema(
        operation_id="audit_events_list",
        summary="The organisation's audit log (default: last 90 days), newest first",
        parameters=FILTER_PARAMETERS + PAGE_PARAMETERS,
        responses=AuditPageSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = _org()
        query = AuditQuery.from_params(request.query_params, organisation)
        return Response(list_body(request, org_events(), query, organisation))


class AuditEventDetailView(APIView):
    queryset = AuditEvent.platform_events.none()

    @requires_permission(AUDIT_VIEW.key)
    @extend_schema(
        operation_id="audit_events_get",
        summary="One audit event with its full values",
        responses=AuditEventDetailSerializer,
    )
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        event = org_events().filter(public_id=public_id).first()
        if event is None:
            raise NotFound
        return Response(event_data(event, full=True))


class AuditRecordHistoryView(APIView):
    queryset = AuditEvent.platform_events.none()

    @requires_permission(AUDIT_VIEW.key)
    @extend_schema(
        operation_id="audit_record_history",
        summary="A record's history, newest first (record history drawer)",
        parameters=PAGE_PARAMETERS,
        responses=AuditHistorySerializer,
    )
    def get(self, request: Request, org: Any, object_type: str, object_id: str) -> Response:
        events = org_events().filter(object_type=object_type, object_id=object_id)
        rows, cursor = page(
            events.order_by("-created_at", "-id"),
            request.query_params.get("cursor"),
            limit_of(request.query_params),
        )
        if not rows and not request.query_params.get("cursor"):
            raise NotFound  # no history here: unknown, or another organisation's record
        latest = rows[0] if rows else None
        return Response(
            {
                "record": {
                    "type": object_type,
                    "type_label": type_label(object_type),
                    "id": object_id,
                    "label": latest.object_label if latest else "",
                },
                "results": [event_data(e) for e in rows],
                "next": cursor,
                "viewer": viewer(request, _org()),
            }
        )


class AuditFiltersView(APIView):
    @requires_permission(AUDIT_VIEW.key)
    @extend_schema(
        operation_id="audit_filters",
        summary="Choices for the audit log filters: people, record types, actions",
        responses=AuditFiltersSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = _org()
        user_ids = loose_distinct("actor_user_id", organisation)
        people = User.objects.filter(pk__in=user_ids).order_by("name", "email")
        users = [{"value": "system", "label": "System"}] + [
            {"value": str(u.public_id), "label": f"{u.name} ({u.email})" if u.name else u.email}
            for u in people
        ]
        types = sorted(
            (
                {"value": t, "label": type_label(t)}
                for t in loose_distinct("object_type", organisation)
            ),
            key=lambda option: option["label"].lower(),
        )
        actions = [{"value": verb, "label": str(label)} for verb, label in VERB_LABELS.items()]
        return Response({"users": users, "types": types, "actions": actions})


class PlatformAuditListView(APIView):
    @requires_permission(PLATFORM_AUDIT_VIEW.key)
    @extend_schema(
        operation_id="platform_audit_events_list",
        summary="Platform audit log: sign-ins, 2FA, practice and organisation events",
        parameters=[
            *FILTER_PARAMETERS,
            OpenApiParameter("organisation", OpenApiTypes.UUID, description="One organisation"),
            *PAGE_PARAMETERS,
        ],
        responses=AuditPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = AuditQuery.from_params(request.query_params, None, platform=True)
        events = AuditEvent.platform_events.select_related(*SELECT)
        return Response(list_body(request, events, query, None))
