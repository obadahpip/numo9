"""Report layouts (K-01-T08): apply, save, publish.

- ``apply_layout(result, config)`` → rows in the layout's order, renamed and hidden as it says,
  with its text blocks inserted (a ``text`` row after the row it names, or first when it names
  none); rows the layout doesn't mention (a new account) keep their place after the ones it does;
- ``save_draft(org, report_id, name, params, config, notes, user, practice=None)`` — a draft (a
  new version when the latest of that name is published);
- ``publish(layout, user, today)`` — runs the report with the layout's parameters, applies the
  layout, stores the result and its header as the **snapshot** and freezes the layout: a published
  layout is never edited (``LayoutLocked``); its snapshot doesn't change when postings come in;
- ``save_custom(...)`` — a named variant, edited freely.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction
from django.utils import timezone

from .engine import ReportError, ReportResult, ReportRow, registry
from .models import LayoutStatus, ReportLayout


class LayoutLocked(ReportError):
    pass


def apply_layout(result: ReportResult, config: dict[str, Any] | None) -> list[ReportRow]:
    config = config or {}
    settings = {str(r.get("key")): r for r in config.get("rows", []) if r.get("key")}
    order = list(settings)
    rows = sorted(
        result.rows,
        key=lambda r: (order.index(r.key) if r.key in settings else len(order), 0),
    )
    out: list[ReportRow] = []
    blocks = list(config.get("text_blocks", []))
    for i, block in enumerate(blocks):
        if not block.get("after"):
            out.append(ReportRow(f"text:{i}", str(block.get("text", "")), "text"))
    for row in rows:
        chosen = settings.get(row.key, {})
        if chosen.get("hidden"):
            continue
        label = str(chosen.get("label") or row.label)
        out.append(ReportRow(row.key, label, row.kind, list(row.values), row.level, row.drill))
        for i, block in enumerate(blocks):
            if block.get("after") == row.key:
                out.append(ReportRow(f"text:{i}", str(block.get("text", "")), "text"))
    return out


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def _latest(organisation: Any, report_id: str, name: str) -> ReportLayout | None:
    return (
        ReportLayout.objects.filter(
            organisation=organisation, report_id=report_id, name=name, deleted_at__isnull=True
        )
        .order_by("-version")
        .first()
    )


def _save(
    organisation: Any,
    status: str,
    report_id: str,
    name: str,
    params: dict[str, Any],
    config: dict[str, Any],
    notes: str,
    user: Any,
    practice: Any,
) -> ReportLayout:
    from numo9.tenancy.context import org_context

    report = registry.get(report_id)
    report.clean_params(params)  # a layout always runs
    with org_context(organisation), transaction.atomic():
        latest = _latest(organisation, report.id, name)
        if latest is not None and latest.status != LayoutStatus.PUBLISHED:
            latest.status = status
            latest.params, latest.config, latest.notes = dict(params), dict(config), notes
            latest.practice = practice
            latest.save()
            return latest
        layout = ReportLayout(
            organisation=organisation,
            report_id=report.id,
            name=name,
            status=status,
            version=(latest.version + 1) if latest else 1,
            params=dict(params),
            config=dict(config),
            notes=notes,
            practice=practice,
            created_by=_person(user),
        )
        layout.save()
        return layout


def save_draft(
    organisation: Any,
    report_id: str,
    name: str,
    *,
    params: dict[str, Any],
    config: dict[str, Any],
    notes: str = "",
    user: Any = None,
    practice: Any = None,
) -> ReportLayout:
    return _save(
        organisation, LayoutStatus.DRAFT, report_id, name, params, config, notes, user, practice
    )


def save_custom(
    organisation: Any,
    report_id: str,
    name: str,
    *,
    params: dict[str, Any],
    config: dict[str, Any],
    notes: str = "",
    user: Any = None,
    practice: Any = None,
) -> ReportLayout:
    return _save(
        organisation, LayoutStatus.CUSTOM, report_id, name, params, config, notes, user, practice
    )


def publish(layout: ReportLayout, user: Any, today: dt.date) -> ReportLayout:
    from numo9.tenancy.context import org_context

    from .header import header_for

    with org_context(layout.organisation), transaction.atomic():
        locked: ReportLayout = ReportLayout.objects.select_for_update().get(pk=layout.pk)
        if locked.status == LayoutStatus.PUBLISHED:
            raise LayoutLocked(
                "This layout is published: save a new draft to change it.",
                code="reports.layout.published",
            )
        report = registry.get(locked.report_id)
        result = report.run(locked.organisation, locked.params)
        header = header_for(locked.organisation, report, result.params, today=today)
        body = result.as_dict()
        body["rows"] = [row.as_dict() for row in apply_layout(result, locked.config)]
        body["header"] = header.as_dict()
        body["notes"] = locked.notes
        locked.snapshot = body
        locked.status = LayoutStatus.PUBLISHED
        locked.published_at = timezone.now()
        locked.published_by = _person(user)
        locked.save()
        return locked
