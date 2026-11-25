"""C-07-T08 — the audit report of a recode batch as PDF, XLSX and CSV: export rows = the batch's
changes."""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from numo9.ledger.recode_execute import create_batch, execute
from numo9.ledger.recode_report import export, report_rows
from numo9.ledger.recode_undo import undo
from numo9.tenancy.context import org_context
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def batch() -> Any:
    books = recode_books()
    org = books["org"]
    criteria = {"conditions": [{"field": "date", "op": "after", "value": "2025-12-31"}]}
    with org_context(org):
        made = create_batch(
            org,
            criteria,
            {"account": str(books["expense2"].public_id), "tracking": {"region": "north"}},
            books["adviser"],
            name="Q1 clean-up",
        )
        done = execute(made, books["adviser"])
    done.books = books  # type: ignore[attr-defined]
    return done


def test_rows_are_the_batch_changes(batch: Any) -> None:
    rows = report_rows(batch)
    with org_context(batch.organisation):
        assert len(rows) == batch.lines.count() == batch.line_count == 8
    expense2 = str(batch.books["expense2"])
    first = rows[0]
    assert first[0].startswith("JE-") and first[2] == 1
    assert first[6] == "Account, Tracking"
    assert first[8] == expense2
    assert first[12] == "region: north"
    assert all(row[15] and row[16] and row[17] == "" for row in rows)


def test_csv_rows_equal_changes(batch: Any) -> None:
    body, content_type, name = export(batch, "csv")
    assert content_type.startswith("text/csv") and name.endswith(".csv")
    table = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
    assert table[0][0] == "Journal" and len(table) - 1 == 8
    assert table[1][4:6] in (["1000.00", "0.00"], ["0.00", "1000.00"])


def test_xlsx_rows_equal_changes(batch: Any) -> None:
    body, _type, name = export(batch, "xlsx")
    sheet = load_workbook(io.BytesIO(body)).active
    values = list(sheet.iter_rows(values_only=True))
    header = next(i for i, row in enumerate(values) if row and row[0] == "Journal")
    assert values[0][0] == "Recode: Q1 clean-up"
    assert len([r for r in values[header + 1 :] if r and r[0]]) == 8
    assert name.endswith(".xlsx")


def test_pdf_lists_every_change_and_the_undo(batch: Any) -> None:
    with org_context(batch.organisation):
        undone = undo(batch, batch.books["adviser"], reason="Wrong year")
    body, content_type, _name = export(undone, "pdf")
    assert content_type == "application/pdf"
    text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(body)).pages)
    assert "Recode audit report" in text and "Wrong year" in text
    rows = report_rows(undone)
    for row in rows:
        assert row[0] in text
    assert rows[0][17]  # undone by


def test_french_headers() -> None:
    from django.utils import translation

    from numo9.ledger.recode_report import headers

    with translation.override("fr-ca"):
        assert headers()[0] != "" and len(headers()) == 18


def test_unknown_format() -> None:
    with pytest.raises(ValueError):
        export(None, "doc")  # type: ignore[arg-type]
