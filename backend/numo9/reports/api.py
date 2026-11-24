"""Reports API (K-01), under ``/api/v1/o/<org>/``.

- ``GET reports`` — the catalogue (K-01-T11): every report with its category, description,
  parameters, the feature key it needs, ``available`` (the package includes it) and
  ``favourite`` (starred by the person); plus the layouts of the organisation by status
  (``drafts``, ``published``, ``custom``) for the report home tabs;
- ``GET reports/<report>/run`` — the report body (header, columns, rows, totals, notes): the
  report's parameters and ``preset`` in the query, ``layout`` (a layout id) to apply one;
- ``GET reports/<report>/export?file=pdf|xlsx|csv`` — the same body as a file (K-01-T10;
  ``file``, not ``format``: DRF keeps ``format`` for its renderers);
- ``PUT``/``DELETE reports/<report>/favourite`` — star / unstar;
- ``GET``/``POST reports/<report>/layouts`` — the report's layouts / save one (``status`` draft or
  custom, ``name``, ``params``, ``config``, ``notes``);
- ``GET``/``DELETE reports/layouts/<id>``, ``POST reports/layouts/<id>/publish``;
- ``PUT reports/<report>/notes`` — a cell note (``row``, ``column``, ``text``; empty removes);
- ``GET reports/<report>/drill`` — the lines behind a figure (K-01-T05): ``account`` (code or
  id), ``to`` (date, required), ``from`` (date; empty = from the start of the books), ``book``
  (``accounting`` / ``tax``), ``tracking`` (``category:option`` pairs, comma-separated), ``page``.
  Answers the account, ``total`` (= the figure), ``count``, the page and its lines, each with its
  source document link.

Every report endpoint needs ``reports.reports.view`` (layouts and notes:
``reports.layouts.manage``) and is gated by **the report's own feature key** (accounting reports
``accounting.reports.read``, tax reports ``tax.reports.read``): a report outside the package
answers 402 naming its product. 400 with a ``reports.*`` code for bad parameters, 404 for an
unknown report or layout.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE, require_feature, requires_feature
from numo9.catalogue.entitlements import get_resolver
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .drill import drill
from .engine import ReportDefinition, ReportError, registry
from .models import LayoutStatus, ReportFavourite, ReportLayout
from .permissions import LAYOUTS_MANAGE, REPORTS_VIEW
from .runner import layout_summary, report_body


def _report(key: str) -> ReportDefinition:
    """The report named in the URL — 404 when unknown, 402 when outside the package."""
    if key not in registry:
        raise NotFound(_("There's no such report."))
    report = registry.get(key)
    require_feature(report.feature)
    return report


def _layout(public_id: Any) -> ReportLayout:
    layout: ReportLayout | None = ReportLayout.objects.filter(
        public_id=public_id, deleted_at__isnull=True
    ).first()
    if layout is None:
        raise NotFound(_("There's no such report layout."))
    require_feature(registry.get(layout.report_id).feature)
    return layout


def _raw(query: Any, *skip: str) -> dict[str, Any]:
    return {k: query.get(k) for k in query if k not in skip}


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
    @requires_feature(CORE)  # gated by the report's own feature key (_report)
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
        _report(report)
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


class ReportCatalogueView(APIView):
    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(CORE)  # the catalogue lists gated reports too, marked unavailable
    @extend_schema(
        operation_id="reports_catalogue", summary="The report catalogue", responses={200: dict}
    )
    def get(self, request: Request, org: Any) -> Response:
        organisation = current_org()
        resolver = get_resolver()
        starred = set(
            ReportFavourite.objects.filter(user=request.user).values_list("report_id", flat=True)
        )
        categories = []
        for category, reports in registry.by_category().items():
            categories.append(
                {
                    "key": category,
                    "reports": [
                        {
                            **report.summary(),
                            "available": resolver.allows(organisation, report.feature),
                            "favourite": report.id in starred,
                        }
                        for report in reports
                    ],
                }
            )
        layouts = ReportLayout.objects.filter(deleted_at__isnull=True).order_by(
            "report_id", "name", "-version"
        )
        tabs: dict[str, list[dict[str, Any]]] = {"drafts": [], "published": [], "custom": []}
        tab = {
            LayoutStatus.DRAFT: "drafts",
            LayoutStatus.PUBLISHED: "published",
            LayoutStatus.CUSTOM: "custom",
        }
        for layout in layouts:
            if layout.report_id in registry:
                tabs[tab[LayoutStatus(layout.status)]].append(layout_summary(layout))
        return Response({"categories": categories, "favourites": sorted(starred), **tabs})


class ReportRunView(APIView):
    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(CORE)  # gated by the report's own feature key (_report)
    @extend_schema(
        operation_id="reports_run",
        summary="Run a report: header, columns, rows, totals and notes",
        parameters=[OpenApiParameter("preset", str), OpenApiParameter("layout", str)],
        responses={200: dict},
    )
    def get(self, request: Request, org: Any, report: str) -> Response:
        definition = _report(report)
        query = request.query_params
        layout = _layout(query["layout"]) if query.get("layout") else None
        try:
            body = report_body(
                current_org(),
                definition,
                _raw(query, "layout"),
                today=timezone.localdate(),
                layout=layout,
            )
        except ReportError as error:
            return _refused(error)
        return Response(body)


class ReportExportView(APIView):
    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(CORE)  # gated by the report's own feature key (_report)
    @extend_schema(
        operation_id="reports_export",
        summary="A report as PDF, XLSX or CSV — the same figures as the screen",
        parameters=[
            OpenApiParameter("file", str, required=True),
            OpenApiParameter("preset", str),
            OpenApiParameter("layout", str),
        ],
        responses={200: bytes},
    )
    def get(self, request: Request, org: Any, report: str) -> Response | HttpResponse:
        from .exports import export_report

        definition = _report(report)
        query = request.query_params
        layout = _layout(query["layout"]) if query.get("layout") else None
        try:
            body = report_body(
                current_org(),
                definition,
                _raw(query, "layout", "file"),
                today=timezone.localdate(),
                layout=layout,
            )
            name, content_type, content = export_report(body, query.get("file") or "")
        except ReportError as error:
            return _refused(error)
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response


class ReportFavouriteView(APIView):
    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="reports_favourite_add", request=None, responses={204: None})
    def put(self, request: Request, org: Any, report: str) -> Response:
        definition = _report(report)
        ReportFavourite.objects.get_or_create(
            organisation=current_org(), user=request.user, report_id=definition.id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="reports_favourite_remove", responses={204: None})
    def delete(self, request: Request, org: Any, report: str) -> Response:
        if report not in registry:
            raise NotFound(_("There's no such report."))
        ReportFavourite.objects.filter(
            user=request.user, report_id=registry.get(report).id
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportLayoutListView(APIView):
    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(CORE)  # gated by the report's own feature key (_report)
    @extend_schema(operation_id="reports_layouts", responses={200: dict})
    def get(self, request: Request, org: Any, report: str) -> Response:
        definition = _report(report)
        layouts = ReportLayout.objects.filter(
            report_id=definition.id, deleted_at__isnull=True
        ).order_by("name", "-version")
        return Response({"results": [layout_summary(layout) for layout in layouts]})

    @requires_permission(LAYOUTS_MANAGE.key)
    @requires_feature(CORE)  # gated by the report's own feature key (_report)
    @extend_schema(
        operation_id="reports_layout_save",
        summary="Save a layout as a draft or a custom variant",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, org: Any, report: str) -> Response:
        from .layouts import save_custom, save_draft

        definition = _report(report)
        data = request.data if isinstance(request.data, dict) else {}
        kind = data.get("status") or LayoutStatus.DRAFT
        name = str(data.get("name") or "").strip()
        try:
            if kind not in (LayoutStatus.DRAFT, LayoutStatus.CUSTOM):
                raise ReportError(
                    "status must be draft or custom (publish a draft to publish it).",
                    code="reports.layout.status",
                )
            if not name:
                raise ReportError("A layout needs a name.", code="reports.layout.name")
            if not isinstance(data.get("params", {}), dict) or not isinstance(
                data.get("config", {}), dict
            ):
                raise ReportError(
                    "params and config must be objects.", code="reports.layout.invalid"
                )
            save = save_custom if kind == LayoutStatus.CUSTOM else save_draft
            layout = save(
                current_org(),
                definition.id,
                name[:120],
                params=data.get("params") or {},
                config=data.get("config") or {},
                notes=str(data.get("notes") or ""),
                user=request.user,
            )
        except ReportError as error:
            return _refused(error)
        return Response(layout_summary(layout), status=status.HTTP_201_CREATED)


class ReportLayoutDetailView(APIView):
    @requires_permission(REPORTS_VIEW.key)
    @requires_feature(CORE)  # gated by the layout's report feature key (_layout)
    @extend_schema(operation_id="reports_layout_detail", responses={200: dict})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        layout = _layout(public_id)
        return Response({**layout_summary(layout), "snapshot": layout.snapshot})

    @requires_permission(LAYOUTS_MANAGE.key)
    @requires_feature(CORE)  # gated by the layout's report feature key (_layout)
    @extend_schema(operation_id="reports_layout_delete", responses={204: None})
    def delete(self, request: Request, org: Any, public_id: Any) -> Response:
        layout = _layout(public_id)
        if layout.status == LayoutStatus.PUBLISHED:
            return _refused(
                ReportError(
                    "A published layout is kept: it is the record of what was published.",
                    code="reports.layout.published",
                )
            )
        layout.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportLayoutPublishView(APIView):
    @requires_permission(LAYOUTS_MANAGE.key)
    @requires_feature(CORE)  # gated by the layout's report feature key (_layout)
    @extend_schema(operation_id="reports_layout_publish", request=None, responses={200: dict})
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        from .layouts import publish

        layout = _layout(public_id)
        try:
            published = publish(layout, request.user, timezone.localdate())
        except ReportError as error:
            return _refused(error)
        return Response({**layout_summary(published), "snapshot": published.snapshot})


class ReportNoteView(APIView):
    @requires_permission(LAYOUTS_MANAGE.key)
    @requires_feature(CORE)  # gated by the report's own feature key (_report)
    @extend_schema(operation_id="reports_note_set", request=dict, responses={200: dict})
    def put(self, request: Request, org: Any, report: str) -> Response:
        from .notes import set_note

        definition = _report(report)
        data = request.data if isinstance(request.data, dict) else {}
        layout = _layout(data["layout"]) if data.get("layout") else None
        try:
            note = set_note(
                current_org(),
                definition.id,
                str(data.get("row") or ""),
                str(data.get("column") or ""),
                str(data.get("text") or ""),
                user=request.user,
                layout=layout,
            )
        except ReportError as error:
            return _refused(error)
        return Response(
            {
                "row": str(data.get("row") or ""),
                "column": str(data.get("column") or ""),
                "text": note.text if note else "",
            }
        )
