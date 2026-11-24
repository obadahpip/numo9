"""Running a report for a screen or an export (K-01-T11): the **report body**.

``report_body(organisation, report, raw, today=…, layout=None, language=None)`` → the dict the
runner shows and every export renders (K-01-T10):

- ``raw`` — the request's parameters; ``preset`` (K-01-T03: ``this_month`` … ``custom``) fills
  ``date_from``/``date_to`` of a period report from the organisation's financial year, the
  report's own parameters are cleaned by its schema;
- with a ``layout`` (K-01-T08) — its parameters are the defaults, its rows order/labels/text
  blocks are applied and its footnotes printed; a **published** layout answers its stored
  snapshot, never a new run;
- ``header`` (K-01-T06) and the cell notes (K-01-T09) on their rows.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any

from .engine import ReportDefinition
from .models import LayoutStatus, ReportLayout

RUN_OPTIONS = ("preset",)


def _resolve_preset(
    organisation: Any, report: ReportDefinition, params: dict[str, Any], today: dt.date
) -> dict[str, Any]:
    from numo9.orgsettings.service import get_settings
    from numo9.tenancy.context import org_context

    preset = params.pop("preset", None)
    names = {spec.name for spec in report.params}
    if not preset or not {"date_from", "date_to"} <= names:
        return params
    from .engine import ParamSpec
    from .parameters import resolve_range

    date = ParamSpec("date", "date")
    with org_context(organisation):
        settings = get_settings(organisation)
    span = resolve_range(
        str(preset),
        today,
        settings,
        date_from=date.clean(params.get("date_from")),
        date_to=date.clean(params.get("date_to")),
    )
    params["date_from"], params["date_to"] = span.start.isoformat(), span.end.isoformat()
    return params


def report_body(
    organisation: Any,
    report: ReportDefinition,
    raw: Mapping[str, Any] | None = None,
    *,
    today: dt.date,
    layout: ReportLayout | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    from .header import header_for
    from .layouts import apply_layout
    from .notes import annotate, notes_for

    if layout is not None and layout.status == LayoutStatus.PUBLISHED and layout.snapshot:
        body = dict(layout.snapshot)
        body["layout"] = layout_summary(layout)
        return body
    params: dict[str, Any] = dict(layout.params) if layout is not None else {}
    params.update({k: v for k, v in (raw or {}).items() if v not in (None, "")})
    params = _resolve_preset(organisation, report, params, today)
    result = report.run(organisation, params)
    body = result.as_dict()
    if layout is not None:
        body["rows"] = [row.as_dict() for row in apply_layout(result, layout.config)]
        body["notes"] = layout.notes
        body["layout"] = layout_summary(layout)
    else:
        body["notes"] = ""
    body["header"] = header_for(
        organisation, report, result.params, today=today, language=language
    ).as_dict()
    annotate(body, notes_for(organisation, report.id, layout))
    return body


def layout_summary(layout: ReportLayout) -> dict[str, Any]:
    return {
        "id": str(layout.public_id),
        "report": layout.report_id,
        "name": layout.name,
        "status": layout.status,
        "version": layout.version,
        "params": layout.params,
        "config": layout.config,
        "notes": layout.notes,
        "practice": str(layout.practice.public_id) if layout.practice is not None else None,
        "published_at": layout.published_at.isoformat() if layout.published_at else None,
        "updated_at": layout.updated_at.isoformat() if layout.updated_at else None,
    }
