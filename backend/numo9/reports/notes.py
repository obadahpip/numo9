"""Cell notes (K-01-T09).

- ``set_note(org, report_id, row_key, column_key, text, user, layout=None)`` — add or change the
  note of one cell (an empty text removes it);
- ``notes_for(org, report_id, layout=None)`` → ``{(row_key, column_key): text}``;
- ``annotate(result_dict, notes)`` — puts each note on its row of a run's result (``notes``:
  ``{column_key: text}``); a note whose row isn't in this run (no activity in the period) is kept
  and listed under ``unplaced_notes``, so nothing is lost when the report runs again.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from .engine import ReportError, registry
from .models import ReportLayout, ReportNote


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def set_note(
    organisation: Any,
    report_id: str,
    row_key: str,
    column_key: str,
    text: str,
    *,
    user: Any = None,
    layout: ReportLayout | None = None,
) -> ReportNote | None:
    from numo9.tenancy.context import org_context

    report = registry.get(report_id)
    if not row_key:
        raise ReportError("A note needs the row it's on.", code="reports.note.row")
    text = (text or "").strip()
    with org_context(organisation), transaction.atomic():
        existing: ReportNote | None = ReportNote.objects.filter(
            report_id=report.id,
            layout=layout,
            row_key=row_key,
            column_key=column_key or "",
            deleted_at__isnull=True,
        ).first()
        if not text:
            if existing is not None:
                existing.delete()
            return None
        if existing is not None:
            existing.text = text
            existing.save()
            return existing
        note = ReportNote(
            organisation=organisation,
            report_id=report.id,
            layout=layout,
            row_key=row_key,
            column_key=column_key or "",
            text=text,
            created_by=_person(user),
        )
        note.save()
        return note


def notes_for(
    organisation: Any, report_id: str, layout: ReportLayout | None = None
) -> dict[tuple[str, str], str]:
    from numo9.tenancy.context import org_context

    report = registry.get(report_id)
    with org_context(organisation):
        rows = ReportNote.objects.filter(
            report_id=report.id, layout=layout, deleted_at__isnull=True
        )
        return {(n.row_key, n.column_key): n.text for n in rows}


def annotate(result: dict[str, Any], notes: dict[tuple[str, str], str]) -> dict[str, Any]:
    keys = {row["key"] for row in [*result.get("rows", []), *result.get("totals", [])]}
    for row in [*result.get("rows", []), *result.get("totals", [])]:
        row["notes"] = {col: text for (key, col), text in notes.items() if key == row["key"]}
    result["unplaced_notes"] = [
        {"row": key, "column": col, "text": text}
        for (key, col), text in sorted(notes.items())
        if key not in keys
    ]
    return result
