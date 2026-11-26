"""Saved list views API (D-09-T03), under ``/api/v1/o/<org>/``.

A user's own named states of the organisation's lists (invoices, bills, quotes, contacts …) —
the organisation-side twin of the directory's saved views (``views_api``, V-01-T08), with the same
rules (``saved_views``): personal, names unique per user and list (case ignored), at most 50 per
user and list, one opens by default.

- ``GET    views?list=sales.invoices`` — my views of that list (the default first, then by name);
- ``POST   views`` — save one: ``list``, ``name``, ``filters`` (the list's query parameters, e.g.
  ``{"tab": "overdue", "q": "maple"}``), ``columns``, ``sort``, ``density``, ``is_default``;
- ``PATCH  views/<id>`` — rename, update with the current state, set as default (the previous
  default of the list stops being one); a view never moves to another list;
- ``DELETE views/<id>``.

Everyone in the organisation may keep views (``organisation.profile.view``: every role has it);
another user's view answers 404, the same as an unknown id or another organisation's.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.accounts.models import User
from numo9.catalogue.drf import CORE
from numo9.i18n import errors
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .api import bad_parameter
from .models import SavedListView
from .saved_views import LIST_KEYS, MAX_VIEWS, ViewNameTaken, save_view
from .serializers import SavedListViewSerializer, SavedListViewWriteSerializer

EVERYONE_HERE = "organisation.profile.view"  # every organisation and practice role has it


def _user(request: Request) -> User:
    return cast(User, request.user)


def _payload(view: SavedListView) -> dict[str, Any]:
    return dict(SavedListViewSerializer(view).data)


def _mine(request: Request, list_key: str) -> Any:
    return SavedListView.objects.filter(
        user=_user(request), list_key=list_key, deleted_at__isnull=True
    )


def _list_key(value: Any) -> str:
    key = str(value or "")
    if key not in LIST_KEYS:
        raise bad_parameter(errors.WORKSPACE_UNKNOWN_LIST, "list", value=key[:60])
    return key


def _save(request: Request, view: SavedListView, data: dict[str, Any]) -> SavedListView:
    try:
        return save_view(view, data, _mine(request, view.list_key))
    except ViewNameTaken:
        raise bad_parameter(errors.WORKSPACE_VIEW_NAME_TAKEN, "name", name=view.name) from None


class SavedListViewListView(APIView):
    required_feature = CORE  # personal preferences: never gated by the package
    serializer_class = SavedListViewSerializer

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="list_views_list",
        summary="My saved views of one list in the organisation",
        parameters=[
            OpenApiParameter("list", str, required=True, description="e.g. sales.invoices")
        ],
        responses=SavedListViewSerializer(many=True),
    )
    def get(self, request: Request, org: Any) -> Response:
        key = _list_key(request.query_params.get("list"))
        views = _mine(request, key).order_by("-is_default", "name", "pk")
        return Response([_payload(view) for view in views])

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="list_views_create",
        summary="Save a view of a list",
        request=SavedListViewWriteSerializer,
        responses={201: SavedListViewSerializer},
    )
    def post(self, request: Request, org: Any) -> Response:
        payload = SavedListViewWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        key = _list_key(data.pop("list", None))
        if _mine(request, key).count() >= MAX_VIEWS:
            raise bad_parameter(errors.WORKSPACE_VIEW_LIMIT, "name", max=MAX_VIEWS)
        view = SavedListView(
            organisation=current_org(),
            user=_user(request),
            created_by=_user(request),
            list_key=key,
        )
        return Response(_payload(_save(request, view, data)), status=status.HTTP_201_CREATED)


class SavedListViewDetailView(APIView):
    required_feature = CORE
    serializer_class = SavedListViewSerializer

    def _view(self, request: Request, view_id: uuid.UUID) -> SavedListView:
        view: SavedListView | None = SavedListView.objects.filter(
            public_id=view_id, user=_user(request), deleted_at__isnull=True
        ).first()
        if view is None:
            raise NotFound  # another user's view, another organisation's, or none
        return view

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="list_views_get",
        summary="A saved list view",
        responses=SavedListViewSerializer,
    )
    def get(self, request: Request, org: Any, view_id: uuid.UUID) -> Response:
        return Response(_payload(self._view(request, view_id)))

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="list_views_update",
        summary="Change a saved list view",
        request=SavedListViewWriteSerializer,
        responses=SavedListViewSerializer,
    )
    def patch(self, request: Request, org: Any, view_id: uuid.UUID) -> Response:
        view = self._view(request, view_id)
        payload = SavedListViewWriteSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        data.pop("list", None)  # a view never moves to another list
        return Response(_payload(_save(request, view, data)))

    @requires_permission(EVERYONE_HERE)
    @extend_schema(
        operation_id="list_views_delete", summary="Delete a saved list view", responses={204: None}
    )
    def delete(self, request: Request, org: Any, view_id: uuid.UUID) -> Response:
        self._view(request, view_id).delete()  # personal preferences: really deleted
        return Response(status=status.HTTP_204_NO_CONTENT)
