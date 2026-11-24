"""K-01-T10 — report exports: PDF (Letter, 1 in margins), XLSX (totals as formulas) and CSV,
each equal to the screen (the report body), checked on the trial balance and account activity
of the report test books, plus a stored PDF text snapshot."""

from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pypdf
import pytest
from openpyxl import load_workbook

from numo9.documents.pdf import LETTER_POINTS
from numo9.reports.engine import ReportError, registry
from numo9.reports.exports import export_report, render_csv, render_pdf, render_xlsx
from numo9.reports.header import header_for
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 8, 1)
SNAPSHOT = Path(__file__).parent / "snapshots" / "report_activity_pdf.txt"


def body(org: Any, report_id: str, params: dict[str, Any]) -> dict[str, Any]:
    report = registry.get(report_id)
    result = report.run(org, params)
    data = result.as_dict()
    data["header"] = header_for(org, report, result.params, today=TODAY).as_dict()
    return data


@pytest.fixture
def books() -> dict[str, Any]:
    return report_books()


@pytest.fixture
def activity(books: dict[str, Any]) -> dict[str, Any]:
    return body(
        books["org"], "account_activity", {"date_from": "2026-05-01", "date_to": "2026-07-31"}
    )


def screen(data: dict[str, Any]) -> list[list[Any]]:
    return [[r["label"], *r["values"]] for r in data["rows"] + data["totals"]]


def test_csv_equals_the_screen(activity: dict[str, Any]) -> None:
    text = render_csv(activity).decode("utf-8")
    assert text.startswith("﻿")
    lines = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert lines[0] == ["Account activity"]
    assert ["1 May 2026 to 31 Jul 2026"] in lines
    heading = lines.index(["", "Debits", "Credits", "Net movement"])
    table = [[cell if cell != "" else None for cell in line] for line in lines[heading + 1 :]]
    assert table == screen(activity)
    assert table[-1] == ["Total", "8750.00", "8750.00", "0.00"]


def test_xlsx_values_equal_the_screen_and_totals_are_formulas(activity: dict[str, Any]) -> None:
    sheet = load_workbook(io.BytesIO(render_xlsx(activity))).active
    assert sheet["A1"].value == "Account activity"
    rows = [list(r) for r in sheet.iter_rows(values_only=True)]
    heading = rows.index([None, "Debits", "Credits", "Net movement"])
    table = rows[heading + 1 : heading + 1 + len(screen(activity))]
    *plain, total = table
    expected = screen(activity)
    for got, want in zip(plain, expected[:-1], strict=True):
        assert got[0] == want[0]
        assert [
            None if v is None else Decimal(str(v)).quantize(Decimal("0.01")) for v in got[1:]
        ] == [None if v is None else Decimal(v) for v in want[1:]]
    first, last = heading + 2, heading + 1 + len(plain)
    assert total[0] == "Total"
    assert total[1:] == [f"=SUM({c}{first}:{c}{last})" for c in "BCD"]
    assert sheet.cell(row=first, column=2).number_format == "#,##0.00;-#,##0.00"


def test_xlsx_total_that_is_not_a_sum_is_written_as_its_value(activity: dict[str, Any]) -> None:
    activity["totals"][0]["values"] = ["1.00", "8750.00", None]
    sheet = load_workbook(io.BytesIO(render_xlsx(activity))).active
    total = next(r for r in sheet.iter_rows(values_only=True) if r[0] == "Total")
    assert total[1] == 1 and str(total[2]).startswith("=SUM(") and total[3] is None


def pdf_text(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
    raw = "\n".join(page.extract_text() for page in reader.pages)
    return "\n".join(
        line.rstrip() for line in re.sub(r"[ \t]+", " ", raw).splitlines() if line.strip()
    )


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\xa0", " "))


@pytest.mark.gap("gap-43")
def test_pdf_shows_the_screen_values_and_matches_the_snapshot(activity: dict[str, Any]) -> None:
    activity["notes"] = "Unaudited — prepared for management."
    text = pdf_text(render_pdf(activity))
    for expected in (
        "Account activity",
        "Refined Interiors Inc.",
        "1 May 2026 to 31 Jul 2026",
        "Basis: Accrual (organisation default)",
        "Accounting book",
        "Unaudited — prepared for management.",
        "$8,750.00",
    ):
        assert expected in text, expected
    for row in activity["rows"]:
        assert squeezed(row["label"]) in squeezed(text)
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text + "\n", encoding="utf-8")
    assert squeezed(text) == squeezed(SNAPSHOT.read_text(encoding="utf-8"))


def test_empty_report_prints_the_no_activity_hint(books: dict[str, Any]) -> None:
    data = body(
        books["org"], "account_activity", {"date_from": "2025-01-01", "date_to": "2025-01-31"}
    )
    assert data["rows"] == []
    assert "No activity in this period" in pdf_text(render_pdf(data))


def test_french_pdf_formats_amounts_the_french_way(activity: dict[str, Any]) -> None:
    assert "8750,00$" in squeezed(pdf_text(render_pdf(activity, "fr-ca")))


def test_export_report_names_the_file_and_refuses_unknown_formats(books: dict[str, Any]) -> None:
    data = body(books["org"], "trial_balance", {"as_of": "2026-07-31"})
    name, mime, content = export_report(data, "xlsx")
    assert name == "trial-balance-2026-07-31.xlsx"
    assert mime.startswith("application/vnd.openxmlformats")
    assert content[:2] == b"PK"
    assert export_report(data, "csv")[0] == "trial-balance-2026-07-31.csv"
    with pytest.raises(ReportError) as refused:
        export_report(data, "docx")
    assert refused.value.code == "reports.export.format"
