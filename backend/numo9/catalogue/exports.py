"""Feature-matrix export for the Platform Owner (U-01-T10): CSV and XLSX (openpyxl).

One row per feature key — exactly the keys in the catalogue table — with its product, the
plain-language description, area, action, read-only flag and one column per package ("Yes" when
the package includes the key's product; no package columns before U-02). Texts in the
requester's language. Used by ``GET /api/v1/platform/catalogue/feature-matrix/export/<format>``
and ``manage.py featurematrix_export``.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from django.utils import translation
from django.utils.translation import gettext as _

from .presenter import feature_matrix

FORMATS = ("csv", "xlsx")
CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_FORMULA = re.compile(r"^[=+\-@\t\r]")


def _safe(cell: Any) -> Any:
    """Text that a spreadsheet would run as a formula is written as text (CSV injection)."""
    if isinstance(cell, str) and _FORMULA.match(cell):
        return "'" + cell
    return cell


def table(locale: str) -> tuple[list[str], list[list[Any]]]:
    """Header and rows of the matrix in ``locale``."""
    with translation.override(locale):
        matrix = feature_matrix()
        packages = matrix["packages"]
        header = [
            _("Product"),
            _("Product code"),
            _("Feature key"),
            _("Description"),
            _("Area"),
            _("Action"),
            _("Read-only"),
            *[p["name"] for p in packages],
        ]
        yes, no = _("Yes"), _("No")
        rows = [
            [
                row["product_name"],
                row["product"],
                row["key"],
                row["description"],
                row["area"],
                row["action"],
                yes if row["is_read_only"] else no,
                *[yes if p["code"] in row["packages"] else "" for p in packages],
            ]
            for row in matrix["features"]
        ]
    return header, rows


def write_csv(locale: str) -> bytes:
    """UTF-8 with a byte-order mark (Excel opens accents correctly), CRLF line ends."""
    header, rows = table(locale)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([_safe(cell) for cell in row])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def write_xlsx(locale: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    header, rows = table(locale)
    with translation.override(locale):
        title = _("Feature matrix")
    book = Workbook()
    sheet = book.active
    sheet.title = title[:31]
    sheet.append(header)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([_safe(cell) for cell in row])
    sheet.freeze_panes = "A2"
    for column, width in zip("ABCDEFG", (16, 14, 38, 60, 22, 10, 10), strict=True):
        sheet.column_dimensions[column].width = width
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def write(kind: str, locale: str) -> bytes:
    return write_csv(locale) if kind == "csv" else write_xlsx(locale)
