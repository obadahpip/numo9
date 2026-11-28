"""Report exports (K-01-T10): PDF, XLSX and CSV of a report run.

Every renderer takes the **report body** — what the screen shows: ``ReportResult.as_dict()``
plus ``header`` (K-01-T06) and, optionally, ``notes`` (footnotes) and cell notes on the rows —
the same dict a published layout stores as its snapshot (K-01-T08). An export is therefore the
screen, never a second computation: same rows, same order, same labels, same values.

- ``render_pdf(body, locale)`` — Letter, 1 in margins, on the printed-document baseline
  (``documents/base.html``, A-10-T16); amounts formatted like the screen (``$1,234.56``); the
  core statements (K-02-T14: P&L, balance sheet, retained earnings, cash flow) on the statement
  template — display and legal name centred over the title, grand totals double-ruled, notes as
  full-width lines;
- ``render_xlsx(body)`` — one sheet: header lines, the column headings, the rows with amounts as
  numbers (``#,##0.00``) and every **total as a formula** (``=SUM(…)``) over the rows it adds up,
  when they do add up to it; a total that isn't a plain sum of rows above it (net income of a
  statement) is written as its value. Google Sheets opens the file as is;
- ``render_csv(body)`` — UTF-8 with BOM (Excel opens it), header lines, a blank line, then the
  table; amounts as plain decimals (``1234.56``), empty when the cell is empty.

``export_report(body, fmt, locale)`` → ``(filename, content_type, bytes)``.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from .engine import ReportError

FORMATS = ("pdf", "xlsx", "csv")
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
}
HEADER_LINES = ("display_name", "legal_name", "period_label", "status_label", "basis_label")


def _header_lines(body: dict[str, Any]) -> list[str]:
    header = body.get("header") or {}
    lines = [str(header.get("title") or body.get("report", ""))]
    lines += [str(header[key]) for key in HEADER_LINES if header.get(key)]
    if header.get("book_label"):
        lines.append(str(header["book_label"]))
    return lines


def _table(body: dict[str, Any]) -> list[dict[str, Any]]:
    return list(body.get("rows", [])) + list(body.get("totals", []))


def _decimal(value: Any) -> Decimal | None:
    return None if value is None or value == "" else Decimal(str(value))


def filename_for(body: dict[str, Any], fmt: str) -> str:
    header = body.get("header") or {}
    base = str(header.get("title") or body.get("report") or "report")
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "report"
    params = body.get("params") or {}
    day = params.get("date_to") or params.get("as_of") or ""
    return f"{slug}{'-' + str(day) if day else ''}.{fmt}"


# --- CSV -----------------------------------------------------------------------------------


def render_csv(body: dict[str, Any]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    for line in _header_lines(body):
        writer.writerow([line])
    writer.writerow([])
    columns = body.get("columns", [])
    writer.writerow(["", *[c["label"] for c in columns]])
    for row in _table(body):
        values = row.get("values") or []
        writer.writerow([row["label"], *["" if v is None else v for v in values]])
    if body.get("notes"):
        writer.writerow([])
        writer.writerow([body["notes"]])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


# --- XLSX ----------------------------------------------------------------------------------


def _sum_ranges(table: Sequence[dict[str, Any]], index: int) -> list[tuple[int, int]]:
    """For the total at ``index``: candidate blocks of plain rows (table positions) it may add
    up — the rows since the previous section or total, then every plain row above it."""
    start = index
    while start > 0 and table[start - 1]["kind"] == "row":
        start -= 1
    plain = [i for i in range(index) if table[i]["kind"] == "row"]
    candidates = []
    if start < index:
        candidates.append((start, index - 1))
    if plain:
        candidates.append((plain[0], plain[-1]))
    return candidates


def render_xlsx(body: dict[str, Any]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    sheet: Any = workbook.active
    header = body.get("header") or {}
    sheet.title = re.sub(r"[\[\]:*?/\\]", " ", str(header.get("title") or "Report"))[:31]
    lines = _header_lines(body)
    for i, line in enumerate(lines, start=1):
        sheet.cell(row=i, column=1, value=line).font = Font(bold=i == 1, size=14 if i == 1 else 11)
    heading_row = len(lines) + 2
    columns = body.get("columns", [])
    for c, column in enumerate(columns, start=2):
        cell = sheet.cell(row=heading_row, column=c, value=column["label"])
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="right")
    table = _table(body)
    first = heading_row + 1
    for t, row in enumerate(table):
        r = first + t
        label = sheet.cell(row=r, column=1, value=row["label"])
        label.alignment = Alignment(indent=int(row.get("level") or 0))
        if row["kind"] in ("section", "total"):
            label.font = Font(bold=True)
        if row["kind"] == "text":
            label.font = Font(italic=True)
        values = row.get("values") or []
        for c, raw in enumerate(values, start=2):
            amount = _decimal(raw)
            if amount is None:
                continue
            cell = sheet.cell(row=r, column=c)
            cell.number_format = "#,##0.00;-#,##0.00"
            if row["kind"] == "total":
                cell.font = Font(bold=True)
                cell.value = _total_cell(table, t, c - 2, amount, first, get_column_letter(c))
            else:
                cell.value = amount
    if body.get("notes"):
        sheet.cell(row=first + len(table) + 1, column=1, value=body["notes"])
    sheet.column_dimensions["A"].width = 48
    for c in range(2, len(columns) + 2):
        sheet.column_dimensions[get_column_letter(c)].width = 16
    sheet.freeze_panes = sheet.cell(row=first, column=2)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _total_cell(
    table: Sequence[dict[str, Any]], index: int, column: int, amount: Decimal, first: int, col: str
) -> Any:
    for start, end in _sum_ranges(table, index):
        rows = [table[i] for i in range(start, end + 1) if table[i]["kind"] == "row"]
        summed = sum(
            (_decimal((r.get("values") or [None] * (column + 1))[column]) or Decimal(0))
            for r in rows
        )
        if summed == amount:
            return f"=SUM({col}{first + start}:{col}{first + end})"
    return amount


# --- PDF -----------------------------------------------------------------------------------


#: K-02-T14: the core financial statements print on their own template (``statement.html``),
#: with the rows that close each statement double-ruled; other reports use ``report.html``.
STATEMENT_TEMPLATES: dict[str, frozenset[str]] = {
    "profit_and_loss": frozenset({"net_income"}),
    "balance_sheet": frozenset({"total:assets", "total:liabilities_and_equity"}),
    "retained_earnings": frozenset({"closing"}),
    "cash_flow": frozenset({"net_change"}),
    "cash_flow_direct": frozenset({"net_change"}),
}


def render_pdf(body: dict[str, Any], locale: str | None = None) -> bytes:
    from numo9.documents.formatting import format_money
    from numo9.documents.pdf import render_pdf as render_document

    language = locale or "en-ca"
    grand = STATEMENT_TEMPLATES.get(str(body.get("report") or ""))
    table = [
        {
            **row,
            "cells": [
                "" if v is None else format_money(v, language) for v in row.get("values") or []
            ],
            "indent": int(row.get("level") or 0) * 12,
            "grand": grand is not None and row.get("key") in grand,
        }
        for row in _table(body)
    ]
    header = body.get("header") or {}
    context = {
        "header": header,
        "issuer": {"legal_name": header.get("legal_name") or header.get("display_name", "")},
        "columns": body.get("columns", []),
        "table": table,
        "empty": not body.get("rows"),
        "notes": body.get("notes", ""),
        "unplaced_notes": body.get("unplaced_notes", []),
    }
    template = "reports/statement.html" if grand is not None else "reports/report.html"
    return render_document(template, context, locale=language)


def export_report(
    body: dict[str, Any], fmt: str, locale: str | None = None
) -> tuple[str, str, bytes]:
    if fmt not in FORMATS:
        raise ReportError(
            f"format must be one of {', '.join(FORMATS)}.", code="reports.export.format"
        )
    content = (
        render_pdf(body, locale)
        if fmt == "pdf"
        else render_xlsx(body)
        if fmt == "xlsx"
        else render_csv(body)
    )
    return filename_for(body, fmt), CONTENT_TYPES[fmt], content
