"""Saved directory views API (V-01-T08), under ``/api/v1/``.

A user's own named directory states, per practice; nobody else — not even a practice admin —
lists, opens, changes or deletes them (another user's view answers 404, the same as an unknown id):

- ``GET    /api/v1/practice/views?practice=…`` — the user's views in the practice (the default one
  first, then by name);
- ``POST   /api/v1/practice/views`` — save one (``practice``, ``name``, ``filters``, ``columns``,
  ``sort``, ``density``, ``is_default``); names are unique per user and practice (case ignored),
  at most 50 views each;
- ``PATCH  /api/v1/practice/views/<id>`` — rename, update with the current state, set as default
  (the previous default stops being one);
- ``DELETE /api/v1/practice/views/<id>``.

The user must belong to the practice (else 404); leaving a practice hides its views (they are
deleted with the membership's practice or user). Not organisation-scoped: on the tenant-sweep
exempt list with the directory; ``tests/test_workspace_views.py`` proves the isolation.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from django.db import IntegrityError, transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.rbac.drf import AUTHENTICATED, requires_permission
from numo9.tenancy.models import Practice, PracticeMember

from .api import bad_parameter, resolve_practice
from .models import SavedView
from .serializers import SavedViewSerializer, SavedViewWriteSerializer

MAX_VIEWS = 50
FIELDS = ("name", "filters", "columns", "sort", "density", "is_default")


def _user(request: Request) -> User:
    return cast(User, request.user)


def _payload(view: SavedView) -> dict[str, Any]:
    return dict(SavedViewSerializer(view).data)


def _save(view: SavedView, data: dict[str, Any]) -> SavedView:
    for name in FIELDS:
        if name in data:
            setattr(view, name, data[name])
    try:
        with transaction.atomic():
            if view.is_default:  # one default per user and practice
                SavedView.objects.filter(
                    user=view.user, practice=view.practice, is_default=True
                ).exclude(pk=view.pk).update(is_default=False)
            view.save()
    except IntegrityError:
        raise bad_parameter(errors.WORKSPACE_VIEW_NAME_TAKEN, "name", name=view.name) from None
    return view


class SavedViewListView(APIView):
    required_feature = CORE  # the Practice product is free: never gated

    @requires_permission(AUTHENTICATED)  # the user's own views, in a practice they belong to
    @extend_schema(
        operation_id="practice_views_list",
        summary="My saved directory views in a practice",
        parameters=[OpenApiParameter("practice", OpenApiTypes.UUID)],
        responses=SavedViewSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        practice = resolve_practice(request)
        views = SavedView.objects.filter(user=_user(request), practice=practice).order_by(
            "-is_default", "name", "pk"
        )
        return Response([_payload(view) for view in views.select_related("practice")])

    @requires_permission(AUTHENTICATED)
    @extend_schema(
        operation_id="practice_views_create",
        summary="Save a directory view",
        request=SavedViewWriteSerializer,
        responses={201: SavedViewSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = SavedViewWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        given = data.pop("practice", None)
        practice: Practice = resolve_practice(request, str(given) if given else None)
        if SavedView.objects.filter(user=_user(request), practice=practice).count() >= MAX_VIEWS:
            raise bad_parameter(errors.WORKSPACE_VIEW_LIMIT, "name", max=MAX_VIEWS)
        view = _save(SavedView(user=_user(request), practice=practice), data)
        return Response(_payload(view), status=status.HTTP_201_CREATED)


class SavedViewDetailView(APIView):
    required_feature = CORE

    def _view(self, request: Request, view_id: uuid.UUID) -> SavedView:
        view = (
            SavedView.objects.filter(public_id=view_id, user=_user(request))
            .select_related("practice")
            .first()
        )
        if (
            view is None
            or not PracticeMember.objects.filter(
                practice=view.practice, user=_user(request)
            ).exists()
        ):
            raise NotFound  # another user's view, or a practice the user has left
        return view

    @requires_permission(AUTHENTICATED)  # only the view's own user (404 for anyone else)
    @extend_schema(
        operation_id="practice_views_update",
        summary="Change a saved directory view",
        request=SavedViewWriteSerializer,
        responses=SavedViewSerializer,
    )
    def patch(self, request: Request, view_id: uuid.UUID) -> Response:
        view = self._view(request, view_id)
        payload = SavedViewWriteSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        data.pop("practice", None)  # a view never moves to another practice
        return Response(_payload(_save(view, data)))

    @requires_permission(AUTHENTICATED)  # only the view's own user (404 for anyone else)
    @extend_schema(
        operation_id="practice_views_delete",
        summary="Delete a saved directory view",
        responses={204: None},
    )
    def delete(self, request: Request, view_id: uuid.UUID) -> Response:
        self._view(request, view_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
