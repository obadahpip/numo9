"""Notification centre API (A-07-T01), under ``/api/v1/o/<org>/notifications``.

A person sees **their own** notifications in the organisation — never anyone else's (404). Every
member may use it (``organisation.profile.view``, which every role has); part of every
organisation (``CORE``, never gated).

- ``notifications`` — GET newest first, 30 per page (``?limit=`` up to 100), with the
  ``unread_count``; ``?unread=1`` only unread, ``?category=`` one category, ``?before=<id>`` the
  next page (the previous page's ``next``). Titles and bodies are rendered in the reader's
  language;
- ``notifications/unread-count`` — GET ``{"unread_count": n}`` (the bell's badge; cheap to poll);
- ``notifications/<id>/read`` — POST mark one read (idempotent: the first read time is kept);
- ``notifications/read-all`` — POST mark every unread one read (``{"category": …}`` limits it to a
  category) → ``{"marked": n, "unread_count": remaining}``;
- ``notifications/preferences`` — GET my choice per category (in the app, by email; locked =
  security, always on); PATCH ``{"category", "in_app", "email"}`` changes one category (a locked
  one: ``409 notifications.category_locked``) (A-07-T02).
"""

from __future__ import annotations

from typing import Any, cast

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.rbac.drf import requires_permission

from . import services
from .models import Notification, NotificationCategory
from .serializers import (
    NotificationPageSerializer,
    NotificationSerializer,
    PreferenceListSerializer,
    PreferenceSerializer,
    PreferenceUpdateSerializer,
    ReadAllRequestSerializer,
    ReadAllResultSerializer,
    UnreadCountSerializer,
)

EVERYONE_HERE = "organisation.profile.view"  # every organisation and practice role has it
PAGE_SIZE = 30
MAX_PAGE_SIZE = 100


def _user(request: Request) -> User:
    return cast(User, request.user)


def _limit(request: Request) -> int:
    try:
        value = int(request.query_params.get("limit", PAGE_SIZE))
    except ValueError:
        return PAGE_SIZE
    return max(1, min(value, MAX_PAGE_SIZE))


def _mine(request: Request, public_id: Any) -> Notification:
    notification = services.my_notifications(_user(request)).filter(public_id=public_id).first()
    if notification is None:
        raise NotFound  # someone else's, another organisation's or nonexistent: all 404
    return notification


class NotificationListView(APIView):
    required_feature = CORE
    serializer_class = NotificationSerializer  # tenant sweep: rows of Notification

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="notifications_list",
        summary="My notifications in the organisation, newest first, with the unread count",
        parameters=[
            OpenApiParameter("unread", OpenApiTypes.BOOL, description="Only unread"),
            OpenApiParameter("category", OpenApiTypes.STR, enum=NotificationCategory.values),
            OpenApiParameter("before", OpenApiTypes.UUID, description="Next page: previous next"),
            OpenApiParameter("limit", OpenApiTypes.INT, description="1–100, 30 by default"),
        ],
        responses=NotificationPageSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        user = _user(request)
        mine = services.my_notifications(user)
        query = mine
        if request.query_params.get("unread") in {"1", "true"}:
            query = query.filter(read_at__isnull=True)
        category = request.query_params.get("category")
        if category:
            query = query.filter(category=category)
        before = request.query_params.get("before")
        if before:
            anchor = mine.filter(public_id=before).values("created_at", "pk").first()
            if anchor is None:
                raise NotFound
            query = query.filter(created_at__lte=anchor["created_at"]).exclude(
                created_at=anchor["created_at"], pk__gte=anchor["pk"]
            )
        limit = _limit(request)
        page = list(query.order_by("-created_at", "-pk")[: limit + 1])
        more = len(page) > limit
        page = page[:limit]
        body = {
            "results": NotificationSerializer(page, many=True, context={"request": request}).data,
            "unread_count": services.unread_count(user),
            "next": str(page[-1].public_id) if more and page else None,
        }
        return Response(body)


class UnreadCountView(APIView):
    required_feature = CORE
    serializer_class = NotificationSerializer

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="notifications_unread_count",
        summary="How many of my notifications are unread (the bell's badge)",
        responses=UnreadCountSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        return Response({"unread_count": services.unread_count(_user(request))})


class MarkReadView(APIView):
    required_feature = CORE
    serializer_class = NotificationSerializer

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="notifications_mark_read",
        summary="Mark one of my notifications read",
        request=None,
        responses=NotificationSerializer,
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        notification = services.mark_read(_mine(request, public_id))
        return Response(NotificationSerializer(notification, context={"request": request}).data)


class MarkAllReadView(APIView):
    required_feature = CORE
    serializer_class = NotificationSerializer

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="notifications_mark_all_read",
        summary="Mark all my unread notifications read (optionally one category)",
        request=ReadAllRequestSerializer,
        responses=ReadAllResultSerializer,
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = ReadAllRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        user = _user(request)
        marked = services.mark_all_read(user, payload.validated_data.get("category"))
        return Response({"marked": marked, "unread_count": services.unread_count(user)})


class PreferencesView(APIView):
    required_feature = CORE
    serializer_class = NotificationSerializer  # tenant sweep: personal rows, nothing listed here

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="notifications_preferences",
        summary="My notification choices per category in the organisation",
        responses=PreferenceListSerializer,
    )
    def get(self, request: Request, org: Any) -> Response:
        preferences = services.preferences_for(_user(request)).values()
        return Response({"results": PreferenceSerializer(list(preferences), many=True).data})

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="notifications_preference_update",
        summary="Change one category: in the app and/or by email",
        request=PreferenceUpdateSerializer,
        responses=PreferenceSerializer,
    )
    def patch(self, request: Request, org: Any) -> Response:
        payload = PreferenceUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        category = data.pop("category")
        try:
            preference = services.set_preference(_user(request), category, **data)
        except services.LockedCategory:
            raise api_error(errors.NOTIFICATIONS_CATEGORY_LOCKED) from None
        return Response(PreferenceSerializer(preference).data)
