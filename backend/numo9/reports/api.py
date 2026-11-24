"""Reports API (K-01), under ``/api/v1/o/<org>/``.

- ``GET reports/<report>/drill`` — the lines behind a figure (K-01-T05): ``account`` (code or
  id), ``to`` (date, required), ``from`` (date; empty = from the start of the books), ``book``
  (``accounting`` / ``tax``), ``tracking`` (``category:option`` pairs, comma-separated), ``page``.
  Answers the account, ``total`` (= the figure), ``count``, the page and its lines, each with its
  source document link. 400 with a ``reports.*`` code for bad parameters, 404 for an unknown
  report.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .drill import drill
from .engine import ReportError, registry
from .permissions import REPORTS_VIEW

READ = "accounting.reports.read"


def _refused(error: ReportError) -> Response:
    return Response({"code": error.code, "detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


def _date(value: str | None, name: str, *, required: bool = False) -> dt.date | None:
    if not value:
        if required:
            raise ReportError(f"{name} is required.", code="reports.param.required")
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise ReportError(
            f"{name}: {value!r} isn't a date.", code="reports.param.invalid"
        ) from None


def _tracking(value: str | None) -> dict[str, list[str]]:
    chosen: dict[str, list[str]] = {}
    for pair in (value or "").split(","):
        if ":" in pair:
            category, option = pair.split(":", 1)
            chosen.setdefault(category.strip(), []).append(option.strip())
    return chosen


class ReportDrillView(APIView):
    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="reports_drill",
        summary="The lines behind a report figure, with their source documents",
        parameters=[
            OpenApiParameter("account", str, required=True),
            OpenApiParameter("to", str, required=True),
            OpenApiParameter("from", str),
            OpenApiParameter("book", str),
            OpenApiParameter("tracking", str),
            OpenApiParameter("page", int),
        ],
        responses={200: dict},
    )
    def get(self, request: Request, org: Any, report: str) -> Response:
        if report not in registry:
            raise NotFound(_("There's no such report."))
        query = request.query_params
        try:
            page_text = query.get("page") or "1"
            if not page_text.isdigit():
                raise ReportError("page must be a number.", code="reports.param.invalid")
            if not query.get("account"):
                raise ReportError("account is required.", code="reports.param.required")
            result = drill(
                current_org(),
                account=str(query["account"]),
                date_from=_date(query.get("from"), "from"),
                date_to=_date(query.get("to"), "to", required=True) or dt.date.max,
                book=query.get("book") or "accounting",
                tracking=_tracking(query.get("tracking")),
                page=int(page_text),
            )
        except ReportError as error:
            return _refused(error)
        return Response(result.as_dict())
