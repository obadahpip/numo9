"""G-05-T11 — tax report exports equal the screen: CSV and XLSX hold exactly the rows, columns
and totals of the run, the PDF shows every row (Letter, 1 in) — the tax summary's PDF text is a
stored snapshot."""

from __future__ import annotations

import csv
import datetime as dt
import io
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from numo9.reports.engine import registry
from numo9.reports.exports import render_csv, render_pdf, render_xlsx
from numo9.reports.header import header_for
from tests.tax_report_helpers import Q2, tax_books
from tests.test_report_exports import pdf_text, squeezed

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 7, 15)
RANGE = {"date_from": Q2[0].isoformat(), "date_to": Q2[1].isoformat()}
REPORTS = ("tax_summary", "tax_detail", "tax_audit", "itc_detail", "tax_tie_out")
SNAPSHOT = Path(__file__).parent / "snapshots" / "tax_summary_pdf.txt"


@pytest.fixture
def bodies() -> dict[str, dict[str, Any]]:
    books = tax_books()
    out = {}
    for report_id in REPORTS:
        report = registry.get(report_id)
        result = report.run(books["org"], RANGE)
        data = result.as_dict()
        data["header"] = header_for(books["org"], report, result.params, today=TODAY).as_dict()
        out[report_id] = data
    return out


def screen(data: dict[str, Any]) -> list[list[Any]]:
    return [[r["label"], *r["values"]] for r in data["rows"] + data["totals"]]


@pytest.mark.parametrize("report_id", REPORTS)
def test_csv_and_xlsx_equal_the_screen(bodies: dict[str, dict[str, Any]], report_id: str) -> None:
    data = bodies[report_id]
    lines = list(csv.reader(io.StringIO(render_csv(data).decode("utf-8").lstrip("﻿"))))
    heading = lines.index(["", *(c["label"] for c in data["columns"])])
    table = [[cell if cell != "" else None for cell in line] for line in lines[heading + 1 :]]
    assert table == screen(data)
    sheet = load_workbook(io.BytesIO(render_xlsx(data))).active
    rows = [list(r) for r in sheet.iter_rows(values_only=True)]
    start = rows.index([None, *(c["label"] for c in data["columns"])]) + 1
    labels = [r[0] for r in rows[start : start + len(screen(data))]]
    assert labels == [r[0] for r in screen(data)]
    plain = rows[start : start + len(data["rows"])]
    for got, want in zip(plain, data["rows"], strict=True):
        assert [
            None if v is None else Decimal(str(v)).quantize(Decimal("0.01")) for v in got[1:]
        ] == [
            None if v is None else Decimal(v).quantize(Decimal("0.01"))
            for v in (want["values"] or [None] * len(data["columns"]))
        ]


@pytest.mark.parametrize("report_id", REPORTS)
def test_pdf_shows_every_row(bodies: dict[str, dict[str, Any]], report_id: str) -> None:
    data = bodies[report_id]
    text = squeezed(pdf_text(render_pdf(data)))
    for row in data["rows"] + data["totals"]:
        assert squeezed(row["label"]) in text, row["label"]


def test_summary_pdf_matches_its_snapshot(bodies: dict[str, dict[str, Any]]) -> None:
    text = pdf_text(render_pdf(bodies["tax_summary"]))
    assert "$195.00" in text and "$143.00" in text and "$52.00" in text
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text + "\n", encoding="utf-8")
    assert squeezed(text) == squeezed(SNAPSHOT.read_text(encoding="utf-8"))
