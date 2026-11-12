"""Audit log exports: CSV, XLSX and PDF from the screen's own query (A-04-T08).

``GET /api/v1/o/<org>/audit/export/<csv|xlsx|pdf>`` with the viewer's filters builds the same
``AuditQuery`` as the list and writes **every** row it returns, newest first — so the file holds
exactly the rows the screen pages through (gap-37: Xero exports PDF/Excel only, without diffs).

One row per event, the columns people read on screen:

    Date and time · User · Action · Record type · Record · Changes · IP address · Request ID ·
    Event ID

- **Date and time** in the organisation's time zone, in the person's language and 12/24-hour
  preference (``26 Oct 2026, 4:33 p.m.``; never "16:33PM"). The XLSX cell is a real date-time
  (with that zone) so it sorts and filters in Excel;
- **Changes**: ``Amount: 100.00 → 120.50; Notes: (empty) → Net 30`` — masked fields read
  ``Hidden``, related records by name;
- **Event ID**: the event's public id, to find it again in Numo9.

Limits: CSV streams any number of rows; XLSX stops at ``XLSX_MAX_ROWS``; a PDF is for printing
and holds at most ``PDF_MAX_ROWS`` — beyond that the request is refused with a message asking to
narrow the filters or choose CSV/XLSX. Every export is itself recorded in the audit log
(``audit.log.exported``: format, row count, filters).
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from collections.abc import Iterable, Iterator
from typing import Any

from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.documents.formatting import format_date, format_datetime

from .models import AuditEvent
from .presenter import action_label, changes_data, type_label
from .query import AuditQuery, iter_all

FORMATS = ("csv", "xlsx", "pdf")
PDF_MAX_ROWS = 2_000
XLSX_MAX_ROWS = 1_000_000

COLUMNS = (
    gettext_lazy("Date and time"),
    gettext_lazy("User"),
    gettext_lazy("Action"),
    gettext_lazy("Record type"),
    gettext_lazy("Record"),
    gettext_lazy("Changes"),
    gettext_lazy("IP address"),
    gettext_lazy("Request ID"),
    gettext_lazy("Event ID"),
)
CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


class ExportTooLarge(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(limit)
        self.limit = limit


def _value_text(value: Any) -> str:
    if value is None or value == "":
        return _("(empty)")
    if isinstance(value, dict):
        if value.get("masked"):
            return _("Hidden")
        if value.get("truncated"):
            return str(value.get("text", ""))
        if "label" in value:
            return str(value.get("label") or value.get("id") or "")
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, bool):
        return _("Yes") if value else _("No")
    return str(value)


def changes_text(event: AuditEvent) -> str:
    parts = []
    for change in changes_data(event, full=True):
        if change["masked"]:
            parts.append(f"{change['label']}: {_('Hidden')}")
        else:
            old, new = _value_text(change["old"]), _value_text(change["new"])
            parts.append(f"{change['label']}: {old} → {new}")
    return "; ".join(parts)


def row_of(event: AuditEvent, query: AuditQuery, locale: str, time_format: str) -> list[Any]:
    local = event.created_at.astimezone(query.time_zone)
    return [
        format_datetime(local, locale, time_format),
        event.actor_label,
        action_label(event.action),
        type_label(event.object_type),
        event.object_label,
        changes_text(event),
        event.ip or "",
        event.request_id,
        str(event.public_id),
    ]


def rows(
    events: Iterable[AuditEvent], query: AuditQuery, locale: str, time_format: str
) -> Iterator[tuple[AuditEvent, list[Any]]]:
    for event in events:
        yield event, row_of(event, query, locale, time_format)


def headers() -> list[str]:
    return [str(c) for c in COLUMNS]


# ---- writers -----------------------------------------------------------------------------------


_FORMULA = re.compile(r"^[=+\-@\t\r]")


def _safe(cell: Any) -> Any:
    """Text that a spreadsheet would run as a formula is written as text (CSV injection)."""
    if isinstance(cell, str) and _FORMULA.match(cell):
        return "'" + cell
    return cell


def write_csv(
    events: Iterable[AuditEvent], query: AuditQuery, locale: str, fmt: str
) -> Iterator[str]:
    """CSV lines, streamed: UTF-8 with a byte-order mark (Excel opens accents correctly)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")

    def flush() -> str:
        text = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return text

    with translation.override(locale):
        writer.writerow(headers())
        yield "﻿" + flush()
        for _event, row in rows(events, query, locale, fmt):
            writer.writerow([_safe(cell) for cell in row])
            yield flush()


def write_xlsx(events: Iterable[AuditEvent], query: AuditQuery, locale: str, fmt: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font

    with translation.override(locale):
        book = Workbook(write_only=True)
        sheet = book.create_sheet(title=_("Audit log")[:31])
        bold = Font(bold=True)

        header = []
        for title in headers():
            cell = WriteOnlyCell(sheet, value=title)
            cell.font = bold
            header.append(cell)
        sheet.append(header)
        for count, (event, row) in enumerate(rows(events, query, locale, fmt), start=1):
            if count > XLSX_MAX_ROWS:
                raise ExportTooLarge(XLSX_MAX_ROWS)
            when = WriteOnlyCell(
                sheet, value=event.created_at.astimezone(query.time_zone).replace(tzinfo=None)
            )
            when.number_format = "yyyy-mm-dd hh:mm" if fmt == "24h" else "yyyy-mm-dd h:mm AM/PM"
            sheet.append([when, *[_safe(cell) for cell in row[1:]]])
        out = io.BytesIO()
        book.save(out)
    return out.getvalue()


def write_pdf(
    events: Iterable[AuditEvent],
    query: AuditQuery,
    locale: str,
    fmt: str,
    *,
    organisation_name: str,
) -> bytes:
    from numo9.documents.pdf import render_pdf

    collected = []
    for count, (_event, row) in enumerate(rows(events, query, locale, fmt), start=1):
        if count > PDF_MAX_ROWS:
            raise ExportTooLarge(PDF_MAX_ROWS)
        collected.append(row)
    context = {
        "issuer": {"legal_name": organisation_name},
        "rows": collected,
        "columns": headers(),
        "range_from": format_date(query.date_from, locale),
        "range_to": format_date(query.date_to, locale),
        "time_zone": query.time_zone.key,
        "generated": format_datetime(dt.datetime.now(query.time_zone), locale, fmt),
    }
    with translation.override(locale):
        context["columns"] = headers()
        return render_pdf("audit/export.html", context, locale=locale)


def all_events(query: AuditQuery, events: Any) -> Iterator[AuditEvent]:
    """Every event of the query, newest first (keyset chunks, like the screen's pages)."""
    return iter(iter_all(query.apply(events)))
